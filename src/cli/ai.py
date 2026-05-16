"""AI 命令模块 - ai 命令组及其子命令。"""

import json
import time
from datetime import date as date_type
from pathlib import Path
from typing import Any

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn
from rich.table import Table

from src.api.finance import FinanceClient
from src.cli.utils import (
    console,
    format_articles_summary,
    format_elapsed_time,
    format_market_data_summary,
    run_async,
)
from src.models.schema import Article
from src.services.ai_processor import AIProcessor
from src.services.market_analyzer import MarketAnalyzer
from src.services.subscription import SubscriptionService
from src.storage.database import get_db


# ---------------------------------------------------------------------------
# market-summary 阶段渲染辅助
# ---------------------------------------------------------------------------

def _stage_header(index: int, total: int, label: str, *, suffix: str = "") -> str:
    """返回阶段头标记，如 '[1/3] 获取市场数据'。"""
    text = f"[{index}/{total}] {label}"
    if suffix:
        text += f" {suffix}"
    return text


def _stage_conclusion(ok: bool, message: str) -> None:
    """输出阶段结论行。"""
    icon = "[green]v[/green]" if ok else "[red]x[/red]"
    console.print(f"  {icon} {message}")


def _stage_detail(message: str) -> None:
    """输出阶段细项摘要行。"""
    console.print(f"      {message}")


def _format_volume_amount(total_volume: float | int | None) -> str:
    """格式化成交额显示。"""
    total = float(total_volume or 0)
    if total >= 10000:
        return f"{total / 10000:.1f}万亿"
    return f"{total:.0f}亿"


def _source_icon(status: str) -> str:
    """根据来源状态返回对应图标。"""
    if status == "ok":
        return "[green]v[/green]"
    if status == "near-complete":
        return "[green]v[/green]"
    if status == "partial":
        return "[yellow]~[/yellow]"
    if status == "empty":
        return "[yellow]o[/yellow]"
    return "[red]x[/red]"


def _status_detail(
    label: str,
    status: str,
    *,
    ok_message: str,
    empty_message: str,
    error_message: str = "获取失败",
) -> None:
    """输出带状态图标的细项行。"""
    if status in ("ok", "near-complete", "partial"):
        message = ok_message
    elif status == "empty":
        message = empty_message
    else:
        message = error_message
    _stage_detail(f"{_source_icon(status)} {label}: {message}")


def _make_status_item(
    label: str,
    status: str,
    *,
    ok_message: str,
    empty_message: str,
    error_message: str = "获取失败",
    summary: str | None = None,
) -> dict[str, str]:
    """构建统一的状态项描述。"""
    if status in ("ok", "near-complete", "partial"):
        message = ok_message
    elif status == "empty":
        message = empty_message
    else:
        message = error_message
    return {
        "label": label,
        "status": status,
        "message": message,
        "summary": summary or message,
    }


