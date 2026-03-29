"""市场总结结构约束测试 - 校验固定章节、策略建议格式和降级行为。"""

import re
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.services.ai_processor import AIProcessor


def _make_processor() -> AIProcessor:
    """创建一个 mock AIProcessor 实例（不连接真实 API）。"""
    mock_db = MagicMock()
    with patch("src.services.ai_processor.AsyncAnthropic"):
        processor = AIProcessor(mock_db)
    # 替换 _call_api 为 mock，不真正调用 LLM
    processor._call_api = AsyncMock(return_value="")
    return processor


def _full_market_data() -> dict:
    """构造完整的市场数据。"""
    return {
        "indices": {
            "sh000001": {"name": "上证指数", "close": 3100.50, "change": 0.015},
            "sz399001": {"name": "深证成指", "close": 10200.30, "change": 0.012},
        },
        "volume": {"total_volume": "8500"},
        "statistics": {"up_count": 3200, "down_count": 1600, "flat_count": 200},
        "sectors": {
            "top_sectors": [
                {"name": "电力", "change": 0.035},
                {"name": "军工", "change": 0.028},
            ],
            "bottom_sectors": [
                {"name": "油气", "change": -0.015},
            ],
        },
        "limit_up": [
            {"name": "华电辽能", "code": "600739"},
            {"name": "长城军工", "code": "601606"},
        ],
    }


def _full_articles() -> list[dict]:
    """构造文章列表。"""
    return [
        {"title": "电力板块爆发分析", "summary": "电力板块全面爆发"},
    ]


def _full_telegraphs() -> list[dict]:
    """构造电报列表。"""
    return [
        {"publish_time": "2024-03-15 09:30", "title": "重要政策", "content": "政策内容"},
    ]


def _full_watch_items() -> list[dict]:
    """构造看盘数据。"""
    return [
        {
            "publish_time": "2024-03-15 10:00",
            "title": "电力拉升",
            "content": "电力板块盘中拉升",
            "stocks": ["华电辽能"],
            "sectors": ["电力"],
        },
    ]


class TestMarketSummaryFixedSections:
    """测试市场总结包含固定章节结构。"""

    def test_template_contains_all_fixed_sections(self) -> None:
        """模板应包含所有固定章节标题。"""
        from pathlib import Path

        template = (Path("templates/market_summary.md")).read_text(encoding="utf-8")

        required_sections = [
            "市场概览",
            "主线与轮动",
            "个股与情绪",
            "关键信息催化",
            "明日观察清单",
            "后续策略建议与风险提示",
        ]

        for section in required_sections:
            assert section in template, f"模板缺少固定章节: {section}"

    def test_template_contains_strategy_format(self) -> None:
        """模板应包含策略建议的三要素格式要求。"""
        from pathlib import Path

        template = (Path("templates/market_summary.md")).read_text(encoding="utf-8")

        required_format_elements = ["依据", "应对", "风险"]
        for element in required_format_elements:
            assert element in template, f"模板缺少策略格式要素: {element}"

    def test_template_contains_strategy_dimensions(self) -> None:
        """模板应明确后续策略至少覆盖三个核心视角。"""
        from pathlib import Path

        template = (Path("templates/market_summary.md")).read_text(encoding="utf-8")

        required_dimensions = [
            "主线与板块策略",
            "个股与情绪策略",
            "关键消息与事件策略",
        ]

        for dimension in required_dimensions:
            assert dimension in template, f"模板缺少策略维度约束: {dimension}"

    def test_template_contains_strategy_count_and_downgrade_rules(self) -> None:
        """模板应约束策略条数和分维度降级写法。"""
        from pathlib import Path

        template = (Path("templates/market_summary.md")).read_text(encoding="utf-8")

        assert "至少输出 3 条策略" in template
        assert "暂不下判断" in template or "等待验证" in template

    def test_template_contains_downgrade_constraint(self) -> None:
        """模板应包含数据不足时的降级约束。"""
        from pathlib import Path

        template = (Path("templates/market_summary.md")).read_text(encoding="utf-8")

        assert "观察模式" in template
        assert "数据缺口" in template or "数据不足" in template

    def test_template_contains_data_gaps_placeholder(self) -> None:
        """模板应包含 {data_gaps} 占位符。"""
        from pathlib import Path

        template = (Path("templates/market_summary.md")).read_text(encoding="utf-8")
        assert "{data_gaps}" in template


