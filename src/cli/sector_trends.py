"""板块趋势 CLI 命令模块 - sector-trends 子命令组。"""

import time

import click
from rich.panel import Panel
from rich.table import Table

from src.cli.utils import console, format_elapsed_time, run_async
from src.services.sector_trend_service import SectorTrendAnalyzer
from src.storage.database import get_db


# ---------------------------------------------------------------------------
# 阶段渲染辅助（共享 sector / group 趋势生成）
# ---------------------------------------------------------------------------

def _stage_header(index: int, total: int, label: str) -> str:
    """返回阶段头标记，如 '[1/4] 初始化板块'。"""
    return f"[{index}/{total}] {label}"


def _stage_ok(message: str) -> None:
    """输出阶段成功行。"""
    console.print(f"  [green]v[/green] {message}")


def _stage_fail(message: str) -> None:
    """输出阶段失败行。"""
    console.print(f"  [red]x[/red] {message}")


def _stage_detail(message: str) -> None:
    """输出阶段细项行。"""
    console.print(f"      {message}")


@click.group(name="sector-trends")
def sector_trends() -> None:
    """板块趋势跟踪命令。"""
    pass


# ---------------------------------------------------------------------------
# 现有单板块命令
# ---------------------------------------------------------------------------

@sector_trends.command()
@click.option("--days", type=int, default=10, help="回看天数（默认 10）")
def discover(days: int) -> None:
    """发现候选板块。"""
    async def _discover() -> None:
        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        with console.status("[bold blue]发现候选板块中...[/bold blue]"):
            result = await analyzer.discover_sectors(days=days)

        console.print(f"[green]发现完成[/green]")
        console.print(f"  总发现: {result['total_discovered']} 个板块")
        console.print(f"  合并到已有: {result['merged_into_existing']} 个")
        console.print(f"  新候选: {result['new_candidates']} 个")

    run_async(_discover())


@sector_trends.command("ls")
@click.option("--status", type=str, default=None, help="状态筛选 (tracked/candidate/inactive/ignored)")
@click.option("--source", type=str, default=None, help="来源筛选")
@click.option("--active-days", type=int, default=None, help="活跃窗口天数")
@click.option("--limit", "-n", type=int, default=50, help="显示数量（默认 50）")
def list_sectors(status: str | None, source: str | None, active_days: int | None, limit: int) -> None:
    """列出板块。"""
    async def _list_sectors() -> None:
        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        sectors = await analyzer.list_sectors(
            status=status, source=source, active_days=active_days, limit=limit,
        )

        if not sectors:
            console.print("[yellow]暂无板块数据[/yellow]")
            return

        table = Table(title=f"板块列表（共 {len(sectors)} 个）")
        table.add_column("名称", style="cyan")
        table.add_column("状态", style="green")
        table.add_column("来源", style="blue")
        table.add_column("最近出现", style="yellow")
        table.add_column("最近更新", style="magenta")

        for s in sectors:
            status_style = {
                "tracked": "[green]tracked[/green]",
                "candidate": "[yellow]candidate[/yellow]",
                "inactive": "[dim]inactive[/dim]",
                "ignored": "[dim]ignored[/dim]",
            }.get(s["status"], s["status"])

            table.add_row(
                s["canonical_name"],
                status_style,
                s.get("source") or "-",
                s.get("last_seen_date") or "-",
                s.get("last_updated_date") or "-",
            )

        console.print(table)

    run_async(_list_sectors())


@sector_trends.command()
@click.option("--sector", required=True, help="板块名称")
def init(sector: str) -> None:
    """初始化板块跟踪。"""
    async def _init() -> None:
        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        result = await analyzer.init_sector(sector)

        action = result["action"]
        if action == "already_tracked":
            console.print(f"[yellow]板块 '{result['canonical_name']}' 已在跟踪中[/yellow]")
        elif action == "promoted":
            console.print(f"[green]板块 '{result['canonical_name']}' 已从候选提升为跟踪[/green]")
        elif action == "created":
            console.print(f"[green]板块 '{result['canonical_name']}' 已创建为跟踪板块[/green]")

    run_async(_init())