def _get_market_data_status_items(market_data: dict[str, Any]) -> list[dict[str, str]]:
    """汇总市场数据逐项状态。"""
    items: list[dict[str, str]] = []
    breadth_quality = market_data.get("breadth_quality", {})

    indices = market_data.get("indices")
    index_count = 0
    if isinstance(indices, dict):
        index_count = sum(
            1 for key in ("sh", "sz", "cy")
            if isinstance(indices.get(key), dict) and indices.get(key)
        )
    items.append(_make_status_item(
        "指数",
        "ok" if index_count > 0 else "error",
        ok_message=f"已获取 {index_count} 个指数",
        empty_message="暂无指数数据",
        summary=f"{index_count} 个指数",
    ))

    volume = market_data.get("volume")
    volume_quality = breadth_quality.get("volume")
    if volume_quality and volume_quality.get("status") in ("ok", "partial", "error"):
        volume_status = volume_quality["status"]
        volume_total = _format_volume_amount(volume.get("total_volume") if isinstance(volume, dict) else None)
        if volume_status == "ok":
            volume_msg = f"已获取 {volume_total}"
        elif volume_status == "partial":
            actual = volume_quality.get("actual_count", 0)
            expected = volume_quality.get("expected_count", 0)
            volume_msg = f"样本不完整 ({actual}/{expected})"
        else:
            volume_msg = "获取失败"
    else:
        # 无 breadth_quality（如缓存数据），回退到旧逻辑
        volume_ok = isinstance(volume, dict) and all(
            key in volume for key in ("sh_volume", "sz_volume", "total_volume")
        )
        volume_status = "ok" if volume_ok else "error"
        volume_total = _format_volume_amount(volume.get("total_volume")) if volume_ok else "0亿"
        volume_msg = f"已获取 {volume_total}" if volume_ok else "获取失败"
    items.append(_make_status_item(
        "成交额",
        volume_status,
        ok_message=volume_msg,
        empty_message="暂无成交额数据",
        summary=volume_msg,
    ))

    statistics = market_data.get("statistics")
    stats_quality = breadth_quality.get("statistics")
    statistics_summary = (
        f"{statistics.get('up_count', 0)}/"
        f"{statistics.get('down_count', 0)}/"
        f"{statistics.get('flat_count', 0)}"
    ) if isinstance(statistics, dict) else "0/0/0"
    if stats_quality and stats_quality.get("status") in ("ok", "near-complete", "partial", "error"):
        stats_status = stats_quality["status"]
        if stats_status == "ok":
            stats_msg = f"已获取 {statistics_summary}"
        elif stats_status == "near-complete":
            actual = stats_quality.get("actual_count", 0)
            expected = stats_quality.get("expected_count", 0)
            stats_msg = f"近完整 ({actual}/{expected}) {statistics_summary}"
        elif stats_status == "partial":
            actual = stats_quality.get("actual_count", 0)
            expected = stats_quality.get("expected_count", 0)
            stats_msg = f"样本不完整 ({actual}/{expected})"
        else:
            stats_msg = "获取失败"
    else:
        stats_ok = isinstance(statistics, dict) and all(
            key in statistics for key in ("up_count", "down_count", "flat_count")
        )
        stats_status = "ok" if stats_ok else "error"
        stats_msg = f"已获取 {statistics_summary}" if stats_ok else "获取失败"
    items.append(_make_status_item(
        "涨跌统计",
        stats_status,
        ok_message=stats_msg,
        empty_message="暂无涨跌统计数据",
        summary=stats_msg,
    ))

    sectors = market_data.get("sectors")
    sector_status = "error"
    sector_count = 0
    if isinstance(sectors, dict) and all(
        key in sectors for key in ("top_sectors", "bottom_sectors")
    ):
        top_sectors = sectors.get("top_sectors") or []
        bottom_sectors = sectors.get("bottom_sectors") or []
        sector_count = len(top_sectors) + len(bottom_sectors)
        sector_status = "ok" if sector_count > 0 else "empty"
    items.append(_make_status_item(
        "板块",
        sector_status,
        ok_message=f"已获取 {sector_count} 个板块",
        empty_message="暂无板块数据",
        summary=f"{sector_count} 个板块",
    ))

    limit_up = market_data.get("limit_up")
    limit_up_quality = market_data.get("limit_up_quality", {})
    limit_up_status = "error"
    limit_up_count = 0
    if isinstance(limit_up, list):
        limit_up_count = len(limit_up)
        limit_up_status = "ok" if limit_up_count > 0 else "empty"
    source_type = limit_up_quality.get("source_type", "")
    limit_up_suffix = ""
    if source_type == "approximate_candidates":
        limit_up_suffix = " (近似候选)"
    items.append(_make_status_item(
        "涨停股",
        limit_up_status,
        ok_message=f"已获取 {limit_up_count} 只{limit_up_suffix}",
        empty_message="0 只",
        summary=f"{limit_up_count} 只{limit_up_suffix}",
    ))

    return items


def _format_pct(value: Any) -> str:
    try:
        return f"{float(value) * 100:+.2f}%"
    except (TypeError, ValueError):
        return "N/A"