class TestBuildDataGaps:
    """测试 _build_data_gaps 方法的数据缺口检测。"""

    def _invoke_build_data_gaps(self, **overrides) -> str:
        """调用 _build_data_gaps 方法。"""
        processor = _make_processor()
        defaults = {
            "indices": {"sh000001": {"name": "上证", "close": 3100, "change": 0.01}},
            "volume": {"total_volume": "8500"},
            "stats": {"up_count": 100, "down_count": 50, "flat_count": 10},
            "top_sectors": [{"name": "电力", "change": 0.03}],
            "bottom_sectors": [{"name": "油气", "change": -0.01}],
            "limit_up": [{"name": "测试股", "code": "000001"}],
            "telegraphs": [{"title": "新闻"}],
            "watch_items": [{"title": "看盘"}],
            "articles": [{"title": "文章"}],
        }
        defaults.update(overrides)
        return processor._build_data_gaps(**defaults)

    def test_no_gaps_when_all_data_present(self) -> None:
        """所有数据完整时，应返回'无'。"""
        result = self._invoke_build_data_gaps()
        assert result == "无"

    def test_detects_missing_indices(self) -> None:
        """缺失指数数据时，应列出缺口。"""
        result = self._invoke_build_data_gaps(indices={})
        assert "指数" in result

    def test_detects_missing_volume(self) -> None:
        """缺失成交额时，应列出缺口。"""
        result = self._invoke_build_data_gaps(volume=None)
        assert "成交额" in result

    def test_detects_missing_sectors(self) -> None:
        """缺失板块数据时，应列出缺口。"""
        result = self._invoke_build_data_gaps(top_sectors=[], bottom_sectors=[])
        assert "板块" in result

    def test_detects_missing_limit_up(self) -> None:
        """缺失涨停数据时，应列出缺口。"""
        result = self._invoke_build_data_gaps(limit_up=[])
        assert "涨停" in result

    def test_detects_missing_telegraphs(self) -> None:
        """缺失电报数据时，应列出缺口。"""
        result = self._invoke_build_data_gaps(telegraphs=None)
        assert "电报" in result

    def test_detects_multiple_gaps(self) -> None:
        """多项数据缺失时，应列出所有缺口。"""
        result = self._invoke_build_data_gaps(
            indices={}, top_sectors=[], bottom_sectors=[], limit_up=[], telegraphs=None
        )
        assert "指数" in result
        assert "板块" in result
        assert "涨停" in result
        assert "电报" in result

    def test_gaps_include_warning_prefix(self) -> None:
        """缺口提示应包含警告前缀。"""
        result = self._invoke_build_data_gaps(indices={})
        assert "⚠️" in result or "不足" in result


class TestGenerateMarketSummaryPromptStructure:
    """测试 generate_market_summary 生成的 prompt 包含证据组结构。"""

    @pytest.mark.asyncio
    async def test_prompt_contains_evidence_groups(self) -> None:
        """生成的 prompt 应包含显式证据组标题。"""
        processor = _make_processor()

        # 捕获传给 _call_api 的实际 prompt
        captured_prompt = ""
        call_count = 0

        async def capture_prompt(prompt: str, max_tokens: int = 1500) -> str:
            nonlocal captured_prompt, call_count
            call_count += 1
            if call_count == 1:
                captured_prompt = prompt
            return "mock summary"

        processor._call_api = capture_prompt

        await processor.generate_market_summary(
            trade_date="2024-03-15",
            market_data=_full_market_data(),
            articles=_full_articles(),
            telegraphs=_full_telegraphs(),
            watch_items=_full_watch_items(),
        )

        evidence_groups = [
            "证据组一：行情总览",
            "证据组二：板块信号",
            "证据组三：涨停与龙头线索",
            "证据组四：财联社电报关键催化",
            "证据组五：盘中轮动线索",
            "证据组六：文章观点补充",
            "数据缺口提示",
        ]

        for group in evidence_groups:
            assert group in captured_prompt, f"Prompt 缺少证据组: {group}"

    @pytest.mark.asyncio
    async def test_prompt_contains_fixed_output_sections(self) -> None:
        """生成的 prompt 应包含固定输出章节标题。"""
        processor = _make_processor()
        captured_prompt = ""
        captured_max_tokens = 0
        call_count = 0

        async def capture_prompt(prompt: str, max_tokens: int = 1500) -> str:
            nonlocal captured_prompt, captured_max_tokens, call_count
            call_count += 1
            if call_count == 1:
                captured_prompt = prompt
                captured_max_tokens = max_tokens
            return "mock summary"

        processor._call_api = capture_prompt

        await processor.generate_market_summary(
            trade_date="2024-03-15",
            market_data=_full_market_data(),
            articles=_full_articles(),
            telegraphs=_full_telegraphs(),
            watch_items=_full_watch_items(),
        )

        output_sections = [
            "一、市场概览",
            "二、主线与轮动",
            "三、个股与情绪",
            "四、关键信息催化",
            "五、明日观察清单",
            "六、后续策略建议与风险提示",
        ]

        for section in output_sections:
            assert section in captured_prompt, f"Prompt 缺少输出章节: {section}"
        assert captured_max_tokens >= 2000

    @pytest.mark.asyncio
    async def test_prompt_shows_no_gaps_when_data_complete(self) -> None:
        """数据完整时，data_gaps 区域应为'无'。"""
        processor = _make_processor()
        captured_prompt = ""
        call_count = 0

        async def capture_prompt(prompt: str, max_tokens: int = 1500) -> str:
            nonlocal captured_prompt, call_count
            call_count += 1
            if call_count == 1:
                captured_prompt = prompt
            return "mock summary"

        processor._call_api = capture_prompt

        await processor.generate_market_summary(
            trade_date="2024-03-15",
            market_data=_full_market_data(),
            articles=_full_articles(),
            telegraphs=_full_telegraphs(),
            watch_items=_full_watch_items(),
        )

        assert "数据缺口提示\n无" in captured_prompt

    @pytest.mark.asyncio
    async def test_prompt_shows_gaps_when_data_missing(self) -> None:
        """数据缺失时，data_gaps 区域应列出缺口。"""
        processor = _make_processor()
        captured_prompt = ""
        call_count = 0

        async def capture_prompt(prompt: str, max_tokens: int = 1500) -> str:
            nonlocal captured_prompt, call_count
            call_count += 1
            if call_count == 1:
                captured_prompt = prompt
            return "mock summary"

        processor._call_api = capture_prompt

        # 空数据
        empty_market_data = {
            "indices": {},
            "volume": {},
            "statistics": {},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
        }

        await processor.generate_market_summary(
            trade_date="2024-03-15",
            market_data=empty_market_data,
            articles=[],
            telegraphs=None,
            watch_items=None,
        )

        assert "⚠️" in captured_prompt
        assert "观察模式" in captured_prompt