@sector_trends.command()
@click.option("--sector", default=None, help="指定板块名称")
@click.option("--all", "update_all", is_flag=True, help="更新所有跟踪板块")
@click.option("--days", type=int, default=10, help="回看窗口天数（默认 10）")
@click.option("--force", is_flag=True, help="强制重新生成")
@click.option("--limit", type=int, default=None, help="批量更新数量限制（--all 模式）")
@click.option("--continue-on-error", is_flag=True, default=True, help="遇到错误继续更新")
def update(
    sector: str | None,
    update_all: bool,
    days: int,
    force: bool,
    limit: int | None,
    continue_on_error: bool,
) -> None:
    """更新板块趋势。"""
    if not sector and not update_all:
        console.print("[red]请指定 --sector <名称> 或 --all[/red]")
        return

    async def _update() -> None:
        from src.services.ai_processor import AIProcessor

        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        try:
            ai_processor = AIProcessor(db)
        except ValueError as e:
            console.print(f"[red]AI 初始化失败: {e}[/red]")
            return

        if update_all:
            console.print("[bold]批量更新板块趋势[/bold]")
            console.print(f"  目标: tracked 板块")
            console.print(f"  回看: {days} 天")
            console.print()

            with console.status("[bold blue]批量更新板块趋势中...[/bold blue]"):
                result = await analyzer.update_all_sector_trends(
                    limit=limit,
                    force=force,
                    continue_on_error=continue_on_error,
                    ai_processor=ai_processor,
                    days=days,
                )

            console.print(f"\n[bold]批量更新完成[/bold]")
            console.print(f"  成功: [green]{result['success']}[/green]")
            console.print(f"  跳过: [yellow]{result['skipped']}[/yellow]")
            console.print(f"  失败: [red]{result['failed']}[/red]")

            if result.get("results"):
                table = Table(title="更新详情")
                table.add_column("板块", style="cyan")
                table.add_column("状态", style="green")
                table.add_column("趋势", style="yellow")
                table.add_column("强度", style="blue")
                table.add_column("倾向", style="magenta")

                for r in result["results"]:
                    action = r.get("action", "unknown")
                    if action == "updated":
                        status_text = "[green]已更新[/green]"
                    elif action == "skipped":
                        status_text = "[yellow]已跳过[/yellow]"
                    elif action == "failed":
                        status_text = f"[red]失败: {r.get('error', '')[:30]}[/red]"
                    else:
                        status_text = action

                    table.add_row(
                        r.get("sector_name", "-"),
                        status_text,
                        r.get("trend_status", "-"),
                        r.get("strength_level", "-"),
                        r.get("action_bias", "-"),
                    )

                console.print(table)
            return

        # 单板块更新 - 阶段式输出
        end_date = analyzer._market_analyzer.get_latest_trade_date()

        console.print(f"[bold]板块: {sector}[/bold]")
        console.print(f"  交易日: {end_date}")
        console.print(f"  回看窗口: {days} 天")
        console.print()

        total_stages = 4
        start_time = time.perf_counter()

        # [1/4] 初始化板块
        console.print(f"[bold cyan]{_stage_header(1, total_stages, '初始化板块')}[/bold cyan]")
        sector_obj = await analyzer._ensure_tracked(sector)
        _stage_ok(f"已处于 tracked 状态")
        console.print()

        # [2/4] 收集板块证据
        console.print(f"[bold cyan]{_stage_header(2, total_stages, '收集板块证据')}[/bold cyan]")
        with console.status("[bold blue]收集证据中...[/bold blue]"):
            evidence = await analyzer.collect_sector_evidence(
                sector_obj.canonical_name, end_date, days,
            )
        evidence_count = evidence.get("total_evidence_count", 0)
        sparse = evidence.get("is_sparse", True)
        _stage_ok("证据收集完成")
        _stage_detail(f"行情强弱榜: {len(evidence.get('market_appearances', []))} 条")
        _stage_detail(f"看盘标签: {len(evidence.get('cls_watch_mentions', []))} 条")
        if sparse:
            _stage_detail("[yellow]~ 证据质量: 偏稀疏[/yellow]")
        console.print()

        # [3/4] 生成趋势总结
        console.print(f"[bold cyan]{_stage_header(3, total_stages, '生成趋势总结')}[/bold cyan]")
        # 检查是否已有
        if not force:
            existing = await analyzer.get_previous_summary(sector_obj.id)
            if existing and existing.end_date == end_date:
                _stage_ok("已跳过 - 今日已更新")
                if existing.output_path:
                    _stage_detail(f"报告: {existing.output_path}")
                console.print()
                return

        with console.status("[bold blue]AI 生成中...[/bold blue]"):
            gen_start = time.perf_counter()
            result = await analyzer.update_sector_trend(
                sector,
                days=days,
                ai_processor=ai_processor,
                force=force,
            )
            gen_elapsed = time.perf_counter() - gen_start

        action = result.get("action")
        if action == "skipped":
            _stage_ok(f"已跳过 - {result.get('reason', '')}")
            if result.get("output_path"):
                _stage_detail(f"报告: {result['output_path']}")
        elif action == "updated":
            _stage_ok(f"AI 生成完成 (耗时 {format_elapsed_time(gen_elapsed)})")
            _stage_detail(f"趋势: {result.get('trend_status', '-')}")
            _stage_detail(f"强度: {result.get('strength_level', '-')}")
            _stage_detail(f"倾向: {result.get('action_bias', '-')}")
        else:
            console.print(f"  [yellow]操作结果: {action}[/yellow]")
        console.print()

        # [4/4] 保存结果
        console.print(f"[bold cyan]{_stage_header(4, total_stages, '保存结果')}[/bold cyan]")
        if action == "updated":
            _stage_ok("保存完成")
            _stage_detail(f"报告: {result.get('output_path', '-')}")
        else:
            _stage_ok("无需保存")
        console.print()

        elapsed = time.perf_counter() - start_time
        console.print(f"[dim]总耗时: {format_elapsed_time(elapsed)}[/dim]")

    run_async(_update())


