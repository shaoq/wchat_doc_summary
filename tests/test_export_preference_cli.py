"""批量导出偏好的订阅 CLI 展示测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

from click.testing import CliRunner
from rich.console import Console

from src.cli import main
from src.models.schema import Feed


def _feed(include_in_export_all: int = 1) -> Feed:
    feed = MagicMock(spec=Feed)
    feed.id = 1
    feed.mp_id = "biz:display"
    feed.name = "展示测试号"
    feed.intro = "简介"
    feed.status = 1
    feed.weight = 5
    feed.sync_time = None
    feed.created_at = None
    feed.include_in_export_all = include_in_export_all
    return feed


def test_ls_shows_batch_export_preference() -> None:
    """wchat ls 应显示批量导出列和值。"""
    feed = _feed(include_in_export_all=0)
    service = MagicMock()
    service.list_subscriptions_with_stats = AsyncMock(return_value=[(feed, 0, None)])

    session = MagicMock()
    session.execute = AsyncMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    db = MagicMock()
    db.get_session = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=session),
        __aexit__=AsyncMock(return_value=False),
    ))

    console = Console(width=160)

    with patch("src.cli.subscription.get_db", new=AsyncMock(return_value=db)), \
         patch("src.cli.subscription.console", console), \
         patch("src.cli.subscription.SubscriptionService", return_value=service):
        runner = CliRunner()
        result = runner.invoke(main, ["ls"])

    assert result.exit_code == 0
    assert "批量导出" in result.output
    assert "否" in result.output


def test_info_shows_batch_export_preference() -> None:
    """wchat info 应显示批量导出偏好。"""
    feed = _feed(include_in_export_all=1)
    service = MagicMock()
    service.get_subscription = AsyncMock(return_value=feed)

    call_count = 0

    async def _execute(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return MagicMock(scalar=MagicMock(return_value=0))
        return MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[]))))

    session = MagicMock()
    session.execute = _execute
    db = MagicMock()
    db.get_session = MagicMock(return_value=AsyncMock(
        __aenter__=AsyncMock(return_value=session),
        __aexit__=AsyncMock(return_value=False),
    ))

    with patch("src.cli.subscription.get_db", new=AsyncMock(return_value=db)), \
         patch("src.cli.subscription.SubscriptionService", return_value=service):
        runner = CliRunner()
        result = runner.invoke(main, ["info", "biz:display"])

    assert result.exit_code == 0
    assert "批量导出" in result.output
    assert "是" in result.output