def _get_global_context_status_item(market_data: dict[str, Any]) -> dict[str, str]:
    """汇总海外市场上下文状态。"""
    context = market_data.get("global_market_context")
    if not isinstance(context, dict):
        return _make_status_item(
            "海外市场",
            "empty",
            ok_message="",
            empty_message="暂无海外市场上下文",
            summary="暂无海外市场上下文",
        )

    status = str(context.get("status", "error"))
    us_market = context.get("us_market", {}) if isinstance(context.get("us_market"), dict) else {}
    session = context.get("session") or us_market.get("session") or "-"
    as_of = context.get("as_of") or us_market.get("as_of") or "-"
    source = context.get("source") or us_market.get("source") or "-"
    degraded = context.get("degraded", False)
    indices = us_market.get("indices", []) if isinstance(us_market.get("indices"), list) else []
    index_summary = ", ".join(
        f"{item.get('symbol', item.get('name', ''))} {_format_pct(item.get('change_pct'))}"
        for item in indices[:3]
        if isinstance(item, dict)
    )
    if not index_summary:
        index_summary = context.get("message") or "暂无指数信号"

    # 构建 fallback 状态后缀
    fallback_suffix = ""
    source_attempts = context.get("source_attempts", [])
    if degraded:
        fallback_suffix = " (fallback)"
    elif status == "error" and source_attempts:
        # 提取最终失败类型
        last_attempt = source_attempts[-1] if source_attempts else {}
        failure_type = last_attempt.get("failure_type", "")
        if failure_type == "unauthorized":
            fallback_suffix = " (上游拒绝访问)"
        elif failure_type == "rate_limited":
            fallback_suffix = " (上游限流)"

    message = f"{index_summary} | session={session} | as_of={as_of}{fallback_suffix}"
    return _make_status_item(
        "海外市场",
        status if status in ("ok", "partial", "error") else "error",
        ok_message=message,
        empty_message="暂无海外市场上下文",
        error_message=context.get("message", "获取失败") + fallback_suffix,
        summary=message,
    )


def _render_market_data_statuses(market_data: dict[str, Any]) -> None:
    """输出市场数据逐项获取状态。"""
    for item in _get_market_data_status_items(market_data) + [_get_global_context_status_item(market_data)]:
        _status_detail(
            item["label"],
            item["status"],
            ok_message=item["message"] if item["status"] in ("ok", "near-complete", "partial") else "",
            empty_message=item["message"] if item["status"] == "empty" else "",
            error_message=item["message"] if item["status"] == "error" else "获取失败",
        )


def _get_news_status_items(news_data: dict[str, Any]) -> list[dict[str, str]]:
    """汇总新闻来源逐项状态。"""
    sources_status = news_data.get("sources_status", {})
    source_details = news_data.get("source_details", {})
    telegraphs_count = len(news_data.get("telegraphs", []))
    watch_count = len(news_data.get("watch_items", []))
    articles_count = len(news_data.get("articles", []))
    telegraph_detail = source_details.get("telegraphs", {}) if isinstance(source_details, dict) else {}
    watch_detail = source_details.get("watch_items", {}) if isinstance(source_details, dict) else {}
    article_detail = source_details.get("articles", {}) if isinstance(source_details, dict) else {}

    return [
        _make_status_item(
            "财联社电报",
            sources_status.get("telegraphs", "empty"),
            ok_message=telegraph_detail.get("message", f"已获取 {telegraphs_count} 条"),
            empty_message=telegraph_detail.get("message", "0 条"),
            error_message=telegraph_detail.get("message", "获取失败"),
            summary=f"{telegraphs_count} 条",
        ),
        _make_status_item(
            "看盘数据",
            sources_status.get("watch_items", "empty"),
            ok_message=watch_detail.get("message", f"已获取 {watch_count} 条"),
            empty_message=watch_detail.get("message", "0 条"),
            error_message=watch_detail.get("message", "获取失败"),
            summary=f"{watch_count} 条",
        ),
        _make_status_item(
            "相关文章",
            sources_status.get("articles", "empty"),
            ok_message=article_detail.get("message", f"已获取 {articles_count} 篇"),
            empty_message=article_detail.get("message", "0 篇"),
            error_message=article_detail.get("message", "获取失败"),
            summary=f"{articles_count} 篇",
        ),
    ]