@sector_trends.command()
@click.option("--sector", required=True, help="板块名称")
def show(sector: str) -> None:
    """查看板块最新趋势。"""
    async def _show() -> None:
        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        result = await analyzer.show_latest(sector)

        if not result:
            console.print(f"[yellow]板块 '{sector}' 未找到[/yellow]")
            return

        if not result.get("has_summary"):
            console.print(f"[yellow]板块 '{result['sector_name']}' 暂无趋势总结[/yellow]")
            console.print(f"  状态: {result.get('status', '-')}")
            return

        console.print(f"\n[bold cyan]板块: {result['sector_name']}[/bold cyan]")
        console.print(f"  日期: {result.get('end_date', '-')}")
        console.print(f"  趋势: {result.get('trend_status', '-')}")
        console.print(f"  强度: {result.get('strength_level', '-')}")
        console.print(f"  倾向: {result.get('action_bias', '-')}")

        if result.get("output_path"):
            console.print(f"  报告路径: {result['output_path']}")

        content = result.get("content", "")
        if content:
            console.print()
            console.print(Panel(
                content[:2000] + "..." if len(content) > 2000 else content,
                title=f"[green]{result['sector_name']} 趋势报告[/green]",
                border_style="green",
            ))

    run_async(_show())


@sector_trends.command()
@click.option("--sector", required=True, help="板块名称")
@click.option("--limit", "-n", type=int, default=20, help="显示数量（默认 20）")
def history(sector: str, limit: int) -> None:
    """查看板块趋势历史。"""
    async def _history() -> None:
        db = await get_db()
        analyzer = SectorTrendAnalyzer(db)

        records = await analyzer.history(sector, limit=limit)

        if not records:
            console.print(f"[yellow]板块 '{sector}' 暂无历史记录[/yellow]")
            return

        table = Table(title=f"板块 '{sector}' 趋势历史（共 {len(records)} 条）")
        table.add_column("日期", style="cyan")
        table.add_column("趋势状态", style="green")
        table.add_column("强度", style="yellow")
        table.add_column("操作倾向", style="blue")
        table.add_column("报告路径", style="dim")

        for r in records:
            table.add_row(
                r.get("end_date", "-"),
                r.get("trend_status", "-"),
                r.get("strength_level", "-"),
                r.get("action_bias", "-"),
                r.get("output_path") or "-",
            )

        console.print(table)

    run_async(_history())