class TestDataSparseDowngrade:
    """测试数据不足时的降级行为。"""

    @pytest.mark.asyncio
    async def test_sparse_data_triggers_observation_mode_in_prompt(self) -> None:
        """数据稀疏时，prompt 中应包含观察模式指令。"""
        processor = _make_processor()
        captured_prompt = ""
        call_count = 0

        async def capture_prompt(prompt: str, max_tokens: int = 1500) -> str:
            nonlocal captured_prompt, call_count
            call_count += 1
            if call_count == 1:
                captured_prompt = prompt
            return "mock summary"

        processor._call_api = capture_prompt

        sparse_data = {
            "indices": {},
            "volume": {},
            "statistics": {},
            "sectors": {"top_sectors": [], "bottom_sectors": []},
            "limit_up": [],
        }

        await processor.generate_market_summary(
            trade_date="2024-03-15",
            market_data=sparse_data,
            articles=[],
        )

        # 验证 prompt 中的降级约束
        assert "观察模式" in captured_prompt
        assert "强方向性" in captured_prompt or "方向性判断" in captured_prompt

    @pytest.mark.asyncio
    async def test_downgrade_instructions_in_template(self) -> None:
        """模板应包含降级约束说明。"""
        from pathlib import Path

        template = Path("templates/market_summary.md").read_text(encoding="utf-8")
        assert "观察模式" in template
        assert "数据不足" in template or "关键数据缺失" in template


