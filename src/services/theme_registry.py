"""主题词典注册表 - 多来源合并、配置加载、候选发现和 AI 归属。"""

import json
import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import (
    AcceptedThemeTerm,
    MarketSector,
    SectorGroup,
    SectorGroupMember,
    SectorGroupSuggestion,
    SectorGroupSuggestionMember,
    ThemeTermSuggestion,
    TrackedSector,
)
from src.services.sector_trend_service import SectorIdentity
from src.storage.database import Database

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# 常量
# ------------------------------------------------------------------

CONFIG_PATH = Path("config/sector_group_themes.json")

THEME_TERM_SUGGESTION_TYPES = (
    "add_to_existing_theme",
    "create_theme",
    "mark_noise",
    "disable_term",
)

THEME_TERM_SUGGESTION_STATUSES = ("pending", "accepted", "ignored", "expired")

# 噪声词默认列表
DEFAULT_NOISE_TERMS: list[str] = [
    "本月解禁", "含GDR", "送转潜力", "高送转", "破发",
    "次新股", "注册制", "转融通", "融资融券", "IPO",
]

# 候选评分权重
SOURCE_WEIGHTS = {
    "market_summary": 3,
    "market_sector": 2,
    "cls_watch_title": 2,
    "cls_watch_content": 1,
    "co_occurrence": 2,
    "existing_theme_proximity": 1,
}
NOISE_PENALTY = -5
CANDIDATE_THRESHOLD = 4
AI_CONFIDENCE_THRESHOLD = 0.6


# ------------------------------------------------------------------
# 数据结构
# ------------------------------------------------------------------

@dataclass(frozen=True)
class ThemeEntry:
    """运行时主题条目。"""
    theme_name: str
    members: tuple[str, ...]
    source: str  # "builtin" | "user_config" | "learned" | "group"
    aliases: tuple[str, ...] = ()
    disabled_members: tuple[str, ...] = ()


@dataclass
class ThemeRegistry:
    """运行时主题注册表 - 合并多来源。"""
    themes: dict[str, ThemeEntry] = field(default_factory=dict)
    noise_terms: set[str] = field(default_factory=set)
    disabled_terms: set[str] = field(default_factory=set)
    _key_index: dict[str, str] = field(default_factory=dict)

    def rebuild_index(self) -> None:
        """重建 comparison_key → theme_name 索引。"""
        self._key_index.clear()
        for theme_name, entry in self.themes.items():
            for member in entry.members:
                key = SectorIdentity.comparison_key(member)
                if key not in self.disabled_terms and key not in self.noise_terms:
                    self._key_index[key] = theme_name
            for alias in entry.aliases:
                key = SectorIdentity.comparison_key(alias)
                if key not in self.disabled_terms and key not in self.noise_terms:
                    self._key_index[key] = theme_name

    def match(self, name: str) -> str | None:
        """匹配板块名称到主题。"""
        key = SectorIdentity.comparison_key(name)
        if key in self.noise_terms or key in self.disabled_terms:
            return None
        return self._key_index.get(key)

    def is_noise(self, name: str) -> bool:
        """判断是否为噪声词。"""
        return SectorIdentity.comparison_key(name) in self.noise_terms

    def is_disabled(self, name: str) -> bool:
        """判断是否为禁用词。"""
        return SectorIdentity.comparison_key(name) in self.disabled_terms

    def list_themes(self) -> list[dict[str, Any]]:
        """列出所有主题信息。"""
        result = []
        for name, entry in sorted(self.themes.items()):
            active_members = [
                m for m in entry.members
                if SectorIdentity.comparison_key(m) not in self.disabled_terms
                and SectorIdentity.comparison_key(m) not in self.noise_terms
            ]
            result.append({
                "name": name,
                "source": entry.source,
                "total_members": len(entry.members),
                "active_members": len(active_members),
                "disabled_count": len(entry.disabled_members),
            })
        return result

    def show_theme(self, name: str) -> dict[str, Any] | None:
        """查看主题详情。"""
        entry = self.themes.get(name)
        if not entry:
            return None
        return {
            "name": entry.theme_name,
            "source": entry.source,
            "members": list(entry.members),
            "aliases": list(entry.aliases),
            "disabled_members": list(entry.disabled_members),
        }

    def validate(self) -> list[dict[str, Any]]:
        """校验主题词典冲突。"""
        issues: list[dict[str, Any]] = []
        key_themes: dict[str, list[str]] = {}

        for theme_name, entry in self.themes.items():
            for member in entry.members:
                key = SectorIdentity.comparison_key(member)
                key_themes.setdefault(key, []).append(theme_name)

        for key, themes in key_themes.items():
            if len(themes) > 1:
                issues.append({
                    "type": "cross_theme_conflict",
                    "term_key": key,
                    "themes": themes,
                    "message": f"词 '{key}' 出现在多个主题中: {', '.join(themes)}",
                })

        for entry in self.themes.values():
            for member in entry.members:
                key = SectorIdentity.comparison_key(member)
                if key in self.noise_terms:
                    issues.append({
                        "type": "noise_conflict",
                        "term_key": key,
                        "theme": entry.theme_name,
                        "message": f"主题 '{entry.theme_name}' 的成员 '{key}' 同时在噪声词表中",
                    })
                if key in self.disabled_terms:
                    issues.append({
                        "type": "disabled_conflict",
                        "term_key": key,
                        "theme": entry.theme_name,
                        "message": f"主题 '{entry.theme_name}' 的成员 '{key}' 被禁用",
                    })

        return issues