# ---------------------------------------------------------------------------
# 分组子命令组
# ---------------------------------------------------------------------------

@sector_trends.group("groups")
def groups() -> None:
    """板块分组管理命令。"""
    pass


@groups.command("ls")
@click.option("--status", type=str, default=None, help="状态筛选 (active/inactive)")
@click.option("--limit", "-n", type=int, default=50, help="显示数量（默认 50）")
def groups_list(status: str | None, limit: int) -> None:
    """列出板块分组。"""
    async def _list() -> None:
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        groups_data = await service.list_groups(status=status, limit=limit)

        if not groups_data:
            console.print("[yellow]暂无分组数据[/yellow]")
            return

        table = Table(title=f"板块分组列表（共 {len(groups_data)} 个）")
        table.add_column("名称", style="cyan")
        table.add_column("状态", style="green")
        table.add_column("成员数", style="blue", justify="right")
        table.add_column("最新更新", style="yellow")
        table.add_column("待处理建议", style="magenta", justify="right")

        for g in groups_data:
            status_style = {
                "active": "[green]active[/green]",
                "inactive": "[dim]inactive[/dim]",
            }.get(g["status"], g["status"])

            table.add_row(
                g["canonical_name"],
                status_style,
                str(g["member_count"]),
                g.get("latest_update_date") or "-",
                str(g.get("pending_suggestion_count", 0)),
            )

        console.print(table)

    run_async(_list())


@groups.command("show")
@click.option("--group", "group_name", required=True, help="分组名称")
@click.option("--latest", is_flag=True, help="显示最新报告")
def groups_show(group_name: str, latest: bool) -> None:
    """查看分组详情。"""
    async def _show() -> None:
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        if latest:
            result = await service.show_latest_group_report(group_name)
            if not result:
                console.print(f"[yellow]分组 '{group_name}' 未找到[/yellow]")
                return

            if not result.get("has_summary"):
                console.print(f"[yellow]分组 '{result['group_name']}' 暂无趋势报告[/yellow]")
                console.print(f"  状态: {result.get('status', '-')}")
                return

            console.print(f"\n[bold cyan]分组: {result['group_name']}[/bold cyan]")
            console.print(f"  日期: {result.get('end_date', '-')}")
            console.print(f"  组级状态: {result.get('trend_status', '-')}")
            console.print(f"  强度: {result.get('strength_level', '-')}")
            console.print(f"  倾向: {result.get('action_bias', '-')}")

            if result.get("output_path"):
                console.print(f"  报告路径: {result['output_path']}")

            content = result.get("content", "")
            if content:
                console.print()
                console.print(Panel(
                    content[:2000] + "..." if len(content) > 2000 else content,
                    title=f"[green]{result['group_name']} 分组趋势报告[/green]",
                    border_style="green",
                ))
            return

        result = await service.show_group_detail(group_name)
        if not result:
            console.print(f"[yellow]分组 '{group_name}' 未找到[/yellow]")
            return

        console.print(f"\n[bold cyan]分组: {result['canonical_name']}[/bold cyan]")
        console.print(f"  状态: {result['status']}")

        if result.get("aliases"):
            console.print(f"  别名: {', '.join(result['aliases'])}")
        if result.get("keywords"):
            console.print(f"  关键词: {', '.join(result['keywords'])}")
        if result.get("description"):
            console.print(f"  描述: {result['description']}")

        members = result.get("members", [])
        if members:
            console.print(f"\n  [bold]成员 ({len(members)} 个):[/bold]")
            table = Table(show_header=True)
            table.add_column("板块", style="cyan")
            table.add_column("状态", style="green")
            table.add_column("关系", style="blue")
            table.add_column("权重", style="magenta", justify="right")
            table.add_column("最近出现", style="yellow")
            table.add_column("最近更新", style="dim")

            for m in members:
                table.add_row(
                    m["sector_name"],
                    m["sector_status"],
                    m["relation_type"],
                    f"{m.get('weight', 1.0):.1f}",
                    m.get("last_seen_date") or "-",
                    m.get("latest_summary_date") or "-",
                )

            console.print(table)
        else:
            console.print("\n  [yellow]暂无成员[/yellow]")

    run_async(_show())