class TestStrategyEnhancement:
    """测试第六节策略增强逻辑。"""

    @pytest.mark.asyncio
    async def test_generate_market_summary_enhances_simple_strategy_section(self) -> None:
        """当第六节过于简单时，应触发二次增强并替换。"""
        processor = _make_processor()
        prompts: list[tuple[str, int]] = []

        initial_summary = """## 一、市场概览
市场整体震荡。

## 二、主线与轮动
电力和军工活跃。

## 三、个股与情绪
情绪一般。

## 四、关键信息催化
有政策消息催化。

## 五、明日观察清单
- 电力

## 六、后续策略建议与风险提示
继续关注热点和龙头表现，注意风险。"""

        enhanced_strategy = """## 六、后续策略建议与风险提示
### 6.1 主线与板块策略
- **观察/策略**: 看多电力主线的回流机会
  - **依据**: 电力位列涨幅榜前列，盘中看盘多次提及电力拉升，华电辽能进入涨停样本。
  - **应对**: 若次日竞价后电力核心股继续强于指数并带动板块扩散，可沿主线核心先观察再择机跟随。
  - **风险**: 若高开低走且板块无跟风涨停扩散，则说明回流强度不足。
- **观察/策略**: 观察军工是否由日内脉冲转为持续轮动
  - **依据**: 军工位于强势板块名单，长城军工进入涨停样本。
  - **应对**: 只有在次日军工继续出现核心股强化和板块联动时，才考虑从观察转向跟踪。
  - **风险**: 若仅龙头单点异动、跟风不足，则更像题材脉冲而非主线。

### 6.2 个股与情绪策略
- **观察/策略**: 观察高标与涨停溢价，判断情绪是否支持接力
  - **依据**: 涨停样本集中在电力、军工，盘中看盘存在板块联动线索。
  - **应对**: 若高标次日承接稳定、炸板率下降，可视为情绪修复；否则继续谨慎。
  - **风险**: 若高标快速走弱并拖累补涨股，则情绪可能重新转入分歧。

### 6.3 关键消息与事件策略
- **观察/策略**: 观察政策消息能否继续发酵到板块层面
  - **依据**: 财联社电报存在“重要政策”标题，文章也聚焦电力板块爆发分析。
  - **应对**: 若次日早盘消息进一步扩散到板块和个股共振，可提升跟踪优先级。
  - **风险**: 若消息无新增增量、相关板块冲高回落，则按日内刺激处理。"""

        async def call_api(prompt: str, max_tokens: int = 1500) -> str:
            prompts.append((prompt, max_tokens))
            return initial_summary if len(prompts) == 1 else enhanced_strategy

        processor._call_api = call_api

        summary = await processor.generate_market_summary(
            trade_date="2024-03-15",
            market_data=_full_market_data(),
            articles=_full_articles(),
            telegraphs=_full_telegraphs(),
            watch_items=_full_watch_items(),
        )

        assert len(prompts) == 2
        assert prompts[0][1] >= 2000
        assert prompts[1][1] >= 1000
        assert "你正在补写并强化一份 A 股市场总结的最后一节" in prompts[1][0]
        assert "### 6.1 主线与板块策略" in summary
        assert "### 6.2 个股与情绪策略" in summary
        assert "### 6.3 关键消息与事件策略" in summary
        assert "继续关注热点和龙头表现" not in summary

    @pytest.mark.asyncio
    async def test_generate_market_summary_skips_enhancement_when_strategy_is_complete(self) -> None:
        """第六节已完整时，不应重复触发增强。"""
        processor = _make_processor()
        prompts: list[tuple[str, int]] = []

        complete_summary = """## 一、市场概览
市场整体震荡。

## 二、主线与轮动
电力和军工活跃。

## 三、个股与情绪
情绪一般。

## 四、关键信息催化
有政策消息催化。

## 五、明日观察清单
- 电力

## 六、后续策略建议与风险提示
### 6.1 主线与板块策略
- **观察/策略**: 看多电力主线的回流机会
  - **依据**: 电力位列涨幅榜前列，华电辽能进入涨停样本。
  - **应对**: 若次日核心股继续强于指数并带动扩散，则继续跟踪。
  - **风险**: 若高开低走且无扩散，则回流失败。
- **观察/策略**: 观察军工分歧后的承接
  - **依据**: 军工位于强势板块名单，长城军工进入涨停样本。
  - **应对**: 只有板块继续强化时才考虑跟踪。
  - **风险**: 若仅单点异动，则按脉冲处理。

### 6.2 个股与情绪策略
- **观察/策略**: 观察高标溢价和炸板反馈
  - **依据**: 涨停样本集中在电力、军工，盘中看盘存在联动线索。
  - **应对**: 若高标承接稳定、炸板率下降，可视为情绪修复。
  - **风险**: 若高标快速转弱，则接力难度提升。

### 6.3 关键消息与事件策略
- **观察/策略**: 观察政策催化能否继续发酵
  - **依据**: 财联社电报存在“重要政策”标题，文章聚焦电力板块。
  - **应对**: 若次日早盘继续有增量消息，可提升优先级。
  - **风险**: 若无新增增量，则仅按日内刺激处理。"""

        async def call_api(prompt: str, max_tokens: int = 1500) -> str:
            prompts.append((prompt, max_tokens))
            return complete_summary

        processor._call_api = call_api

        summary = await processor.generate_market_summary(
            trade_date="2024-03-15",
            market_data=_full_market_data(),
            articles=_full_articles(),
            telegraphs=_full_telegraphs(),
            watch_items=_full_watch_items(),
        )

        assert len(prompts) == 1
        assert summary == complete_summary