# ------------------------------------------------------------------
# 服务
# ------------------------------------------------------------------

class ThemeRegistryService:
    """主题词典服务 - 注册表构建、配置加载、候选发现、AI 归属、建议审查。"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._registry: ThemeRegistry | None = None

    async def get_registry(self) -> ThemeRegistry:
        """获取或构建运行时主题注册表。"""
        if self._registry is not None:
            return self._registry

        registry = ThemeRegistry()

        # 层 1: 内置主题（最低优先级）
        from src.services.sector_group_service import THEME_DEFINITIONS
        for theme_name, members in THEME_DEFINITIONS.items():
            registry.themes[theme_name] = ThemeEntry(
                theme_name=theme_name,
                members=tuple(members),
                source="builtin",
            )

        # 层 2: 用户配置
        user_config = self._load_user_config()
        if user_config:
            themes = user_config.get("themes", {})
            for theme_name, cfg in themes.items():
                members = tuple(cfg.get("members", []))
                aliases = tuple(cfg.get("aliases", []))
                existing = registry.themes.get(theme_name)
                if existing:
                    # 合并成员
                    all_members = tuple(dict.fromkeys(existing.members + members))
                    all_aliases = tuple(dict.fromkeys(existing.aliases + aliases))
                    registry.themes[theme_name] = ThemeEntry(
                        theme_name=theme_name,
                        members=all_members,
                        source="user_config",
                        aliases=all_aliases,
                        disabled_members=tuple(cfg.get("disabled_members", [])),
                    )
                else:
                    registry.themes[theme_name] = ThemeEntry(
                        theme_name=theme_name,
                        members=members,
                        source="user_config",
                        aliases=aliases,
                    )

            # 噪声词
            for term in user_config.get("noise_terms", []):
                registry.noise_terms.add(SectorIdentity.comparison_key(term))

            # 禁用词
            for term in user_config.get("disabled_terms", []):
                registry.disabled_terms.add(SectorIdentity.comparison_key(term))

        # 层 3: 已接受学习结果
        async with self.db.get_session() as session:
            result = await session.execute(select(AcceptedThemeTerm))
            accepted = list(result.scalars().all())

        for at in accepted:
            existing = registry.themes.get(at.theme_name)
            if existing:
                all_members = tuple(dict.fromkeys(existing.members + (at.term,)))
                registry.themes[at.theme_name] = ThemeEntry(
                    theme_name=at.theme_name,
                    members=all_members,
                    source=existing.source,
                    aliases=existing.aliases,
                    disabled_members=existing.disabled_members,
                )
            else:
                registry.themes[at.theme_name] = ThemeEntry(
                    theme_name=at.theme_name,
                    members=(at.term,),
                    source="learned",
                )

        # 层 4: 活跃分组的别名/关键词/成员
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroup).where(SectorGroup.status == "active")
            )
            groups = list(result.scalars().all())

            result = await session.execute(select(SectorGroupMember))
            all_members = list(result.scalars().all())

            result = await session.execute(select(TrackedSector))
            all_sectors = {s.id: s for s in result.scalars().all()}

        for group in groups:
            group_member_names: list[str] = []
            for m in all_members:
                if m.group_id == group.id:
                    sector = all_sectors.get(m.sector_id)
                    if sector:
                        group_member_names.append(sector.canonical_name)

            existing = registry.themes.get(group.canonical_name)
            if existing:
                all_names = tuple(dict.fromkeys(
                    existing.members + tuple(group_member_names)
                ))
                registry.themes[group.canonical_name] = ThemeEntry(
                    theme_name=group.canonical_name,
                    members=all_names,
                    source=existing.source,
                    aliases=existing.aliases,
                    disabled_members=existing.disabled_members,
                )
            elif group_member_names:
                aliases: list[str] = []
                if group.aliases:
                    try:
                        aliases = json.loads(group.aliases)
                    except (json.JSONDecodeError, TypeError):
                        pass
                registry.themes[group.canonical_name] = ThemeEntry(
                    theme_name=group.canonical_name,
                    members=tuple(group_member_names),
                    source="group",
                    aliases=tuple(aliases),
                )

        # 层 5: 噪声词（最高优先级，覆盖所有）
        for term in DEFAULT_NOISE_TERMS:
            registry.noise_terms.add(SectorIdentity.comparison_key(term))

        registry.rebuild_index()
        self._registry = registry
        return registry

    def invalidate_cache(self) -> None:
        """清除注册表缓存，下次 get_registry 重新构建。"""
        self._registry = None

    @staticmethod
    def _load_user_config() -> dict[str, Any] | None:
        """加载用户配置。"""
        if not CONFIG_PATH.exists():
            return None
        try:
            content = CONFIG_PATH.read_text(encoding="utf-8")
            return json.loads(content)
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("主题配置加载失败: %s", e)
            return None

    @staticmethod
    def save_user_config(config: dict[str, Any]) -> None:
        """备份安全写入用户配置。"""
        CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
        if CONFIG_PATH.exists():
            backup = CONFIG_PATH.with_suffix(".json.bak")
            backup.write_text(CONFIG_PATH.read_text(encoding="utf-8"), encoding="utf-8")
        CONFIG_PATH.write_text(
            json.dumps(config, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # 建议生成
    # ------------------------------------------------------------------

    async def generate_theme_suggestions(
        self,
        days: int = 10,
        *,
        ai_processor: Any = None,
    ) -> dict[str, Any]:
        """生成主题词学习建议。"""
        registry = await self.get_registry()
        cutoff_date = date.today() - timedelta(days=days)

        # 收集候选
        candidates = await self._extract_candidates(cutoff_date, registry)

        # 规则评分
        scored = self._score_candidates(candidates, registry)

        # 过滤低证据
        high_evidence = [c for c in scored if c["score"] >= CANDIDATE_THRESHOLD]

        if not high_evidence:
            return {"suggestions_created": 0, "candidates_filtered": len(scored)}

        # AI 分类
        classified = []
        if ai_processor:
            classified = await self._classify_with_ai(high_evidence, registry, ai_processor)
        else:
            classified = self._rule_only_classify(high_evidence, registry)

        # 持久化
        created = 0
        for item in classified:
            if await self._persist_theme_suggestion(item, registry):
                created += 1

        return {
            "suggestions_created": created,
            "candidates_filtered": len(scored) - len(high_evidence),
            "candidates_classified": len(classified),
        }

    async def _extract_candidates(
        self,
        cutoff_date: date,
        registry: ThemeRegistry,
    ) -> list[dict[str, Any]]:
        """从多源提取主题词候选。"""
        candidates: dict[str, dict[str, Any]] = {}

        def add_candidate(term: str, source: str, evidence: dict[str, Any]) -> None:
            key = SectorIdentity.comparison_key(term)
            if not key:
                return
            if registry.is_noise(term) or registry.is_disabled(term):
                return
            if registry.match(term) is not None:
                return
            if key not in candidates:
                candidates[key] = {
                    "term": term,
                    "normalized_key": key,
                    "sources": [],
                    "evidence": [],
                }
            candidates[key]["sources"].append(source)
            candidates[key]["evidence"].append(evidence)

        # 来源 1: market_sectors
        async with self.db.get_session() as session:
            result = await session.execute(
                select(MarketSector.sector_name, MarketSector.trade_date)
                .where(MarketSector.trade_date >= cutoff_date)
            )
            for sector_name, trade_date in result.all():
                if sector_name:
                    add_candidate(sector_name, "market_sector", {
                        "trade_date": trade_date.isoformat(),
                    })

        # 来源 2: 已接受分组建议中的成员
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroupSuggestion).where(
                    SectorGroupSuggestion.status == "accepted"
                )
            )
            accepted_suggestions = list(result.scalars().all())

            for s in accepted_suggestions:
                result2 = await session.execute(
                    select(SectorGroupSuggestionMember).where(
                        SectorGroupSuggestionMember.suggestion_id == s.id
                    )
                )
                for sm in result2.scalars().all():
                    sector_result = await session.execute(
                        select(TrackedSector).where(TrackedSector.id == sm.sector_id)
                    )
                    sector = sector_result.scalar_one_or_none()
                    if sector:
                        add_candidate(sector.canonical_name, "accepted_group_suggestion", {
                            "suggestion_id": s.id,
                            "suggested_group_name": s.suggested_group_name,
                        })

        return list(candidates.values())

    @staticmethod
    def _score_candidates(
        candidates: list[dict[str, Any]],
        registry: ThemeRegistry,
    ) -> list[dict[str, Any]]:
        """规则评分。"""
        scored = []
        for c in candidates:
            score = 0
            source_counts: dict[str, int] = {}
            for src in c["sources"]:
                source_counts[src] = source_counts.get(src, 0) + 1
                weight = SOURCE_WEIGHTS.get(src, 1)
                score += weight

            # 同日共现加分
            if source_counts.get("market_sector", 0) >= 2:
                score += 2

            c["score"] = score
            c["source_counts"] = source_counts
            scored.append(c)
        return scored

    async def _classify_with_ai(
        self,
        candidates: list[dict[str, Any]],
        registry: ThemeRegistry,
        ai_processor: Any,
    ) -> list[dict[str, Any]]:
        """使用 AI 分类候选。"""
        theme_list = [
            {"name": name, "members": list(e.members)}
            for name, e in registry.themes.items()
        ]

        prompt = (
            "你是一个 A 股行业分析师。请判断以下候选词应归入哪个操作。\n\n"
            "可用操作：\n"
            "- add_to_existing_theme: 归入已有主题\n"
            "- create_theme: 创建新主题\n"
            "- mark_noise: 标记为噪声词\n"
            "- ignore: 忽略\n\n"
            f"已有主题:\n{json.dumps(theme_list, ensure_ascii=False, indent=2)}\n\n"
            f"噪声词: {list(registry.noise_terms)}\n\n"
            f"候选词:\n{json.dumps(candidates[:20], ensure_ascii=False, indent=2)}\n\n"
            "请严格按以下 JSON 格式返回（数组）：\n"
            '[{"term": "候选词", "action": "add_to_existing_theme", '
            '"target_theme_name": "主题名", "confidence": 0.8, "reason": "理由"}]\n'
            "confidence 低于 0.5 的建议用 ignore。"
        )

        try:
            response = await ai_processor._call_api(
                prompt=prompt,
                max_tokens=2000,
            )
        except Exception as e:
            logger.warning("AI 主题分类失败: %s", e)
            return self._rule_only_classify(candidates, registry)

        return self._parse_ai_classification(response, candidates, registry)

    @staticmethod
    def _parse_ai_classification(
        response: str,
        candidates: list[dict[str, Any]],
        registry: ThemeRegistry,
    ) -> list[dict[str, Any]]:
        """解析 AI 分类结果。"""
        json_str = response.strip()
        if "{" in json_str:
            start = json_str.find("[")
            end = json_str.rfind("]") + 1
            if start >= 0 and end > start:
                json_str = json_str[start:end]

        try:
            items = json.loads(json_str)
            if not isinstance(items, list):
                items = [items]
        except (json.JSONDecodeError, TypeError):
            return []

        candidate_keys = {c["normalized_key"] for c in candidates}
        known_themes = set(registry.themes.keys())
        results = []

        for item in items:
            term = item.get("term", "")
            key = SectorIdentity.comparison_key(term)
            if key not in candidate_keys:
                continue

            action = item.get("action", "ignore")
            if action not in THEME_TERM_SUGGESTION_TYPES and action != "ignore":
                action = "ignore"

            confidence = item.get("confidence", 0.0)
            if not isinstance(confidence, (int, float)):
                confidence = 0.0
            confidence = float(confidence)

            if confidence < AI_CONFIDENCE_THRESHOLD:
                continue

            target = item.get("target_theme_name")
            if action == "add_to_existing_theme" and target not in known_themes:
                continue

            results.append({
                "term": term,
                "normalized_key": key,
                "action": action,
                "target_theme_name": target,
                "confidence": confidence,
                "reason": item.get("reason", ""),
            })

        return results

    @staticmethod
    def _rule_only_classify(
        candidates: list[dict[str, Any]],
        registry: ThemeRegistry,
    ) -> list[dict[str, Any]]:
        """规则兜底分类。"""
        results = []
        for c in candidates:
            # 高分候选归入最接近的主题
            results.append({
                "term": c["term"],
                "normalized_key": c["normalized_key"],
                "action": "ignore",
                "target_theme_name": None,
                "confidence": 0.3,
                "reason": "规则兜底：无法确定归属",
            })
        return results

    async def _persist_theme_suggestion(
        self,
        item: dict[str, Any],
        registry: ThemeRegistry,
    ) -> bool:
        """持久化主题词建议。"""
        if item["action"] == "ignore":
            return False

        normalized_key = item["normalized_key"]

        # 检查是否已有相同 pending 建议
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ThemeTermSuggestion).where(
                    ThemeTermSuggestion.normalized_key == normalized_key,
                    ThemeTermSuggestion.status == "pending",
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                return False

            suggestion = ThemeTermSuggestion(
                suggestion_type=item["action"],
                target_theme_name=item.get("target_theme_name"),
                suggested_theme_name=item.get("suggested_theme_name"),
                term=item["term"],
                normalized_key=normalized_key,
                status="pending",
                confidence=item.get("confidence"),
                reason=item.get("reason"),
                evidence_json=json.dumps(item, ensure_ascii=False),
            )
            session.add(suggestion)

        return True

    # ------------------------------------------------------------------
    # 建议审查
    # ------------------------------------------------------------------

    async def list_theme_suggestions(
        self,
        status: str | None = "pending",
        suggestion_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出主题词建议。"""
        async with self.db.get_session() as session:
            query = select(ThemeTermSuggestion)
            if status:
                query = query.where(ThemeTermSuggestion.status == status)
            if suggestion_type:
                query = query.where(ThemeTermSuggestion.suggestion_type == suggestion_type)
            query = query.order_by(
                ThemeTermSuggestion.confidence.desc().nullslast(),
                ThemeTermSuggestion.created_at.desc(),
            )
            result = await session.execute(query)
            suggestions = result.scalars().all()

        return [
            {
                "id": s.id,
                "suggestion_type": s.suggestion_type,
                "target_theme_name": s.target_theme_name,
                "suggested_theme_name": s.suggested_theme_name,
                "term": s.term,
                "status": s.status,
                "confidence": s.confidence,
                "reason": s.reason,
                "created_at": s.created_at.isoformat() if s.created_at else None,
            }
            for s in suggestions
        ]

    async def accept_theme_suggestion(self, suggestion_id: int) -> dict[str, Any]:
        """接受主题词建议。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ThemeTermSuggestion).where(ThemeTermSuggestion.id == suggestion_id)
            )
            suggestion = result.scalar_one_or_none()
            if not suggestion:
                return {"action": "error", "error": f"建议 {suggestion_id} 不存在"}
            if suggestion.status != "pending":
                return {"action": "error", "error": f"建议 {suggestion_id} 状态为 {suggestion.status}"}

            suggestion.status = "accepted"

            # 写入已接受主题词记录
            accepted = AcceptedThemeTerm(
                theme_name=(
                    suggestion.target_theme_name
                    or suggestion.suggested_theme_name
                    or "未命名主题"
                ),
                term=suggestion.term,
                normalized_key=suggestion.normalized_key,
                source_suggestion_id=suggestion.id,
            )
            session.add(accepted)

        # 刷新注册表缓存
        self.invalidate_cache()

        return {
            "action": "accepted",
            "suggestion_id": suggestion_id,
            "term": suggestion.term,
            "theme_name": suggestion.target_theme_name or suggestion.suggested_theme_name,
        }

    async def ignore_theme_suggestion(self, suggestion_id: int) -> dict[str, Any]:
        """忽略主题词建议。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(ThemeTermSuggestion).where(ThemeTermSuggestion.id == suggestion_id)
            )
            suggestion = result.scalar_one_or_none()
            if not suggestion:
                return {"action": "error", "error": f"建议 {suggestion_id} 不存在"}
            if suggestion.status != "pending":
                return {"action": "error", "error": f"建议 {suggestion_id} 状态为 {suggestion.status}"}

            suggestion.status = "ignored"

        return {"action": "ignored", "suggestion_id": suggestion_id}

    # ------------------------------------------------------------------
    # 手动维护
    # ------------------------------------------------------------------

    async def add_theme_member(
        self,
        theme_name: str,
        member: str,
    ) -> dict[str, Any]:
        """手动添加主题词成员到用户配置。"""
        config = self._load_user_config() or {"themes": {}, "noise_terms": [], "disabled_terms": []}
        themes = config.setdefault("themes", {})
        if theme_name not in themes:
            themes[theme_name] = {"members": [], "aliases": []}
        members = themes[theme_name].setdefault("members", [])
        if member not in members:
            members.append(member)
        self.save_user_config(config)
        self.invalidate_cache()
        return {"action": "added", "theme": theme_name, "member": member}

    async def remove_theme_member(
        self,
        theme_name: str,
        member: str,
    ) -> dict[str, Any]:
        """从用户配置中移除主题词成员。"""
        config = self._load_user_config()
        if not config:
            return {"action": "error", "error": "用户配置不存在"}
        themes = config.get("themes", {})
        if theme_name not in themes:
            return {"action": "error", "error": f"主题 '{theme_name}' 不在用户配置中"}
        members = themes[theme_name].get("members", [])
        if member in members:
            members.remove(member)
        # 加入 disabled
        disabled = themes[theme_name].setdefault("disabled_members", [])
        if member not in disabled:
            disabled.append(member)
        self.save_user_config(config)
        self.invalidate_cache()
        return {"action": "removed", "theme": theme_name, "member": member}

    async def ignore_term(self, term: str) -> dict[str, Any]:
        """将词加入噪声词表。"""
        config = self._load_user_config() or {"themes": {}, "noise_terms": [], "disabled_terms": []}
        noise = config.setdefault("noise_terms", [])
        if term not in noise:
            noise.append(term)
        self.save_user_config(config)
        self.invalidate_cache()
        return {"action": "ignored", "term": term}