@groups.command("create")
@click.option("--group", "group_name", required=True, help="分组名称")
def groups_create(group_name: str) -> None:
    """创建板块分组。"""
    async def _create() -> None:
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        result = await service.create_group(group_name)

        action = result["action"]
        if action == "already_exists":
            console.print(f"[yellow]分组 '{result['canonical_name']}' 已存在[/yellow]")
        elif action == "created":
            console.print(f"[green]分组 '{result['canonical_name']}' 已创建[/green]")

    run_async(_create())


@groups.command("add")
@click.option("--group", "group_name", required=True, help="分组名称")
@click.option("--sector", "sector_name", required=True, help="板块名称")
@click.option("--type", "relation_type", default="related",
              type=click.Choice(["core", "upstream", "downstream", "material",
                                  "equipment", "catalyst", "related"]),
              help="关系类型")
def groups_add(group_name: str, sector_name: str, relation_type: str) -> None:
    """向分组添加成员板块。"""
    async def _add() -> None:
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        result = await service.add_member(
            group_name=group_name,
            sector_name=sector_name,
            relation_type=relation_type,
        )

        action = result.get("action")
        if action == "added":
            console.print(f"[green]板块 '{result['sector_name']}' 已添加到分组 (类型: {relation_type})[/green]")
        elif action == "updated":
            console.print(f"[green]板块 '{result['sector_name']}' 成员关系已更新 (类型: {relation_type})[/green]")
        elif action == "error":
            console.print(f"[red]{result['error']}[/red]")

    run_async(_add())


@groups.command("suggest")
@click.option("--days", type=int, default=10, help="回看天数（默认 10）")
def groups_suggest(days: int) -> None:
    """生成分组建议。"""
    async def _suggest() -> None:
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        with console.status("[bold blue]生成分组建议中...[/bold blue]"):
            result = await service.generate_suggestions(days=days)

        console.print(f"[green]建议生成完成[/green]")
        console.print(f"  新建分组建议: {result['new_group_suggestions']} 个")
        console.print(f"  补充成员建议: {result['add_member_suggestions']} 个")
        console.print(f"  刷新已有建议: {result['refreshed_suggestions']} 个")

    run_async(_suggest())


