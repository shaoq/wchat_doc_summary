"""AI Stocks 子命令模块 - stocks 子命令组。"""

import json

import click
from rich.table import Table

from src.cli.utils import console, run_async
from src.models.schema import Article, ArticleProcessing, Feed
from src.storage.database import get_db


@click.group(name='stocks')
def stocks() -> None:
    """股票信息查询命令。"""
    pass


@stocks.command('list')
@click.option('--mp-id', 'mp_id', default=None, help='指定公众号 ID（可选）')
@click.option('--limit', '-n', type=int, default=50, help='显示数量（默认 50）')
def stocks_list(mp_id: str | None, limit: int) -> None:
    """列出所有已提取的股票（按出现次数排序）。"""
    async def _stocks_list() -> None:
        db = await get_db()

        from sqlalchemy import func as sql_func, select

        async with db.get_session() as session:
            # 构建查询
            query = (
                select(ArticleProcessing.result, Article.feed_id)
                .join(Article, ArticleProcessing.article_id == Article.id)
                .where(
                    ArticleProcessing.task_type == "extract_stocks",
                    ArticleProcessing.status == "success",
                )
            )

            if mp_id:
                # 过滤特定公众号
                subquery = select(Feed.id).where(Feed.mp_id == mp_id).scalar_subquery()
                query = query.where(Article.feed_id == subquery)

            result = await session.execute(query)
            rows = result.all()

        # 统计股票出现次数
        stock_counts: dict[str, int] = {}
        for row in rows:
            try:
                stocks_list_data = json.loads(row[0]) if row[0] else []
                for stock in stocks_list_data:
                    stock_counts[stock] = stock_counts.get(stock, 0) + 1
            except json.JSONDecodeError:
                continue

        if not stock_counts:
            console.print("[yellow]暂无股票数据[/yellow]")
            return

        # 按出现次数排序
        sorted_stocks = sorted(stock_counts.items(), key=lambda x: x[1], reverse=True)[:limit]

        table = Table(title=f"股票列表（共 {len(stock_counts)} 只，显示前 {len(sorted_stocks)} 只）")
        table.add_column("股票名称", style="cyan")
        table.add_column("出现次数", style="green", justify="right")

        for stock, count in sorted_stocks:
            table.add_row(stock, str(count))

        console.print(table)

    run_async(_stocks_list())


@stocks.command()
@click.argument('keyword')
def search(keyword: str) -> None:
    """根据关键词搜索股票。

    KEYWORD: 搜索关键词
    """
    async def _search() -> None:
        db = await get_db()

        from sqlalchemy import select

        async with db.get_session() as session:
            query = (
                select(ArticleProcessing.result, ArticleProcessing.article_id)
                .join(Article, ArticleProcessing.article_id == Article.id)
                .where(
                    ArticleProcessing.task_type == "extract_stocks",
                    ArticleProcessing.status == "success",
                )
            )
            result = await session.execute(query)
            rows = result.all()

        # 搜索匹配的股票
        matched_stocks: dict[str, int] = {}
        for row in rows:
            try:
                stocks_list_data = json.loads(row[0]) if row[0] else []
                for stock in stocks_list_data:
                    if keyword.lower() in stock.lower():
                        matched_stocks[stock] = matched_stocks.get(stock, 0) + 1
            except json.JSONDecodeError:
                continue

        if not matched_stocks:
            console.print(f"[yellow]未找到包含 '{keyword}' 的股票[/yellow]")
            return

        # 按出现次数排序
        sorted_stocks = sorted(matched_stocks.items(), key=lambda x: x[1], reverse=True)

        table = Table(title=f"搜索结果: '{keyword}'（找到 {len(sorted_stocks)} 只）")
        table.add_column("股票名称", style="cyan")
        table.add_column("出现次数", style="green", justify="right")

        for stock, count in sorted_stocks:
            table.add_row(stock, str(count))

        console.print(table)

    run_async(_search())


@stocks.command()
@click.argument('stock_name')
@click.option('--limit', '-n', type=int, default=20, help='显示文章数量（默认 20）')
def show(stock_name: str, limit: int) -> None:
    """显示某股票出现在哪些文章中。

    STOCK_NAME: 股票名称（支持模糊匹配）
    """
    async def _show() -> None:
        db = await get_db()

        from sqlalchemy import select

        async with db.get_session() as session:
            query = (
                select(ArticleProcessing.result, ArticleProcessing.article_id, Article.title, Article.publish_time)
                .join(Article, ArticleProcessing.article_id == Article.id)
                .where(
                    ArticleProcessing.task_type == "extract_stocks",
                    ArticleProcessing.status == "success",
                )
                .order_by(Article.publish_time.desc())
            )
            result = await session.execute(query)
            rows = result.all()

        # 查找包含该股票的文章
        matched_articles = []
        for row in rows:
            try:
                stocks_list_data = json.loads(row[0]) if row[0] else []
                # 模糊匹配
                for stock in stocks_list_data:
                    if stock_name.lower() in stock.lower():
                        matched_articles.append({
                            "title": row[2],
                            "publish_time": row[3],
                            "stocks": stocks_list_data,
                        })
                        break
            except json.JSONDecodeError:
                continue

        if not matched_articles:
            console.print(f"[yellow]未找到包含 '{stock_name}' 的文章[/yellow]")
            return

        matched_articles = matched_articles[:limit]

        console.print(f"[cyan]股票: {stock_name}[/cyan]")
        console.print(f"[blue]出现在 {len(matched_articles)} 篇文章中:[/blue]\n")

        for article in matched_articles:
            publish_str = article["publish_time"].strftime("%Y-%m-%d") if article["publish_time"] else "未知日期"
            title = article["title"][:40] + "..." if len(article["title"]) > 40 else article["title"]
            console.print(f"  • 《{title}》 {publish_str}")

        if len(matched_articles) == limit:
            console.print(f"\n[dim]显示前 {limit} 篇，使用 --limit 查看更多[/dim]")

    run_async(_show())