def _render_pre_generation_summary(market_data: dict[str, Any], news_data: dict[str, Any]) -> None:
    """在生成报告前输出 AI 输入数据清单。"""
    console.print("[bold cyan][预检] AI 输入数据清单[/bold cyan]")
    items = (
        _get_market_data_status_items(market_data)
        + [_get_global_context_status_item(market_data)]
        + _get_news_status_items(news_data)
    )
    for item in items:
        _status_detail(
            item["label"],
            item["status"],
            ok_message=item["message"] if item["status"] in ("ok", "near-complete", "partial") else "",
            empty_message=item["message"] if item["status"] == "empty" else "",
            error_message=item["message"] if item["status"] == "error" else "获取失败",
        )
    console.print()


def _data_source_label(data_source: str) -> str:
    """将 data_source 值转为可读标签。"""
    labels = {
        "api": "API 实时数据",
        "cache": "缓存数据",
        "none": "无数据",
        "error": "获取失败",
    }
    return labels.get(data_source, data_source)


def _breadth_source_outcome_label(market_data: dict[str, Any]) -> str | None:
    """汇总宽度数据来源结果，突出官方成交额、pytdx、成交额旧链路兜底和降级空值。"""
    breadth_quality = market_data.get("breadth_quality", {})
    volume_quality = breadth_quality.get("volume", {})
    stats_quality = breadth_quality.get("statistics", {})
    if not volume_quality or not stats_quality:
        return None

    volume_status = str(volume_quality.get("status", ""))
    stats_status = str(stats_quality.get("status", ""))
    volume_source = str(volume_quality.get("source", ""))
    stats_source = str(stats_quality.get("source", ""))

    if volume_status == "error" and stats_status == "error":
        return "降级为空值"

    if volume_status == "ok" and stats_status == "ok":
        if volume_source == "official_exchange_turnover" and stats_source == "pytdx_quotes":
            return "官方成交额 + pytdx 统计"
        if volume_source == "akshare_spot_em" and stats_source == "pytdx_quotes":
            return "成交额旧链路兜底 + pytdx 统计"

    fallback_parts = []
    if volume_status == "ok":
        if volume_source == "official_exchange_turnover":
            fallback_parts.append("官方成交额")
        elif volume_source == "akshare_spot_em":
            fallback_parts.append("成交额旧链路兜底")
    if stats_status in ("ok", "near-complete"):
        if stats_source == "pytdx_quotes":
            label = "pytdx 统计" if stats_status == "ok" else "pytdx 统计(近完整)"
            fallback_parts.append(label)
    if fallback_parts:
        return " + ".join(fallback_parts)

    return None


@click.group()
def ai() -> None:
    """AI 处理命令。"""
    pass


@ai.command()
@click.argument('article_id', type=int)
@click.option('--max-length', type=int, default=200, help='摘要最大字数')
def summarize(article_id: int, max_length: int) -> None:
    """生成文章摘要。

    ARTICLE_ID: 文章 ID
    """
    async def _summarize() -> None:
        db = await get_db()
        processor = AIProcessor(db)

        with console.status("[bold blue]生成摘要中...[/bold blue]"):
            try:
                summary = await processor.summarize(article_id, max_length)
            except ValueError as e:
                console.print(f"[red]错误: {e}[/red]")
                return
            except Exception as e:
                console.print(f"[red]生成摘要失败: {e}[/red]")
                return

        console.print(Panel(
            summary,
            title=f"[green]文章 {article_id} 摘要[/green]",
            border_style="green",
        ))

    run_async(_summarize())


@ai.command()
@click.argument('article_id', type=int)
@click.option('--max-keywords', type=int, default=10, help='最大关键词数量')
def keywords(article_id: int, max_keywords: int) -> None:
    """提取文章关键词。

    ARTICLE_ID: 文章 ID
    """
    async def _keywords() -> None:
        db = await get_db()
        processor = AIProcessor(db)

        with console.status("[bold blue]提取关键词中...[/bold blue]"):
            try:
                keywords_list = await processor.extract_keywords(article_id, max_keywords)
            except ValueError as e:
                console.print(f"[red]错误: {e}[/red]")
                return
            except Exception as e:
                console.print(f"[red]提取关键词失败: {e}[/red]")
                return

        console.print(Panel(
            ", ".join(keywords_list),
            title=f"[green]文章 {article_id} 关键词[/green]",
            border_style="green",
        ))

    run_async(_keywords())