@groups.command("suggestions")
@click.option("--status", type=str, default="pending", help="状态筛选 (pending/accepted/ignored)")
@click.option("--type", "suggestion_type", type=str, default=None, help="建议类型筛选")
@click.option("--group", "group_name", type=str, default=None, help="目标分组筛选")
def groups_suggestions(status: str, suggestion_type: str | None, group_name: str | None) -> None:
    """查看分组建议。"""
    async def _suggestions() -> None:
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        suggestions = await service.list_suggestions(
            status=status,
            suggestion_type=suggestion_type,
            group_name=group_name,
        )

        if not suggestions:
            console.print("[yellow]暂无建议[/yellow]")
            return

        table = Table(title=f"分组建议（共 {len(suggestions)} 条）")
        table.add_column("ID", style="dim", justify="right")
        table.add_column("类型", style="cyan")
        table.add_column("目标分组", style="green")
        table.add_column("置信度", style="blue", justify="right")
        table.add_column("成员数", style="magenta", justify="right")
        table.add_column("原因", style="yellow", max_width=40)

        for s in suggestions:
            type_style = {
                "new_group": "[cyan]新建[/cyan]",
                "add_members": "[green]补充[/green]",
                "update_members": "[yellow]更新[/yellow]",
            }.get(s["suggestion_type"], s["suggestion_type"])

            members = s.get("members", [])
            member_names = ", ".join(m.get("sector_name", "?") for m in members[:3])
            if len(members) > 3:
                member_names += f" +{len(members) - 3}"

            table.add_row(
                str(s["id"]),
                type_style,
                s.get("target_group_name") or s.get("suggested_group_name") or "-",
                f"{s.get('confidence', 0):.2f}" if s.get("confidence") else "-",
                str(len(members)),
                (s.get("reason") or "-")[:40],
            )

        console.print(table)

        # 显示第一个建议的成员详情
        if suggestions:
            s = suggestions[0]
            members = s.get("members", [])
            if members:
                console.print(f"\n[bold]建议 #{s['id']} 成员详情:[/bold]")
                for m in members:
                    status_label = {
                        "tracked": "[green]tracked[/green]",
                        "candidate": "[yellow]candidate[/yellow]",
                        "inactive": "[dim]inactive[/dim]",
                    }.get(m.get("sector_status", ""), m.get("sector_status", ""))
                    console.print(f"  {m['sector_name']} ({status_label}) -> {m.get('suggested_relation_type', 'related')}")

    run_async(_suggestions())


@groups.command("accept")
@click.argument("suggestion_id", type=int)
@click.option("--include", "include_sectors", multiple=True, help="仅接受这些板块（可多次使用）")
@click.option("--exclude", "exclude_sectors", multiple=True, help="排除这些板块（可多次使用）")
@click.option("--keep-status", is_flag=True, help="保持板块原状态，不提升 candidate")
def groups_accept(suggestion_id: int, include_sectors: tuple[str, ...], exclude_sectors: tuple[str, ...], keep_status: bool) -> None:
    """接受分组建议。"""
    async def _accept() -> None:
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        result = await service.accept_suggestion(
            suggestion_id=suggestion_id,
            include_sectors=list(include_sectors) or None,
            exclude_sectors=list(exclude_sectors) or None,
            keep_status=keep_status,
        )

        action = result.get("action")
        if action == "accepted":
            console.print(f"[green]建议已接受[/green]")
            console.print(f"  分组ID: {result['group_id']}")
            members = result.get("accepted_members", [])
            if members:
                console.print(f"  接受成员: {', '.join(members)}")
        elif action == "error":
            console.print(f"[red]{result['error']}[/red]")

    run_async(_accept())


@groups.command("ignore")
@click.argument("suggestion_id", type=int)
def groups_ignore(suggestion_id: int) -> None:
    """忽略分组建议。"""
    async def _ignore() -> None:
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        result = await service.ignore_suggestion(suggestion_id=suggestion_id)

        action = result.get("action")
        if action == "ignored":
            console.print(f"[green]建议 {suggestion_id} 已忽略[/green]")
        elif action == "error":
            console.print(f"[red]{result['error']}[/red]")

    run_async(_ignore())


