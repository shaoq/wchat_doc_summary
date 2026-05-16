"""板块分组服务 - 分组 CRUD、成员管理、建议生成与审查、组级趋势更新。"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import and_, func as sql_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.schema import (
    SectorGroup,
    SectorGroupMember,
    SectorGroupSuggestion,
    SectorGroupSuggestionMember,
    SectorGroupTrendSummary,
    SectorTrendSummary,
    TrackedSector,
)
from src.services.sector_trend_service import SectorIdentity
from src.storage.database import Database

logger = logging.getLogger(__name__)

GROUP_OUTPUT_DIR = Path("output/sector_groups")

RELATION_TYPES = (
    "core", "upstream", "downstream", "material",
    "equipment", "catalyst", "related",
)

SUGGESTION_TYPES = ("new_group", "add_members", "update_members")
SUGGESTION_STATUSES = ("pending", "accepted", "ignored", "expired")


class SectorGroupService:
    """板块分组服务。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # 分组 CRUD
    # ------------------------------------------------------------------

    async def create_group(
        self,
        name: str,
        aliases: list[str] | None = None,
        keywords: list[str] | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """创建板块分组。

        Args:
            name: 分组名称
            aliases: 别名列表
            keywords: 关键词列表
            description: 描述

        Returns:
            创建结果
        """
        canonical = SectorIdentity.normalize(name)

        async with self.db.get_session() as session:
            existing = await self._resolve_group(session, canonical)
            if existing:
                return {
                    "action": "already_exists",
                    "group_id": existing.id,
                    "canonical_name": existing.canonical_name,
                }

            group = SectorGroup(
                canonical_name=canonical,
                aliases=json.dumps(aliases or [], ensure_ascii=False),
                keywords=json.dumps(keywords or [], ensure_ascii=False),
                description=description,
                status="active",
            )
            session.add(group)
            await session.flush()
            await session.refresh(group)

            return {
                "action": "created",
                "group_id": group.id,
                "canonical_name": group.canonical_name,
            }

    async def list_groups(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """列出分组。

        Args:
            status: 状态筛选
            limit: 返回数量

        Returns:
            分组信息列表
        """
        async with self.db.get_session() as session:
            query = select(SectorGroup)

            if status:
                query = query.where(SectorGroup.status == status)
            else:
                query = query.where(SectorGroup.status == "active")

            query = query.order_by(SectorGroup.updated_at.desc()).limit(limit)
            result = await session.execute(query)
            groups = result.scalars().all()

            output = []
            for g in groups:
                member_count = await self._count_members(session, g.id)
                latest_update = await self._get_latest_group_summary_date(session, g.id)
                pending_suggestions = await self._count_pending_suggestions(session, g.id)

                output.append({
                    "id": g.id,
                    "canonical_name": g.canonical_name,
                    "description": g.description,
                    "status": g.status,
                    "member_count": member_count,
                    "latest_update_date": latest_update.isoformat() if latest_update else None,
                    "pending_suggestion_count": pending_suggestions,
                })

            return output

    async def resolve_group(
        self,
        name: str,
    ) -> dict[str, Any] | None:
        """按名称或别名解析分组。

        Args:
            name: 分组名称或别名

        Returns:
            分组信息或 None
        """
        async with self.db.get_session() as session:
            group = await self._resolve_group(session, name)
            if not group:
                return None
            return {
                "id": group.id,
                "canonical_name": group.canonical_name,
                "status": group.status,
            }

    async def show_group_detail(
        self,
        name: str,
    ) -> dict[str, Any] | None:
        """查看分组详情，包含成员信息。

        Args:
            name: 分组名称

        Returns:
            分组详情或 None
        """
        async with self.db.get_session() as session:
            group = await self._resolve_group(session, name)
            if not group:
                return None

            members = await self._load_group_members(session, group.id)

            aliases: list[str] = []
            if group.aliases:
                try:
                    aliases = json.loads(group.aliases)
                except (json.JSONDecodeError, TypeError):
                    pass

            keywords: list[str] = []
            if group.keywords:
                try:
                    keywords = json.loads(group.keywords)
                except (json.JSONDecodeError, TypeError):
                    pass

            return {
                "id": group.id,
                "canonical_name": group.canonical_name,
                "aliases": aliases,
                "keywords": keywords,
                "description": group.description,
                "status": group.status,
                "members": members,
                "created_at": group.created_at.isoformat() if group.created_at else None,
                "updated_at": group.updated_at.isoformat() if group.updated_at else None,
            }

    # ------------------------------------------------------------------
    # 成员管理
    # ------------------------------------------------------------------

    async def add_member(
        self,
        group_name: str,
        sector_name: str,
        relation_type: str = "related",
        weight: float | None = None,
        source: str = "manual",
        confidence: float | None = None,
    ) -> dict[str, Any]:
        """向分组添加成员。

        如果成员已存在则更新元数据。

        Args:
            group_name: 分组名称
            sector_name: 板块名称
            relation_type: 关系类型
            weight: 权重
            source: 来源
            confidence: 置信度

        Returns:
            操作结果
        """
        if relation_type not in RELATION_TYPES:
            return {"action": "error", "error": f"无效的关系类型: {relation_type}"}

        canonical_sector = SectorIdentity.normalize(sector_name)

        async with self.db.get_session() as session:
            group = await self._resolve_group(session, group_name)
            if not group:
                return {"action": "error", "error": f"分组 '{group_name}' 不存在"}

            sector = await self._resolve_sector(session, canonical_sector)
            if not sector:
                return {"action": "error", "error": f"板块 '{sector_name}' 不存在"}

            # 检查是否已有成员关系
            result = await session.execute(
                select(SectorGroupMember).where(
                    SectorGroupMember.group_id == group.id,
                    SectorGroupMember.sector_id == sector.id,
                )
            )
            existing_member = result.scalar_one_or_none()

            if existing_member:
                # 更新元数据而非创建重复记录
                existing_member.relation_type = relation_type
                if weight is not None:
                    existing_member.weight = weight
                if source is not None:
                    existing_member.source = source
                if confidence is not None:
                    existing_member.confidence = confidence
                return {
                    "action": "updated",
                    "group_id": group.id,
                    "sector_id": sector.id,
                    "sector_name": sector.canonical_name,
                    "relation_type": relation_type,
                }

            member = SectorGroupMember(
                group_id=group.id,
                sector_id=sector.id,
                relation_type=relation_type,
                weight=weight or 1.0,
                source=source,
                confidence=confidence,
            )
            session.add(member)

            return {
                "action": "added",
                "group_id": group.id,
                "sector_id": sector.id,
                "sector_name": sector.canonical_name,
                "relation_type": relation_type,
            }

    # ------------------------------------------------------------------
    # 建议生成
    # ------------------------------------------------------------------

    async def generate_suggestions(
        self,
        days: int = 10,
    ) -> dict[str, Any]:
        """生成分组建议。

        基于近期板块共现和已有分组成员重疊分析。

        Args:
            days: 回看天数

        Returns:
            生成结果统计
        """
        cutoff_date = date.today() - timedelta(days=days)

        async with self.db.get_session() as session:
            # 获取 tracked 和 candidate 板块
            result = await session.execute(
                select(TrackedSector).where(
                    TrackedSector.status.in_(["tracked", "candidate"])
                )
            )
            eligible_sectors = list(result.scalars().all())

            # 获取已有分组
            result = await session.execute(
                select(SectorGroup).where(SectorGroup.status == "active")
            )
            existing_groups = list(result.scalars().all())

            # 获取已有成员
            result = await session.execute(select(SectorGroupMember))
            existing_members = list(result.scalars().all())

            # 获取已有 pending 建议
            result = await session.execute(
                select(SectorGroupSuggestion).where(
                    SectorGroupSuggestion.status == "pending"
                )
            )
            pending_suggestions = list(result.scalars().all())

        # 构建共现图（从 CLS 看盘板块标签）
        co_occurrence = await self._build_co_occurrence(cutoff_date)

        # 生成建议
        new_count = 0
        add_count = 0
        refresh_count = 0

        for group in existing_groups:
            suggestions = await self._suggest_for_existing_group(
                group=group,
                eligible_sectors=eligible_sectors,
                existing_members=existing_members,
                co_occurrence=co_occurrence,
                pending_suggestions=pending_suggestions,
                days=days,
            )
            add_count += suggestions["add_members"]
            refresh_count += suggestions["refreshed"]

        # 检测新分组机会
        new_group_suggestions = await self._suggest_new_groups(
            eligible_sectors=eligible_sectors,
            existing_groups=existing_groups,
            existing_members=existing_members,
            co_occurrence=co_occurrence,
            pending_suggestions=pending_suggestions,
            days=days,
        )
        new_count = new_group_suggestions["new_groups"]

        return {
            "new_group_suggestions": new_count,
            "add_member_suggestions": add_count,
            "refreshed_suggestions": refresh_count,
        }

    async def list_suggestions(
        self,
        status: str | None = "pending",
        suggestion_type: str | None = None,
        group_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """列出建议。

        Args:
            status: 状态筛选
            suggestion_type: 建议类型筛选
            group_name: 目标分组筛选

        Returns:
            建议列表
        """
        async with self.db.get_session() as session:
            query = select(SectorGroupSuggestion)

            if status:
                query = query.where(SectorGroupSuggestion.status == status)
            if suggestion_type:
                query = query.where(SectorGroupSuggestion.suggestion_type == suggestion_type)

            if group_name:
                group = await self._resolve_group(session, group_name)
                if group:
                    query = query.where(SectorGroupSuggestion.target_group_id == group.id)

            query = query.order_by(SectorGroupSuggestion.confidence.desc().nullslast())
            result = await session.execute(query)
            suggestions = result.scalars().all()

            output = []
            for s in suggestions:
                members = await self._load_suggestion_members(session, s.id)
                group_name_resolved = None
                if s.target_group_id:
                    grp = await session.execute(
                        select(SectorGroup).where(SectorGroup.id == s.target_group_id)
                    )
                    grp_obj = grp.scalar_one_or_none()
                    if grp_obj:
                        group_name_resolved = grp_obj.canonical_name

                output.append({
                    "id": s.id,
                    "suggestion_type": s.suggestion_type,
                    "target_group_id": s.target_group_id,
                    "target_group_name": group_name_resolved,
                    "suggested_group_name": s.suggested_group_name,
                    "status": s.status,
                    "confidence": s.confidence,
                    "reason": s.reason,
                    "members": members,
                    "created_at": s.created_at.isoformat() if s.created_at else None,
                })

            return output

    async def accept_suggestion(
        self,
        suggestion_id: int,
        include_sectors: list[str] | None = None,
        exclude_sectors: list[str] | None = None,
        keep_status: bool = False,
    ) -> dict[str, Any]:
        """接受建议。

        Args:
            suggestion_id: 建议 ID
            include_sectors: 仅接受这些板块（部分接受）
            exclude_sectors: 排除这些板块
            keep_status: 保持板块原状态，不提升 candidate 为 tracked

        Returns:
            接受结果
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroupSuggestion).where(
                    SectorGroupSuggestion.id == suggestion_id
                )
            )
            suggestion = result.scalar_one_or_none()
            if not suggestion:
                return {"action": "error", "error": f"建议 {suggestion_id} 不存在"}
            if suggestion.status != "pending":
                return {"action": "error", "error": f"建议 {suggestion_id} 状态为 {suggestion.status}，无法接受"}

            # 加载建议成员
            result = await session.execute(
                select(SectorGroupSuggestionMember).where(
                    SectorGroupSuggestionMember.suggestion_id == suggestion_id
                )
            )
            suggestion_members = list(result.scalars().all())

            # 确定目标分组
            group_id = suggestion.target_group_id
            if suggestion.suggestion_type == "new_group" and not group_id:
                group = SectorGroup(
                    canonical_name=SectorIdentity.normalize(
                        suggestion.suggested_group_name or "未命名分组"
                    ),
                    status="active",
                )
                session.add(group)
                await session.flush()
                await session.refresh(group)
                group_id = group.id

            if not group_id:
                return {"action": "error", "error": "无法确定目标分组"}

            # 筛选成员
            accepted_members = []
            for sm in suggestion_members:
                sector = await session.execute(
                    select(TrackedSector).where(TrackedSector.id == sm.sector_id)
                )
                sector_obj = sector.scalar_one_or_none()
                if not sector_obj:
                    continue

                sector_name = sector_obj.canonical_name

                if include_sectors:
                    if sector_name not in include_sectors and sector_obj.canonical_name not in include_sectors:
                        continue
                if exclude_sectors:
                    if sector_name in exclude_sectors or sector_obj.canonical_name in exclude_sectors:
                        continue

                # 检查是否已是成员
                existing = await session.execute(
                    select(SectorGroupMember).where(
                        SectorGroupMember.group_id == group_id,
                        SectorGroupMember.sector_id == sm.sector_id,
                    )
                )
                existing_member = existing.scalar_one_or_none()

                if existing_member:
                    # 更新已有成员
                    if sm.suggested_relation_type:
                        existing_member.relation_type = sm.suggested_relation_type
                    if sm.suggested_weight is not None:
                        existing_member.weight = sm.suggested_weight
                else:
                    # 创建新成员
                    member = SectorGroupMember(
                        group_id=group_id,
                        sector_id=sm.sector_id,
                        relation_type=sm.suggested_relation_type or "related",
                        weight=sm.suggested_weight or 1.0,
                        source="suggestion",
                        confidence=sm.confidence,
                    )
                    session.add(member)

                # 提升 candidate 为 tracked
                if not keep_status and sector_obj.status == "candidate":
                    sector_obj.status = "tracked"

                accepted_members.append(sector_name)

            suggestion.status = "accepted"

            return {
                "action": "accepted",
                "suggestion_id": suggestion_id,
                "group_id": group_id,
                "accepted_members": accepted_members,
            }

    async def ignore_suggestion(
        self,
        suggestion_id: int,
    ) -> dict[str, Any]:
        """忽略建议。

        Args:
            suggestion_id: 建议 ID

        Returns:
            操作结果
        """
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroupSuggestion).where(
                    SectorGroupSuggestion.id == suggestion_id
                )
            )
            suggestion = result.scalar_one_or_none()
            if not suggestion:
                return {"action": "error", "error": f"建议 {suggestion_id} 不存在"}
            if suggestion.status != "pending":
                return {"action": "error", "error": f"建议 {suggestion_id} 状态为 {suggestion.status}，无法忽略"}

            suggestion.status = "ignored"

            return {
                "action": "ignored",
                "suggestion_id": suggestion_id,
            }

    # ------------------------------------------------------------------
    # 组级趋势更新
    # ------------------------------------------------------------------

    async def update_group_trend(
        self,
        group_name: str,
        *,
        ai_processor: Any = None,
        force: bool = False,
        no_refresh_members: bool = False,
        force_refresh_members: bool = False,
        days: int = 10,
        continue_on_error: bool = True,
    ) -> dict[str, Any]:
        """更新分组趋势。

        Args:
            group_name: 分组名称
            ai_processor: AI 处理器
            force: 强制重新生成
            no_refresh_members: 跳过成员刷新
            force_refresh_members: 强制刷新所有成员
            days: 回看窗口天数
            continue_on_error: 成员刷新失败后继续

        Returns:
            更新结果
        """
        from src.services.sector_trend_service import SectorTrendAnalyzer
        from src.services.trade_calendar import get_previous_trade_date, is_trade_day

        end_date = self._get_latest_trade_date()

        async with self.db.get_session() as session:
            group = await self._resolve_group(session, group_name)
            if not group:
                return {"action": "error", "error": f"分组 '{group_name}' 不存在"}

            group_id = group.id
            group_canonical = group.canonical_name

        # 检查已有报告
        if not force:
            existing_summary = await self._get_latest_group_summary(group_id)
            if existing_summary and existing_summary.end_date == end_date:
                return {
                    "action": "skipped",
                    "group_name": group_canonical,
                    "reason": "今日已更新",
                    "output_path": existing_summary.output_path,
                }

        # 加载成员
        async with self.db.get_session() as session:
            members = await self._load_group_members(session, group_id)

        # 成员刷新
        refresh_results: list[dict[str, Any]] = []
        if not no_refresh_members and ai_processor:
            analyzer = SectorTrendAnalyzer(self.db)
            for member in members:
                sector_status = member.get("sector_status")
                if sector_status == "candidate":
                    refresh_results.append({
                        "sector_name": member["sector_name"],
                        "action": "skipped_candidate",
                    })
                    continue

                if sector_status not in ("tracked",):
                    refresh_results.append({
                        "sector_name": member["sector_name"],
                        "action": "skipped_status",
                    })
                    continue

                # 检查是否已有当日报告
                if not force_refresh_members:
                    has_today = await self._sector_has_report(member["sector_id"], end_date)
                    if has_today:
                        refresh_results.append({
                            "sector_name": member["sector_name"],
                            "action": "skipped_has_report",
                        })
                        continue

                try:
                    update_result = await analyzer.update_sector_trend(
                        member["sector_name"],
                        days=days,
                        ai_processor=ai_processor,
                        force=force_refresh_members,
                    )
                    refresh_results.append(update_result)
                except Exception as e:
                    logger.error("刷新成员 %s 失败: %s", member["sector_name"], e)
                    refresh_results.append({
                        "action": "failed",
                        "sector_name": member["sector_name"],
                        "error": str(e),
                    })
                    if not continue_on_error:
                        break

        # 收集组级证据
        evidence = await self._collect_group_evidence(group_id, end_date, days)

        # 成员新鲜度
        member_freshness = await self._calculate_member_freshness(
            group_id, end_date, members
        )

        # AI 生成组级报告
        if ai_processor is None:
            return {
                "action": "no_ai_processor",
                "group_name": group_canonical,
                "evidence": evidence,
                "member_refresh_results": refresh_results,
            }

        content, labels = await ai_processor.generate_sector_group_trend_summary(
            group_name=group_canonical,
            evidence=evidence,
            member_freshness=member_freshness,
            end_date=end_date.isoformat(),
            window_days=days,
        )

        # 保存报告
        summary = await self._save_group_trend_summary(
            group_id=group_id,
            group_name=group_canonical,
            end_date=end_date,
            window_days=days,
            content=content,
            trend_status=labels.get("trend_status"),
            strength_level=labels.get("strength_level"),
            action_bias=labels.get("action_bias"),
            judgement=labels.get("judgement"),
            evidence_json=json.dumps(evidence, ensure_ascii=False),
            member_freshness_json=json.dumps(member_freshness, ensure_ascii=False),
        )

        return {
            "action": "updated",
            "group_name": group_canonical,
            "end_date": end_date.isoformat(),
            "output_path": summary.output_path,
            "trend_status": labels.get("trend_status"),
            "strength_level": labels.get("strength_level"),
            "action_bias": labels.get("action_bias"),
            "member_refresh_results": refresh_results,
        }

    async def update_all_group_trends(
        self,
        *,
        ai_processor: Any = None,
        force: bool = False,
        no_refresh_members: bool = False,
        force_refresh_members: bool = False,
        days: int = 10,
        continue_on_error: bool = True,
        limit: int | None = None,
    ) -> dict[str, Any]:
        """批量更新所有活跃分组趋势。

        Args:
            ai_processor: AI 处理器
            force: 强制重新生成
            no_refresh_members: 跳过成员刷新
            force_refresh_members: 强制刷新所有成员
            days: 回看窗口天数
            continue_on_error: 错误时继续
            limit: 最大更新数量

        Returns:
            批量更新结果
        """
        async with self.db.get_session() as session:
            query = select(SectorGroup).where(
                SectorGroup.status == "active"
            ).order_by(SectorGroup.updated_at.asc())
            if limit:
                query = query.limit(limit)
            result = await session.execute(query)
            groups = list(result.scalars().all())

        results: list[dict[str, Any]] = []
        success = 0
        skipped = 0
        failed = 0
        member_refresh_success = 0
        member_refresh_failed = 0

        for group in groups:
            try:
                update_result = await self.update_group_trend(
                    group.canonical_name,
                    ai_processor=ai_processor,
                    force=force,
                    no_refresh_members=no_refresh_members,
                    force_refresh_members=force_refresh_members,
                    days=days,
                    continue_on_error=continue_on_error,
                )
                results.append(update_result)

                action = update_result.get("action")
                if action == "updated":
                    success += 1
                elif action == "skipped":
                    skipped += 1
                else:
                    skipped += 1

                # 统计成员刷新
                for mr in update_result.get("member_refresh_results", []):
                    if mr.get("action") == "updated":
                        member_refresh_success += 1
                    elif mr.get("action") == "failed":
                        member_refresh_failed += 1

            except Exception as e:
                logger.error("更新分组 %s 失败: %s", group.canonical_name, e)
                failed += 1
                results.append({
                    "action": "failed",
                    "group_name": group.canonical_name,
                    "error": str(e),
                })
                if not continue_on_error:
                    break

        return {
            "total": len(groups),
            "success": success,
            "skipped": skipped,
            "failed": failed,
            "member_refresh_success": member_refresh_success,
            "member_refresh_failed": member_refresh_failed,
            "results": results,
        }

    # ------------------------------------------------------------------
    # 查看与历史
    # ------------------------------------------------------------------

    async def show_latest_group_report(
        self,
        group_name: str,
    ) -> dict[str, Any] | None:
        """查看分组最新趋势报告。"""
        async with self.db.get_session() as session:
            group = await self._resolve_group(session, group_name)
            if not group:
                return None

            summary = await self._get_latest_group_summary(group.id)
            if not summary:
                return {
                    "group_name": group.canonical_name,
                    "status": group.status,
                    "has_summary": False,
                }

            return {
                "group_name": group.canonical_name,
                "status": group.status,
                "has_summary": True,
                "end_date": summary.end_date.isoformat() if summary.end_date else None,
                "trend_status": summary.trend_status,
                "strength_level": summary.strength_level,
                "action_bias": summary.action_bias,
                "content": summary.content,
                "output_path": summary.output_path,
                "member_freshness": summary.member_freshness_json,
            }

    async def group_history(
        self,
        group_name: str,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """查看分组趋势历史。"""
        async with self.db.get_session() as session:
            group = await self._resolve_group(session, group_name)
            if not group:
                return []

            result = await session.execute(
                select(SectorGroupTrendSummary)
                .where(SectorGroupTrendSummary.group_id == group.id)
                .order_by(SectorGroupTrendSummary.end_date.desc())
                .limit(limit)
            )
            summaries = result.scalars().all()

        return [
            {
                "end_date": s.end_date.isoformat() if s.end_date else None,
                "trend_status": s.trend_status,
                "strength_level": s.strength_level,
                "action_bias": s.action_bias,
                "output_path": s.output_path,
            }
            for s in summaries
        ]

    # ------------------------------------------------------------------
    # 私有辅助方法
    # ------------------------------------------------------------------

    async def _resolve_group(
        self,
        session: AsyncSession,
        name: str,
    ) -> SectorGroup | None:
        """按名称或别名解析分组。"""
        canonical = SectorIdentity.normalize(name)

        # 先按规范名精确匹配
        result = await session.execute(
            select(SectorGroup).where(
                SectorGroup.canonical_name == canonical
            )
        )
        group = result.scalar_one_or_none()
        if group:
            return group

        # 按别名匹配
        result = await session.execute(select(SectorGroup))
        all_groups = result.scalars().all()

        name_key = SectorIdentity.comparison_key(name)
        for g in all_groups:
            if g.aliases:
                try:
                    aliases = json.loads(g.aliases)
                    for alias in aliases:
                        if SectorIdentity.comparison_key(alias) == name_key:
                            return g
                except (json.JSONDecodeError, TypeError):
                    pass
            if g.keywords:
                try:
                    keywords = json.loads(g.keywords)
                    for kw in keywords:
                        if SectorIdentity.comparison_key(kw) == name_key:
                            return g
                except (json.JSONDecodeError, TypeError):
                    pass

        return None

    async def _resolve_sector(
        self,
        session: AsyncSession,
        name: str,
    ) -> TrackedSector | None:
        """按名称解析板块。"""
        canonical = SectorIdentity.normalize(name)
        result = await session.execute(
            select(TrackedSector).where(
                TrackedSector.canonical_name == canonical
            )
        )
        return result.scalar_one_or_none()

    async def _count_members(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> int:
        """统计分组成员数量。"""
        result = await session.execute(
            select(sql_func.count(SectorGroupMember.id)).where(
                SectorGroupMember.group_id == group_id
            )
        )
        return result.scalar() or 0

    async def _count_pending_suggestions(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> int:
        """统计分组待处理建议数量。"""
        result = await session.execute(
            select(sql_func.count(SectorGroupSuggestion.id)).where(
                SectorGroupSuggestion.target_group_id == group_id,
                SectorGroupSuggestion.status == "pending",
            )
        )
        return result.scalar() or 0

    async def _get_latest_group_summary_date(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> date | None:
        """获取分组最新趋势报告日期。"""
        result = await session.execute(
            select(sql_func.max(SectorGroupTrendSummary.end_date)).where(
                SectorGroupTrendSummary.group_id == group_id
            )
        )
        return result.scalar()

    async def _load_group_members(
        self,
        session: AsyncSession,
        group_id: int,
    ) -> list[dict[str, Any]]:
        """加载分组成员详情。"""
        result = await session.execute(
            select(SectorGroupMember, TrackedSector)
            .join(TrackedSector, SectorGroupMember.sector_id == TrackedSector.id)
            .where(SectorGroupMember.group_id == group_id)
            .order_by(SectorGroupMember.weight.desc().nullslast())
        )
        rows = result.all()

        members = []
        for member, sector in rows:
            # 获取板块最新趋势报告日期
            latest_summary_result = await session.execute(
                select(sql_func.max(SectorTrendSummary.end_date)).where(
                    SectorTrendSummary.sector_id == sector.id
                )
            )
            latest_summary_date = latest_summary_result.scalar()

            members.append({
                "sector_id": sector.id,
                "sector_name": sector.canonical_name,
                "sector_status": sector.status,
                "relation_type": member.relation_type,
                "weight": member.weight,
                "source": member.source,
                "confidence": member.confidence,
                "last_seen_date": sector.last_seen_date.isoformat() if sector.last_seen_date else None,
                "last_updated_date": sector.last_updated_date.isoformat() if sector.last_updated_date else None,
                "latest_summary_date": latest_summary_date.isoformat() if latest_summary_date else None,
            })

        return members

    async def _load_suggestion_members(
        self,
        session: AsyncSession,
        suggestion_id: int,
    ) -> list[dict[str, Any]]:
        """加载建议成员详情。"""
        result = await session.execute(
            select(SectorGroupSuggestionMember, TrackedSector)
            .join(TrackedSector, SectorGroupSuggestionMember.sector_id == TrackedSector.id)
            .where(SectorGroupSuggestionMember.suggestion_id == suggestion_id)
        )
        rows = result.all()

        return [
            {
                "sector_id": sector.id,
                "sector_name": sector.canonical_name,
                "sector_status": sector.status,
                "suggested_relation_type": sm.suggested_relation_type,
                "current_relation_type": sm.current_relation_type,
                "suggested_weight": sm.suggested_weight,
                "current_weight": sm.current_weight,
                "confidence": sm.confidence,
                "reason": sm.reason,
            }
            for sm, sector in rows
        ]

    async def _build_co_occurrence(
        self,
        cutoff_date: date,
    ) -> dict[str, dict[str, int]]:
        """构建板块共现矩阵（基于 CLS 看盘数据）。"""
        from src.models.schema import CLSWatchData

        cutoff_ts = int(datetime.combine(cutoff_date, datetime.min.time()).timestamp())

        async with self.db.get_session() as session:
            result = await session.execute(
                select(CLSWatchData.sectors)
                .where(CLSWatchData.ctime >= cutoff_ts)
                .where(CLSWatchData.sectors.isnot(None))
            )
            rows = result.all()

        co_occurrence: dict[str, dict[str, int]] = {}

        for row in rows:
            try:
                sectors = json.loads(row.sectors) if row.sectors else []
                sectors = [s.strip() for s in sectors if isinstance(s, str) and s.strip()]
            except (json.JSONDecodeError, TypeError):
                continue

            for i, s1 in enumerate(sectors):
                for s2 in sectors[i + 1:]:
                    key1 = SectorIdentity.comparison_key(s1)
                    key2 = SectorIdentity.comparison_key(s2)
                    if key1 == key2:
                        continue
                    if key1 not in co_occurrence:
                        co_occurrence[key1] = {}
                    co_occurrence[key1][key2] = co_occurrence[key1].get(key2, 0) + 1
                    if key2 not in co_occurrence:
                        co_occurrence[key2] = {}
                    co_occurrence[key2][key1] = co_occurrence[key2].get(key1, 0) + 1

        return co_occurrence

    async def _suggest_for_existing_group(
        self,
        group: SectorGroup,
        eligible_sectors: list[TrackedSector],
        existing_members: list[SectorGroupMember],
        co_occurrence: dict[str, dict[str, int]],
        pending_suggestions: list[SectorGroupSuggestion],
        days: int,
    ) -> dict[str, int]:
        """为已有分组生成 add_members 建议。"""
        add_count = 0
        refreshed = 0

        # 获取该分组已有的成员 sector_id
        group_member_ids = {
            m.sector_id for m in existing_members if m.group_id == group.id
        }

        # 获取该分组已有的 pending 建议
        group_pending = [
            s for s in pending_suggestions
            if s.target_group_id == group.id and s.status == "pending"
        ]
        pending_sector_ids: set[int] = set()
        for s in group_pending:
            # 获取 pending 建议的成员
            async with self.db.get_session() as session:
                from sqlalchemy import select as sa_select
                result = await session.execute(
                    sa_select(SectorGroupSuggestionMember.sector_id).where(
                        SectorGroupSuggestionMember.suggestion_id == s.id
                    )
                )
                for row in result.all():
                    pending_sector_ids.add(row[0])

        # 检查共现关系
        group_key = SectorIdentity.comparison_key(group.canonical_name)
        related_sectors: list[tuple[TrackedSector, int]] = []

        # 从分组名/别名/关键词查找共现
        search_keys = [group_key]
        if group.aliases:
            try:
                for alias in json.loads(group.aliases):
                    search_keys.append(SectorIdentity.comparison_key(alias))
            except (json.JSONDecodeError, TypeError):
                pass
        if group.keywords:
            try:
                for kw in json.loads(group.keywords):
                    search_keys.append(SectorIdentity.comparison_key(kw))
            except (json.JSONDecodeError, TypeError):
                pass

        for sector in eligible_sectors:
            if sector.id in group_member_ids:
                continue
            if sector.status == "ignored":
                continue
            if sector.status == "inactive":
                continue

            sector_key = SectorIdentity.comparison_key(sector.canonical_name)

            # 检查共现
            max_co = 0
            for sk in search_keys:
                co = co_occurrence.get(sk, {}).get(sector_key, 0)
                max_co = max(max_co, co)

            if max_co >= 2:
                related_sectors.append((sector, max_co))

        if not related_sectors:
            return {"add_members": 0, "refreshed": 0}

        # 按共现次数排序
        related_sectors.sort(key=lambda x: -x[1])

        # 生成建议
        suggestion_members: list[dict[str, Any]] = []
        for sector, co_count in related_sectors[:10]:
            if sector.id in pending_sector_ids:
                refreshed += 1
                continue

            suggestion_members.append({
                "sector_id": sector.id,
                "relation_type": "related",
                "confidence": min(co_count / 10.0, 1.0),
                "reason": f"与分组 '{group.canonical_name}' 近{days}日共现{co_count}次",
            })

        if suggestion_members:
            async with self.db.get_session() as session:
                suggestion = SectorGroupSuggestion(
                    suggestion_type="add_members",
                    target_group_id=group.id,
                    status="pending",
                    confidence=max(m["confidence"] for m in suggestion_members),
                    reason=f"基于近{days}日共现分析，建议向分组 '{group.canonical_name}' 添加{len(suggestion_members)}个成员",
                )
                session.add(suggestion)
                await session.flush()
                await session.refresh(suggestion)

                for sm_data in suggestion_members:
                    member = SectorGroupSuggestionMember(
                        suggestion_id=suggestion.id,
                        sector_id=sm_data["sector_id"],
                        suggested_relation_type=sm_data["relation_type"],
                        confidence=sm_data["confidence"],
                        reason=sm_data["reason"],
                    )
                    session.add(member)

                add_count += 1

        return {"add_members": add_count, "refreshed": refreshed}

    async def _suggest_new_groups(
        self,
        eligible_sectors: list[TrackedSector],
        existing_groups: list[SectorGroup],
        existing_members: list[SectorGroupMember],
        co_occurrence: dict[str, dict[str, int]],
        pending_suggestions: list[SectorGroupSuggestion],
        days: int,
    ) -> dict[str, int]:
        """检测新分组机会。"""
        # 获取已有 pending new_group 建议的名称
        pending_names = {
            SectorIdentity.comparison_key(s.suggested_group_name or "")
            for s in pending_suggestions
            if s.suggestion_type == "new_group" and s.status == "pending"
        }

        # 获取已在任何分组中的 sector_id
        all_member_ids = {m.sector_id for m in existing_members}

        # 寻找高频共现但未归组的板块对
        pair_count: dict[frozenset[str], int] = {}
        for key1, partners in co_occurrence.items():
            for key2, count in partners.items():
                if count >= 3:
                    pair = frozenset([key1, key2])
                    pair_count[pair] = pair_count.get(pair, 0) + count

        if not pair_count:
            return {"new_groups": 0}

        # 聚类：简单贪心聚类
        used_keys: set[str] = set()
        clusters: list[set[str]] = []

        for pair, count in sorted(pair_count.items(), key=lambda x: -x[1]):
            keys = list(pair)
            cluster = set(keys)
            for k in keys:
                cluster.add(k)
                if k in co_occurrence:
                    for partner, c in co_occurrence[k].items():
                        if c >= 2 and partner not in used_keys:
                            cluster.add(partner)

            if len(cluster) >= 2:
                overlap = cluster & used_keys
                if not overlap:
                    used_keys.update(cluster)
                    clusters.append(cluster)

        new_count = 0
        for cluster in clusters[:5]:
            # 查找对应的板块记录
            cluster_sectors: list[TrackedSector] = []
            for sector in eligible_sectors:
                if sector.status == "ignored":
                    continue
                sector_key = SectorIdentity.comparison_key(sector.canonical_name)
                if sector_key in cluster:
                    cluster_sectors.append(sector)

            if len(cluster_sectors) < 2:
                continue

            # 检查是否已有匹配的分组
            matched_existing = False
            for group in existing_groups:
                group_key = SectorIdentity.comparison_key(group.canonical_name)
                if group_key in cluster:
                    matched_existing = True
                    break
            if matched_existing:
                continue

            # 使用第一个板块名作为分组名候选
            suggested_name = cluster_sectors[0].canonical_name + "链"
            name_key = SectorIdentity.comparison_key(suggested_name)
            if name_key in pending_names:
                continue

            async with self.db.get_session() as session:
                suggestion = SectorGroupSuggestion(
                    suggestion_type="new_group",
                    suggested_group_name=suggested_name,
                    status="pending",
                    confidence=0.6,
                    reason=f"近{days}日共现分析发现{len(cluster_sectors)}个板块高频关联，建议创建新分组",
                )
                session.add(suggestion)
                await session.flush()
                await session.refresh(suggestion)

                for sector in cluster_sectors[:10]:
                    member = SectorGroupSuggestionMember(
                        suggestion_id=suggestion.id,
                        sector_id=sector.id,
                        suggested_relation_type="related",
                        confidence=0.5,
                        reason=f"共现聚类成员",
                    )
                    session.add(member)

                new_count += 1

        return {"new_groups": new_count}

    async def _collect_group_evidence(
        self,
        group_id: int,
        end_date: date,
        window_days: int,
    ) -> dict[str, Any]:
        """收集组级证据。"""
        async with self.db.get_session() as session:
            # 获取已确认成员
            result = await session.execute(
                select(SectorGroupMember, TrackedSector)
                .join(TrackedSector, SectorGroupMember.sector_id == TrackedSector.id)
                .where(SectorGroupMember.group_id == group_id)
            )
            members = result.all()

        evidence: dict[str, Any] = {
            "group_id": group_id,
            "end_date": end_date.isoformat(),
            "window_days": window_days,
            "member_summaries": [],
            "raw_evidence_count": 0,
        }

        for member, sector in members:
            # 获取成员最新的趋势报告
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(SectorTrendSummary)
                    .where(SectorTrendSummary.sector_id == sector.id)
                    .order_by(SectorTrendSummary.end_date.desc())
                    .limit(1)
                )
                summary = result.scalar_one_or_none()

            member_data: dict[str, Any] = {
                "sector_name": sector.canonical_name,
                "sector_status": sector.status,
                "relation_type": member.relation_type,
                "has_summary": summary is not None,
            }

            if summary:
                member_data["summary_date"] = summary.end_date.isoformat() if summary.end_date else None
                member_data["trend_status"] = summary.trend_status
                member_data["strength_level"] = summary.strength_level
                member_data["action_bias"] = summary.action_bias
                member_data["judgement"] = summary.judgement
                member_data["summary_content"] = summary.content

            evidence["member_summaries"].append(member_data)

        evidence["member_count"] = len(evidence["member_summaries"])

        return evidence

    async def _calculate_member_freshness(
        self,
        group_id: int,
        target_date: date,
        members: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """计算成员新鲜度。"""
        freshness = []
        for member in members:
            sector_id = member["sector_id"]
            sector_status = member.get("sector_status", "")

            # 获取最新报告日期
            async with self.db.get_session() as session:
                result = await session.execute(
                    select(sql_func.max(SectorTrendSummary.end_date)).where(
                        SectorTrendSummary.sector_id == sector_id
                    )
                )
                latest_date = result.scalar()

            is_candidate = sector_status == "candidate"
            is_stale = False
            is_missing = False

            if not is_candidate:
                if latest_date is None:
                    is_missing = True
                elif latest_date < target_date:
                    is_stale = True

            freshness.append({
                "sector_name": member["sector_name"],
                "sector_status": sector_status,
                "relation_type": member.get("relation_type", "related"),
                "is_candidate": is_candidate,
                "is_stale": is_stale,
                "is_missing": is_missing,
                "latest_summary_date": latest_date.isoformat() if latest_date else None,
                "target_date": target_date.isoformat(),
            })

        return freshness

    async def _sector_has_report(
        self,
        sector_id: int,
        target_date: date,
    ) -> bool:
        """检查板块是否有目标日期的报告。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(sql_func.count(SectorTrendSummary.id)).where(
                    SectorTrendSummary.sector_id == sector_id,
                    SectorTrendSummary.end_date == target_date,
                )
            )
            return (result.scalar() or 0) > 0

    async def _get_latest_group_summary(
        self,
        group_id: int,
    ) -> SectorGroupTrendSummary | None:
        """获取分组最新趋势报告。"""
        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroupTrendSummary)
                .where(SectorGroupTrendSummary.group_id == group_id)
                .order_by(SectorGroupTrendSummary.end_date.desc())
                .limit(1)
            )
            return result.scalar_one_or_none()

    async def _save_group_trend_summary(
        self,
        group_id: int,
        group_name: str,
        end_date: date,
        window_days: int,
        content: str,
        trend_status: str | None = None,
        strength_level: str | None = None,
        action_bias: str | None = None,
        judgement: str | None = None,
        evidence_json: str | None = None,
        member_freshness_json: str | None = None,
    ) -> SectorGroupTrendSummary:
        """保存分组趋势报告（文件 + 数据库）。"""
        from src.services.sector_trend_service import sector_to_path_name

        path_name = sector_to_path_name(group_name)
        output_path = GROUP_OUTPUT_DIR / path_name / f"{end_date}.md"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8")
        logger.info("分组趋势报告已保存: %s", output_path)

        async with self.db.get_session() as session:
            result = await session.execute(
                select(SectorGroupTrendSummary).where(
                    SectorGroupTrendSummary.group_id == group_id,
                    SectorGroupTrendSummary.end_date == end_date,
                )
            )
            summary = result.scalar_one_or_none()

            if summary:
                summary.content = content
                summary.trend_status = trend_status
                summary.strength_level = strength_level
                summary.action_bias = action_bias
                summary.judgement = judgement
                summary.evidence_json = evidence_json
                summary.member_freshness_json = member_freshness_json
                summary.output_path = str(output_path)
                summary.window_days = window_days
            else:
                summary = SectorGroupTrendSummary(
                    group_id=group_id,
                    group_name=group_name,
                    end_date=end_date,
                    window_days=window_days,
                    trend_status=trend_status,
                    strength_level=strength_level,
                    action_bias=action_bias,
                    judgement=judgement,
                    content=content,
                    evidence_json=evidence_json,
                    member_freshness_json=member_freshness_json,
                    output_path=str(output_path),
                )
                session.add(summary)

            await session.flush()
            await session.refresh(summary)

        return summary

    def _get_latest_trade_date(self) -> date:
        """获取最近交易日期。"""
        from src.services.market_analyzer import MarketAnalyzer
        analyzer = MarketAnalyzer(self.db)
        return analyzer.get_latest_trade_date()