@ai.command()
@click.argument('article_id', type=int)
def classify(article_id: int) -> None:
    """智能分类文章。

    ARTICLE_ID: 文章 ID
    """
    async def _classify() -> None:
        db = await get_db()
        processor = AIProcessor(db)

        with console.status("[bold blue]分类中...[/bold blue]"):
            try:
                category = await processor.classify(article_id)
            except ValueError as e:
                console.print(f"[red]错误: {e}[/red]")
                return
            except Exception as e:
                console.print(f"[red]分类失败: {e}[/red]")
                return

        console.print(f"[green]文章 {article_id} 分类:[/green] [bold]{category}[/bold]")

    run_async(_classify())


@ai.command()
@click.argument('article_id', type=int)
def sentiment(article_id: int) -> None:
    """情感分析。

    ARTICLE_ID: 文章 ID
    """
    async def _sentiment() -> None:
        db = await get_db()
        processor = AIProcessor(db)

        with console.status("[bold blue]情感分析中...[/bold blue]"):
            try:
                sentiment_result = await processor.analyze_sentiment(article_id)
            except ValueError as e:
                console.print(f"[red]错误: {e}[/red]")
                return
            except Exception as e:
                console.print(f"[red]情感分析失败: {e}[/red]")
                return

        # 情感标签映射
        sentiment_map = {
            "positive": ("正面", "green"),
            "negative": ("负面", "red"),
            "neutral": ("中立", "yellow"),
        }
        label, color = sentiment_map.get(sentiment_result, ("未知", "dim"))

        console.print(f"[green]文章 {article_id} 情感分析:[/green] [{color}]{label}[/{color}]")

    run_async(_sentiment())


@ai.command()
@click.option('--mp-id', 'mp_id', help='指定公众号 ID（可选）')
@click.option('--batch-size', type=int, default=10, help='批量处理数量')
def batch_summarize(mp_id: str | None, batch_size: int) -> None:
    """批量生成摘要。"""
    async def _batch_summarize() -> None:
        db = await get_db()
        processor = AIProcessor(db)

        from sqlalchemy import select
        from src.models.schema import Article, Feed

        # 获取未生成摘要的文章
        async with db.get_session() as session:
            query = select(Article).where(Article.summary.is_(None))

            if mp_id:
                query = query.join(Feed).where(Feed.mp_id == mp_id)

            query = query.limit(batch_size)
            result = await session.execute(query)
            articles = list(result.scalars().all())

        if not articles:
            console.print("[yellow]没有需要处理的文章[/yellow]")
            return

        article_ids = [a.id for a in articles]
        console.print(f"[blue]开始处理 {len(article_ids)} 篇文章...[/blue]")

        results = await processor.batch_summarize(article_ids)

        success_count = len(results)
        console.print(f"[green]处理完成，成功: {success_count}/{len(article_ids)}[/green]")

    run_async(_batch_summarize())