@groups.command("update")
@click.option("--group", "group_name", default=None, help="指定分组名称")
@click.option("--all", "update_all", is_flag=True, help="更新所有活跃分组")
@click.option("--days", type=int, default=10, help="回看窗口天数（默认 10）")
@click.option("--force", is_flag=True, help="强制重新生成报告")
@click.option("--no-refresh-members", is_flag=True, help="跳过成员板块刷新")
@click.option("--refresh-members", "force_refresh_members", is_flag=True, help="强制刷新所有成员")
@click.option("--limit", type=int, default=None, help="批量更新数量限制（--all 模式）")
@click.option("--continue-on-error", is_flag=True, default=True, help="遇到错误继续")
def groups_update(
    group_name: str | None,
    update_all: bool,
    days: int,
    force: bool,
    no_refresh_members: bool,
    force_refresh_members: bool,
    limit: int | None,
    continue_on_error: bool,
) -> None:
    """更新分组趋势。"""
    if not group_name and not update_all:
        console.print("[red]请指定 --group <名称> 或 --all[/red]")
        return

    async def _update() -> None:
        from src.services.ai_processor import AIProcessor
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        try:
            ai_processor = AIProcessor(db)
        except ValueError as e:
            console.print(f"[red]AI 初始化失败: {e}[/red]")
            return

        if update_all:
            console.print("[bold]批量更新分组趋势[/bold]")
            console.print(f"  目标: tracked 分组")
            console.print(f"  成员刷新: {'跳过' if no_refresh_members else '默认刷新缺失 tracked 成员'}")
            console.print()

            result = await service.update_all_group_trends(
                ai_processor=ai_processor,
                force=force,
                no_refresh_members=no_refresh_members,
                force_refresh_members=force_refresh_members,
                days=days,
                continue_on_error=continue_on_error,
                limit=limit,
            )

            console.print(f"\n[bold]批量更新完成[/bold]")
            console.print(f"  成功: [green]{result['success']}[/green]")
            console.print(f"  跳过: [yellow]{result['skipped']}[/yellow]")
            console.print(f"  失败: [red]{result['failed']}[/red]")
            if not no_refresh_members:
                console.print(f"  成员刷新成功: [green]{result['member_refresh_success']}[/green]")
                console.print(f"  成员刷新失败: [red]{result['member_refresh_failed']}[/red]")

            if result.get("results"):
                table = Table(title="更新详情")
                table.add_column("分组", style="cyan")
                table.add_column("状态", style="green")
                table.add_column("成员刷新", style="blue")
                table.add_column("报告", style="dim")

                for r in result["results"]:
                    action = r.get("action", "unknown")
                    if action == "updated":
                        status_text = "[green]已更新[/green]"
                    elif action == "skipped":
                        status_text = "[yellow]已跳过[/yellow]"
                    elif action == "failed":
                        status_text = f"[red]失败[/red]"
                    else:
                        status_text = action

                    refresh_results = r.get("member_refresh_results", [])
                    refreshed = sum(1 for mr in refresh_results if mr.get("action") == "updated")
                    total_mr = len(refresh_results)
                    refresh_text = f"{refreshed}/{total_mr}" if total_mr > 0 else "-"

                    table.add_row(
                        r.get("group_name", "-"),
                        status_text,
                        refresh_text,
                        r.get("output_path") or "-",
                    )

                console.print(table)
            return

        # 单分组更新 - 阶段式输出
        from src.services.sector_group_service import SectorGroupService

        end_date = service._get_latest_trade_date()

        console.print(f"[bold]分组: {group_name}[/bold]")
        console.print(f"  交易日: {end_date}")
        mode = "跳过成员刷新" if no_refresh_members else ("强制刷新所有成员" if force_refresh_members else "默认刷新缺失 tracked 成员")
        console.print(f"  执行模式: {mode}")
        console.print()

        total_stages = 5
        start_time = time.perf_counter()

        # [1/5] 检查成员状态
        console.print(f"[bold cyan]{_stage_header(1, total_stages, '检查成员状态')}[/bold cyan]")
        detail = await service.show_group_detail(group_name)
        if not detail:
            console.print(f"[red]分组 '{group_name}' 未找到[/red]")
            return

        members = detail.get("members", [])
        tracked_members = [m for m in members if m.get("sector_status") == "tracked"]
        candidate_members = [m for m in members if m.get("sector_status") == "candidate"]

        _stage_ok(f"检查完成")
        _stage_detail(f"总成员: {len(members)}")
        _stage_detail(f"tracked: {len(tracked_members)}")
        if candidate_members:
            _stage_detail(f"[yellow]candidate (跳过): {', '.join(m['sector_name'] for m in candidate_members)}[/yellow]")
        console.print()

        # [2/5] 刷新成员板块
        console.print(f"[bold cyan]{_stage_header(2, total_stages, '刷新成员板块')}[/bold cyan]")
        result = await service.update_group_trend(
            group_name,
            ai_processor=ai_processor,
            force=force,
            no_refresh_members=no_refresh_members,
            force_refresh_members=force_refresh_members,
            days=days,
            continue_on_error=continue_on_error,
        )

        refresh_results = result.get("member_refresh_results", [])
        if no_refresh_members:
            _stage_ok("已跳过成员刷新")
        elif refresh_results:
            for mr in refresh_results:
                mr_action = mr.get("action", "")
                if mr_action == "updated":
                    _stage_ok(f"{mr.get('sector_name', '?')}: 已更新")
                elif mr_action == "skipped_candidate":
                    console.print(f"  [yellow]~ {mr.get('sector_name', '?')}: candidate 跳过[/yellow]")
                elif mr_action == "skipped_has_report":
                    _stage_detail(f"{mr.get('sector_name', '?')}: 今日已更新")
                elif mr_action == "failed":
                    _stage_fail(f"{mr.get('sector_name', '?')}: {mr.get('error', '失败')}")
        else:
            _stage_ok("无需刷新")
        console.print()

        # [3/5] 收集分组证据
        console.print(f"[bold cyan]{_stage_header(3, total_stages, '收集分组证据')}[/bold cyan]")
        if result.get("action") == "error":
            _stage_fail(result.get("error", "未知错误"))
            console.print()
            return
        _stage_ok("证据收集完成")
        console.print()

        # [4/5] 生成分组总结
        console.print(f"[bold cyan]{_stage_header(4, total_stages, '生成分组总结')}[/bold cyan]")
        action = result.get("action")
        if action == "skipped":
            _stage_ok(f"已跳过 - {result.get('reason', '')}")
            if result.get("output_path"):
                _stage_detail(f"报告: {result['output_path']}")
            console.print()
            return
        elif action == "updated":
            _stage_ok(f"AI 生成完成")
            _stage_detail(f"组级状态: {result.get('trend_status', '-')}")
            _stage_detail(f"强度: {result.get('strength_level', '-')}")
            _stage_detail(f"倾向: {result.get('action_bias', '-')}")
        elif action == "no_ai_processor":
            console.print(f"  [yellow]无 AI 处理器[/yellow]")
        console.print()

        # [5/5] 保存结果
        console.print(f"[bold cyan]{_stage_header(5, total_stages, '保存结果')}[/bold cyan]")
        if action == "updated":
            _stage_ok("保存完成")
            _stage_detail(f"分组报告: {result.get('output_path', '-')}")
        else:
            _stage_ok("无需保存")
        console.print()

        elapsed = time.perf_counter() - start_time
        console.print(f"[dim]总耗时: {format_elapsed_time(elapsed)}[/dim]")

    run_async(_update())


@groups.command("history")
@click.option("--group", "group_name", required=True, help="分组名称")
@click.option("--limit", "-n", type=int, default=20, help="显示数量（默认 20）")
def groups_history(group_name: str, limit: int) -> None:
    """查看分组趋势历史。"""
    async def _history() -> None:
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        records = await service.group_history(group_name, limit=limit)

        if not records:
            console.print(f"[yellow]分组 '{group_name}' 暂无历史记录[/yellow]")
            return

        table = Table(title=f"分组 '{group_name}' 趋势历史（共 {len(records)} 条）")
        table.add_column("日期", style="cyan")
        table.add_column("组级状态", style="green")
        table.add_column("强度", style="yellow")
        table.add_column("操作倾向", style="blue")
        table.add_column("报告路径", style="dim")

        for r in records:
            table.add_row(
                r.get("end_date", "-"),
                r.get("trend_status", "-"),
                r.get("strength_level", "-"),
                r.get("action_bias", "-"),
                r.get("output_path") or "-",
            )

        console.print(table)

    run_async(_history())