@ai.command()
@click.argument('mp_id')
@click.option('--output', '-o', 'output_file', type=click.Path(), default=None, help='输出文件路径（默认: output/extract_stocks/{mp_id}_stocks_{YYMMDD}.txt）')
@click.option('--force', is_flag=False, flag_value=True, default=False, help='强制重新处理已处理的文章')
@click.option('--simple-info', is_flag=True, default=False, help='额外输出简化格式的股票列表文件')
def extract_stocks(mp_id: str, output_file: str | None, force: bool, simple_info: bool) -> None:
    """提取公众号文章中的股票信息。

    MP_ID: 公众号 ID
    """
    from datetime import datetime

    # 默认输出路径
    if output_file is None:
        today = datetime.now().strftime("%y%m%d")
        output_file = f"output/extract_stocks/{mp_id}_stocks_{today}.txt"

    async def _extract_stocks() -> None:
        db = await get_db()
        processor = AIProcessor(db)
        subscription_service = SubscriptionService(db)

        # 验证订阅存在
        feed = await subscription_service.get_subscription(mp_id)
        if not feed:
            console.print(f"[red]订阅不存在: {mp_id}[/red]")
            return

        from sqlalchemy import func as sql_func, select

        async with db.get_session() as session:
            # 获取文章总数
            count_result = await session.execute(
                select(sql_func.count(Article.id)).where(Article.feed_id == feed.id)
            )
            total = count_result.scalar() or 0

            if total == 0:
                console.print(f"[yellow]该公众号暂无已抓取的文章[/yellow]")
                return

            # 查询所有文章
            query = (
                select(Article)
                .where(Article.feed_id == feed.id)
                .order_by(Article.publish_time.desc())
            )
            result = await session.execute(query)
            articles = list(result.scalars().all())

        console.print(f"[cyan]公众号: {feed.name}[/cyan]")
        console.print(f"[blue]文章总数: {total}[/blue]")

        if force:
            console.print("[yellow]强制模式: 重新处理所有文章[/yellow]")

        # 构建文章 ID 到文章的映射
        article_map = {a.id: a for a in articles}
        article_ids = list(article_map.keys())

        # 统计计数
        stats = {"success": 0, "skipped": 0, "failed": 0}
        results: dict[int, list[str]] = {}

        # 进度回调函数
        def on_progress(article_id: int, status: str, stocks_or_error) -> None:
            stats[status] = stats.get(status, 0) + 1
            if status == "success" and stocks_or_error:
                results[article_id] = stocks_or_error

        # 使用进度条
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("  成功: {task.fields[success]}  跳过: {task.fields[skipped]}  失败: {task.fields[failed]}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "提取股票信息",
                total=len(article_ids),
                success=0,
                skipped=0,
                failed=0,
            )

            # 更新进度的回调
            def progress_callback(article_id: int, status: str, stocks_or_error) -> None:
                on_progress(article_id, status, stocks_or_error)
                article = article_map.get(article_id)
                title = article.title[:20] + "..." if article and len(article.title) > 20 else (article.title if article else "未知")
                progress.update(
                    task,
                    advance=1,
                    description=f"提取股票信息 - {title}",
                    success=stats["success"],
                    skipped=stats["skipped"],
                    failed=stats["failed"],
                )

            # 批量处理
            await processor.batch_extract_stocks(article_ids, force=force, progress_callback=progress_callback)

        # 收集所有股票
        all_stocks: set[str] = set()
        output_lines: list[str] = []

        for article in articles:
            stocks = results.get(article.id, [])
            if stocks:
                all_stocks.update(stocks)
                line = f"文章 #{article.id} 《{article.title[:30]}{'...' if len(article.title) > 30 else ''}》\n  {', '.join(stocks)}"
                output_lines.append(line)

        # 汇总
        summary = f"\n[green]处理完成: {len(results)} 篇文章，提取到 {len(all_stocks)} 只股票[/green]"
        console.print(summary)

        # 导出到文件（默认保存）
        today = datetime.now().strftime("%y%m%d")
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"公众号: {feed.name}\n")
            f.write(f"文章总数: {total}\n")
            f.write(f"处理文章: {len(results)}\n")
            f.write(f"提取股票: {len(all_stocks)}\n")
            f.write("\n" + "=" * 50 + "\n\n")
            for line in output_lines:
                f.write(line + "\n\n")
            f.write("\n" + "=" * 50 + "\n")
            f.write(f"\n所有股票 ({len(all_stocks)} 只):\n")
            for stock in sorted(all_stocks):
                f.write(f"  - {stock}\n")

        console.print(f"[green]已导出到: {output_path}[/green]")

        # 输出简化格式文件
        if simple_info and all_stocks:
            info_file = f"output/extract_stocks/{mp_id}_stocks_{today}_info.txt"
            info_path = Path(info_file)
            info_path.parent.mkdir(parents=True, exist_ok=True)

            sorted_stocks = sorted(all_stocks)
            group_size = 10
            groups = [sorted_stocks[i:i + group_size] for i in range(0, len(sorted_stocks), group_size)]

            with open(info_path, 'w', encoding='utf-8') as f:
                f.write(f"股票列表（共 {len(all_stocks)} 只）\n")
                f.write("=" * 50 + "\n\n")
                for idx, group in enumerate(groups, 1):
                    f.write(f"第 {idx} 组:\n")
                    f.write(", ".join(group) + "\n\n")

            console.print(f"[green]已导出简化格式到: {info_path}[/green]")

    run_async(_extract_stocks())


@ai.command('market-summary')
@click.option('--date', 'target_date', type=str, default=None, help='指定日期 (YYYY-MM-DD)')
@click.option('--offline', is_flag=True, help='离线模式（仅使用已抓取文章）')
@click.option('--list', 'list_summaries', is_flag=True, help='查看历史总结')
@click.option('--force', is_flag=True, help='强制重新生成（覆盖已有总结）')
def market_summary(target_date: str | None, offline: bool, list_summaries: bool, force: bool) -> None:
    """生成 A 股市场总结。

    自动获取最近一个交易日（排除周末和节假日）的市场数据，
    结合已抓取的财经公众号文章，生成结构化的市场总结报告。
    """
    async def _market_summary() -> None:
        db = await get_db()
        analyzer = MarketAnalyzer(db)

        # 查看历史总结（不需要 AIProcessor，无需 LLM 配置）
        if list_summaries:
            summaries = await analyzer.list_summaries(limit=10)
            if not summaries:
                console.print("[yellow]暂无历史总结[/yellow]")
                return

            table = Table(title="历史市场总结")
            table.add_column("日期", style="cyan")
            table.add_column("创建时间", style="green")

            for s in summaries:
                table.add_row(
                    str(s.trade_date),
                    s.created_at.strftime("%Y-%m-%d %H:%M") if s.created_at else "未知",
                )

            console.print(table)
            return

        # ── 本地前置校验（不依赖 AI 组件） ──

        # 解析日期
        if target_date:
            try:
                trade_date = date_type.fromisoformat(target_date)
            except ValueError:
                console.print(f"[red]日期格式错误: {target_date}，请使用 YYYY-MM-DD 格式[/red]")
                return
        else:
            trade_date = analyzer.get_latest_trade_date()

        # 检查是否已有总结
        existing = await analyzer.get_existing_summary(trade_date)
        if existing and not force:
            console.print(f"[yellow]该交易日已有总结，使用 --force 重新生成[/yellow]")
            console.print(f"\n已保存到: output/market_summaries/{trade_date}.md")
            return

        # 执行上下文
        console.print(f"[bold]交易日:[/bold] {trade_date}")
        mode = "离线" if offline else ("强制刷新" if force else "在线")
        console.print(f"[bold]执行模式:[/bold] {mode}")
        if offline:
            strategy = "仅使用本地数据"
        elif force:
            strategy = "跳过缓存，强制刷新"
        else:
            strategy = "优先使用缓存"
        console.print(f"[bold]数据策略:[/bold] {strategy}")
        console.print()

        # ── 本地校验通过，初始化 AI 依赖 ──
        processor = AIProcessor(db)

        # ── [1/3] 获取市场数据 ──
        console.print(f"[bold cyan]{_stage_header(1, 3, '获取市场数据')}[/bold cyan]")
        with console.status("[bold blue]获取中...[/bold blue]"):
            market_data = await analyzer.collect_market_data(
                offline=offline,
                trade_date=trade_date,
                force=force,
            )

        # 判断市场数据是否不可用，不可用时在阶段 1 内闭合
        if market_data.get("error") and market_data.get("data_source") in ("none", "error"):
            _stage_conclusion(False, f"市场数据不可用: {market_data['error']}")
            console.print()
            return

        # 阶段 1 结论 + 摘要
        if market_data.get("offline"):
            _stage_conclusion(True, "[yellow]离线模式: 无实时数据[/yellow]")
        else:
            summary = format_market_data_summary(market_data)
            _stage_conclusion(True, summary)
        _render_market_data_statuses(market_data)

        # 数据来源标签
        source = market_data.get("data_source", "")
        if source:
            _stage_detail(f"数据来源: {_data_source_label(source)}")
        breadth_source = _breadth_source_outcome_label(market_data)
        if breadth_source:
            _stage_detail(f"宽度来源: {breadth_source}")
        console.print()

        # ── [2/3] 获取新闻数据 ──
        console.print(f"[bold cyan]{_stage_header(2, 3, '获取新闻数据')}[/bold cyan]")
        with console.status("[bold blue]获取中...[/bold blue]"):
            news_data = await analyzer.collect_news_data(trade_date, offline=offline)

        time_windows = news_data.get("time_windows", {})
        news_stage_status = news_data.get("status", "success")
        news_status_items = _get_news_status_items(news_data)

        # 阶段 2 结论：根据聚合状态区分完全成功、退化、失败
        if news_stage_status == "failed":
            _stage_conclusion(False, "所有新闻来源获取失败")
        elif news_stage_status == "degraded":
            _stage_conclusion(True, "[yellow]新闻数据获取完成（部分来源失败）[/yellow]")
        else:
            _stage_conclusion(True, "新闻数据获取完成")
        for item in news_status_items:
            _status_detail(
                item["label"],
                item["status"],
                ok_message=item["message"] if item["status"] == "ok" else "",
                empty_message=item["message"] if item["status"] == "empty" else "",
                error_message=item["message"] if item["status"] == "error" else "获取失败",
            )

        # 时间窗口（固定顺序：看盘 → 电报 → 文章）
        if time_windows:
            watch_w = time_windows.get("watch", {})
            telegraph_w = time_windows.get("telegraph", {})
            article_w = time_windows.get("article", {})
            _stage_detail(f"[dim]看盘窗口: {watch_w.get('start', '-')} ~ {watch_w.get('end', '-')}[/dim]")
            _stage_detail(f"[dim]电报窗口: {telegraph_w.get('start', '-')} ~ {telegraph_w.get('end', '-')}[/dim]")
            _stage_detail(f"[dim]文章窗口: {article_w.get('start', '-')} ~ {article_w.get('end', '-')}[/dim]")
        console.print()

        _render_pre_generation_summary(market_data, news_data)

        # ── [3/3] 生成并保存市场总结 ──
        console.print(f"[bold cyan]{_stage_header(3, 3, '生成并保存市场总结')}[/bold cyan]")
        with console.status("[bold blue]AI 生成中...[/bold blue]"):
            start_time = time.perf_counter()

            content = await processor.generate_market_summary(
                trade_date=str(trade_date),
                market_data=market_data,
                articles=news_data.get("articles", []),
                telegraphs=news_data.get("telegraphs", []),
                watch_items=news_data.get("watch_items", []),
                global_market_context=market_data.get("global_market_context"),
            )
            elapsed = time.perf_counter() - start_time

        # 保存总结（文件 + 数据库双重持久化）
        save_path = f"output/market_summaries/{trade_date}.md"
        try:
            await analyzer.save_summary(trade_date, content, market_data)
        except RuntimeError as e:
            _stage_conclusion(False, f"保存失败: {e}")
            console.print()
            return

        # 阶段 3 结论
        _stage_conclusion(True, f"生成并保存完成 (耗时 {format_elapsed_time(elapsed)})")
        _stage_detail(f"已保存到: {save_path}")
        console.print()

        # 显示结果
        console.print(Panel(
            content[:2000] + "..." if len(content) > 2000 else content,
            title=f"[green]{trade_date} 市场总结[/green]",
            border_style="green",
        ))

    run_async(_market_summary())


# 导入并注册 stocks 子命令组
from src.cli.ai_stocks import stocks
ai.add_command(stocks)

# 导入并注册 sector-trends 子命令组
from src.cli.sector_trends import sector_trends
ai.add_command(sector_trends)

# 导入并注册 market-data 子命令组
from src.cli.market_data import market_data
ai.add_command(market_data)
