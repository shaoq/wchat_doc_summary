"""板块趋势 CLI 命令模块 - sector-trends 子命令组。"""

import json
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
@click.option("--date", "report_date", required=True, type=str, help="目标日期 (YYYY-MM-DD)")
@click.option("--days", type=int, default=10, help="回看窗口天数（默认 10）")
def repair(report_date: str, days: int) -> None:
    """修复 CLS 看盘数据板块归属（不生成趋势报告）。"""
    from datetime import date as date_type

    try:
        target_date = date_type.fromisoformat(report_date)
    except ValueError:
        console.print(f"[red]日期格式错误: {report_date}，请使用 YYYY-MM-DD 格式[/red]")
        return

    async def _repair() -> None:
        from src.services.cls_watch_repair import ClsWatchRepairService

        db = await get_db()
        service = ClsWatchRepairService(db)

        console.print(f"[bold]修复 CLS 看盘板块归属[/bold]")
        console.print(f"  目标日期: {target_date}")
        console.print(f"  窗口: {days} 天")
        console.print()

        with console.status("[bold blue]修复中...[/bold blue]"):
            result = await service.repair_window(target_date, days)

        console.print(f"\n[bold]修复完成[/bold]")
        console.print(f"  已修复: [green]{result.repaired}[/green]")
        console.print(f"  未变更: [dim]{result.unchanged}[/dim]")
        console.print(f"  未匹配: [yellow]{result.unmatched}[/yellow]")
        console.print(f"  低置信: [dim]{result.low_confidence}[/dim]")
        console.print(f"  跳过: [dim]{result.skipped}[/dim]")

        if result.details:
            table = Table(title="修复详情")
            table.add_column("标题", style="cyan", max_width=40)
            table.add_column("归属板块", style="green")
            table.add_column("置信度", style="yellow")

            for d in result.details[:20]:  # 最多显示 20 条
                sectors_str = ", ".join(d["sectors"])
                confidences = ", ".join(
                    m["confidence"] for m in d["matches"]
                )
                table.add_row(
                    (d["title"] or "")[:40],
                    sectors_str,
                    confidences,
                )

            console.print(table)

    run_async(_repair())


@sector_trends.command()
@click.option("--sector", default=None, help="指定板块名称")
@click.option("--all", "update_all", is_flag=True, help="更新所有跟踪板块")
@click.option("--days", type=int, default=10, help="回看窗口天数（默认 10）")
@click.option("--force", is_flag=True, help="强制重新生成")
@click.option("--limit", type=int, default=None, help="批量更新数量限制（--all 模式）")
@click.option("--continue-on-error", is_flag=True, default=True, help="遇到错误继续更新")
@click.option("--date", "report_date", type=str, default=None, help="报告日期 (YYYY-MM-DD)")
@click.option("--skip-repair", is_flag=True, default=False, help="跳过 CLS 看盘板块归属修复")
def update(
    sector: str | None,
    update_all: bool,
    days: int,
    force: bool,
    limit: int | None,
    continue_on_error: bool,
    report_date: str | None,
    skip_repair: bool,
) -> None:
    """更新板块趋势。"""
    if not sector and not update_all:
        console.print("[red]请指定 --sector <名称> 或 --all[/red]")
        return

    # 解析日期
    from datetime import date as date_type

    parsed_report_date: date_type | None = None
    if report_date:
        try:
            parsed_report_date = date_type.fromisoformat(report_date)
        except ValueError:
            console.print(f"[red]日期格式错误: {report_date}，请使用 YYYY-MM-DD 格式[/red]")
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
                    report_date=parsed_report_date,
                    skip_repair=skip_repair,
                )

            console.print(f"\n[bold]批量更新完成[/bold]")
            console.print(f"  成功: [green]{result['success']}[/green]")
            console.print(f"  跳过: [yellow]{result['skipped']}[/yellow]")
            console.print(f"  失败: [red]{result['failed']}[/red]")

            if result.get("repair_result"):
                rr = result["repair_result"]
                console.print(f"  修复: [green]{rr.repaired}[/green] 已归属, [yellow]{rr.low_confidence}[/yellow] 低置信, [dim]{rr.unmatched} 未匹配[/dim]")

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
        end_date = parsed_report_date or analyzer._market_analyzer.get_latest_trade_date()

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
                report_date=parsed_report_date,
                skip_repair=skip_repair,
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


# ---------------------------------------------------------------------------
# 主题词典子命令组
# ---------------------------------------------------------------------------


@groups.group("themes")
def themes() -> None:
    """主题词典管理命令。"""
    pass


@themes.command("ls")
def themes_ls() -> None:
    """列出有效主题。"""
    async def _run() -> None:
        from src.services.theme_registry import ThemeRegistryService

        db = await get_db()
        service = ThemeRegistryService(db)
        registry = await service.get_registry()
        theme_list = registry.list_themes()

        if not theme_list:
            console.print("[yellow]暂无主题[/yellow]")
            return

        table = Table(title=f"主题词典（共 {len(theme_list)} 个）")
        table.add_column("主题名", style="cyan")
        table.add_column("来源", style="green")
        table.add_column("总成员", justify="right")
        table.add_column("活跃成员", style="blue", justify="right")
        table.add_column("禁用数", style="yellow", justify="right")

        for t in theme_list:
            table.add_row(
                t["name"],
                t["source"],
                str(t["total_members"]),
                str(t["active_members"]),
                str(t["disabled_count"]),
            )
        console.print(table)

    run_async(_run())


@themes.command("show")
@click.option("--theme", "theme_name", required=True, help="主题名")
def themes_show(theme_name: str) -> None:
    """查看主题详情。"""
    async def _run() -> None:
        from src.services.theme_registry import ThemeRegistryService

        db = await get_db()
        service = ThemeRegistryService(db)
        registry = await service.get_registry()
        detail = registry.show_theme(theme_name)

        if not detail:
            console.print(f"[red]主题 '{theme_name}' 不存在[/red]")
            return

        console.print(f"[bold]主题: {detail['name']}[/bold] (来源: {detail['source']})")
        if detail["aliases"]:
            console.print(f"  别名: {', '.join(detail['aliases'])}")
        console.print(f"  成员: {', '.join(detail['members'])}")
        if detail["disabled_members"]:
            console.print(f"  禁用: {', '.join(detail['disabled_members'])}")

    run_async(_run())


@themes.command("validate")
def themes_validate() -> None:
    """校验主题词典冲突。"""
    async def _run() -> None:
        from src.services.theme_registry import ThemeRegistryService

        db = await get_db()
        service = ThemeRegistryService(db)
        registry = await service.get_registry()
        issues = registry.validate()

        if not issues:
            console.print("[green]无冲突[/green]")
            return

        for issue in issues:
            console.print(f"[yellow][{issue['type']}] {issue['message']}[/yellow]")

    run_async(_run())


@themes.command("add")
@click.option("--theme", "theme_name", required=True, help="主题名")
@click.option("--member", required=True, help="主题词")
def themes_add(theme_name: str, member: str) -> None:
    """手动添加主题词成员。"""
    async def _run() -> None:
        from src.services.theme_registry import ThemeRegistryService

        db = await get_db()
        service = ThemeRegistryService(db)
        result = await service.add_theme_member(theme_name, member)
        if result["action"] == "added":
            console.print(f"[green]已添加 '{member}' 到 '{theme_name}'[/green]")
        else:
            console.print(f"[red]{result.get('error', '操作失败')}[/red]")

    run_async(_run())


@themes.command("remove")
@click.option("--theme", "theme_name", required=True, help="主题名")
@click.option("--member", required=True, help="主题词")
def themes_remove(theme_name: str, member: str) -> None:
    """移除并禁用主题词成员。"""
    async def _run() -> None:
        from src.services.theme_registry import ThemeRegistryService

        db = await get_db()
        service = ThemeRegistryService(db)
        result = await service.remove_theme_member(theme_name, member)
        if result["action"] == "removed":
            console.print(f"[green]已从 '{theme_name}' 移除并禁用 '{member}'[/green]")
        else:
            console.print(f"[red]{result.get('error', '操作失败')}[/red]")

    run_async(_run())


@themes.command("ignore-term")
@click.option("--term", required=True, help="噪声词")
def themes_ignore_term(term: str) -> None:
    """将词加入噪声词表。"""
    async def _run() -> None:
        from src.services.theme_registry import ThemeRegistryService

        db = await get_db()
        service = ThemeRegistryService(db)
        result = await service.ignore_term(term)
        console.print(f"[green]已将 '{term}' 加入噪声词表[/green]")

    run_async(_run())


@themes.command("suggest")
@click.option("--days", type=int, default=10, help="回看天数")
@click.option("--no-ai", is_flag=True, default=False, help="禁用 AI 分类")
def themes_suggest(days: int, no_ai: bool) -> None:
    """生成主题词学习建议。"""
    async def _run() -> None:
        from src.services.theme_registry import ThemeRegistryService

        db = await get_db()
        service = ThemeRegistryService(db)

        ai_processor = None
        if not no_ai:
            try:
                from src.services.ai_processor import AIProcessor
                ai_processor = AIProcessor(db)
            except Exception:
                pass

        with console.status("[bold blue]生成主题词建议中...[/bold blue]"):
            result = await service.generate_theme_suggestions(
                days=days, ai_processor=ai_processor
            )

        console.print(f"[green]主题词建议生成完成[/green]")
        console.print(f"  新建建议: {result['suggestions_created']} 个")
        console.print(f"  低证据过滤: {result['candidates_filtered']} 个")

    run_async(_run())


@themes.command("suggestions")
@click.option("--status", type=str, default="pending", help="状态筛选")
def themes_suggestions(status: str) -> None:
    """查看主题词建议。"""
    async def _run() -> None:
        from src.services.theme_registry import ThemeRegistryService

        db = await get_db()
        service = ThemeRegistryService(db)
        suggestions = await service.list_theme_suggestions(status=status)

        if not suggestions:
            console.print("[yellow]暂无主题词建议[/yellow]")
            return

        table = Table(title=f"主题词建议（共 {len(suggestions)} 条）")
        table.add_column("ID", style="dim", justify="right")
        table.add_column("类型", style="cyan")
        table.add_column("词", style="green")
        table.add_column("目标主题", style="blue")
        table.add_column("置信度", justify="right")
        table.add_column("原因", style="yellow", max_width=40)

        for s in suggestions:
            table.add_row(
                str(s["id"]),
                s["suggestion_type"],
                s["term"],
                s.get("target_theme_name") or s.get("suggested_theme_name") or "-",
                f"{s.get('confidence', 0):.2f}" if s.get("confidence") else "-",
                (s.get("reason") or "-")[:40],
            )
        console.print(table)

    run_async(_run())


@themes.command("accept")
@click.argument("suggestion_id", type=int)
def themes_accept(suggestion_id: int) -> None:
    """接受主题词建议。"""
    async def _run() -> None:
        from src.services.theme_registry import ThemeRegistryService

        db = await get_db()
        service = ThemeRegistryService(db)
        result = await service.accept_theme_suggestion(suggestion_id)
        if result["action"] == "accepted":
            console.print(
                f"[green]已接受: '{result['term']}' → '{result['theme_name']}'[/green]"
            )
        else:
            console.print(f"[red]{result.get('error', '操作失败')}[/red]")

    run_async(_run())


@themes.command("ignore")
@click.argument("suggestion_id", type=int)
def themes_ignore(suggestion_id: int) -> None:
    """忽略主题词建议。"""
    async def _run() -> None:
        from src.services.theme_registry import ThemeRegistryService

        db = await get_db()
        service = ThemeRegistryService(db)
        result = await service.ignore_theme_suggestion(suggestion_id)
        if result["action"] == "ignored":
            console.print(f"[green]已忽略建议 #{suggestion_id}[/green]")
        else:
            console.print(f"[red]{result.get('error', '操作失败')}[/red]")

    run_async(_run())


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
@click.option("--no-ai", is_flag=True, default=False, help="禁用 AI 语义清洗")
def groups_suggest(days: int, no_ai: bool) -> None:
    """生成分组建议。"""
    async def _suggest() -> None:
        from src.services.sector_group_service import SectorGroupService

        db = await get_db()
        service = SectorGroupService(db)

        ai_processor = None
        if not no_ai:
            try:
                from src.services.ai_processor import AIProcessor
                ai_processor = AIProcessor(db)
            except Exception:
                pass

        with console.status("[bold blue]生成分组建议中...[/bold blue]"):
            result = await service.generate_suggestions(days=days, ai_processor=ai_processor)

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
                    confidence_str = f" ({m.get('confidence', 0):.2f})" if m.get("confidence") else ""
                    console.print(f"  {m['sector_name']} ({status_label}) -> {m.get('suggested_relation_type', 'related')}{confidence_str}")

            # 显示证据摘要
            evidence_raw = None
            async def _load_evidence(suggestion_id: int) -> str | None:
                from src.services.sector_group_service import SectorGroupService
                db = await get_db()
                service = SectorGroupService(db)
                async with service.db.get_session() as session:
                    from sqlalchemy import select
                    from src.models.schema import SectorGroupSuggestion
                    result = await session.execute(
                        select(SectorGroupSuggestion.evidence_json).where(
                            SectorGroupSuggestion.id == suggestion_id
                        )
                    )
                    return result.scalar_one_or_none()

            evidence_raw = await _load_evidence(s["id"])
            if evidence_raw:
                try:
                    evidence = json.loads(evidence_raw)
                    source = evidence.get("source", "")
                    theme = evidence.get("theme_name")
                    ai_cleaned = evidence.get("ai_cleaned", False)
                    parts = []
                    if source:
                        source_label = "行情缓存线索" if source == "market_cache" else "CLS 看盘"
                        parts.append(f"来源: {source_label}")
                    if theme:
                        parts.append(f"主题: {theme}")
                    if ai_cleaned:
                        parts.append("已 AI 清洗")
                    rejected = evidence.get("rejected_members", [])
                    if rejected:
                        parts.append(f"被剔除: {len(rejected)} 个")
                    if parts:
                        console.print(f"  [dim]{' | '.join(parts)}[/dim]")
                except (json.JSONDecodeError, TypeError):
                    pass

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
@click.option("--verbose", is_flag=True, help="显示详细诊断信息")
@click.option("--quiet", is_flag=True, help="静默模式，只显示最终汇总")
@click.option("--date", "report_date", type=str, default=None, help="报告日期 (YYYY-MM-DD)")
def groups_update(
    group_name: str | None,
    update_all: bool,
    days: int,
    force: bool,
    no_refresh_members: bool,
    force_refresh_members: bool,
    limit: int | None,
    continue_on_error: bool,
    verbose: bool,
    quiet: bool,
    report_date: str | None,
) -> None:
    """更新分组趋势。"""
    if not group_name and not update_all:
        console.print("[red]请指定 --group <名称> 或 --all[/red]")
        return

    # 解析日期
    from datetime import date as date_type

    parsed_report_date: date_type | None = None
    if report_date:
        try:
            parsed_report_date = date_type.fromisoformat(report_date)
        except ValueError:
            console.print(f"[red]日期格式错误: {report_date}，请使用 YYYY-MM-DD 格式[/red]")
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
            from src.services.sector_group_service import GroupUpdateProgressEvent

            # 收集渲染所需的中间状态
            _group_results: list[dict[str, Any]] = []
            _failed_groups: list[dict[str, Any]] = []
            _member_refresh_success = 0
            _member_refresh_failed = 0

            def _render_event(event: GroupUpdateProgressEvent) -> None:
                nonlocal _member_refresh_success, _member_refresh_failed

                if event.type == "batch_start":
                    if not quiet:
                        console.print("[bold]批量更新分组趋势[/bold]")
                        console.print(f"  交易日: {event.trade_date}")
                        console.print(f"  目标: {event.target_count} 个 active 分组")
                        console.print(f"  回看窗口: {event.lookback_window} 天")
                        if event.force_mode:
                            console.print(f"  强制模式: 是")
                        refresh_label = {
                            "skip": "跳过成员刷新",
                            "force": "强制刷新所有成员",
                            "default": "默认刷新缺失 tracked 成员",
                        }.get(event.refresh_members_mode, event.refresh_members_mode)
                        console.print(f"  成员刷新: {refresh_label}")
                        console.print()
                    return

                if event.type == "group_start":
                    if not quiet:
                        console.print(
                            f"[bold cyan][{event.group_index}/{event.group_total}] "
                            f"{event.group_name}[/bold cyan]"
                        )
                    return

                if event.type == "member_refresh_start":
                    if not quiet:
                        console.print(f"  刷新成员: {event.member_name}")
                    return

                if event.type == "member_stage":
                    # 成员板块内部阶段（证据收集、AI 生成、保存）
                    if not quiet:
                        stage_labels = {
                            "evidence": "收集板块证据...",
                            "ai": "AI 生成板块趋势...",
                            "save": "保存板块报告...",
                            "skipped": f"已跳过 ({event.action})",
                        }
                        label = stage_labels.get(event.stage, event.action or event.stage)
                        console.print(f"    {label}")
                    return

                if event.type == "member_refresh_skip":
                    if not quiet:
                        skip_reasons = {
                            "skipped_candidate": "candidate 跳过",
                            "skipped_status": "非 tracked 跳过",
                            "skipped_has_report": "今日已更新",
                        }
                        reason = skip_reasons.get(event.action, event.action)
                        console.print(f"  [dim]~ {event.member_name}: {reason}[/dim]")
                    return

                if event.type == "member_refresh_done":
                    if event.action == "updated":
                        _member_refresh_success += 1
                    if not quiet:
                        action_label = {
                            "updated": "[green]v 已更新[/green]",
                            "skipped": "[yellow]~ 已跳过[/yellow]",
                        }
                        styled = action_label.get(event.action, event.action)
                        console.print(f"  {styled} {event.member_name}")
                    return

                if event.type == "member_refresh_failed":
                    _member_refresh_failed += 1
                    if not quiet:
                        console.print(
                            f"  [red]x[/red] {event.member_name}: {event.error[:80]}"
                        )
                    return

                if event.type == "group_ai_start":
                    if not quiet:
                        console.print(f"  生成组级总结: AI 生成中...")
                    return

                if event.type == "group_evidence_start":
                    if not quiet:
                        console.print(f"  收集分组证据...")
                    return

                if event.type == "api_retry":
                    if not quiet:
                        console.print(
                            f"  [yellow]! 重试[/yellow] "
                            f"({event.attempt}/{event.max_attempts}) "
                            f"{event.error[:60]}"
                        )
                        if verbose:
                            if event.provider:
                                console.print(f"    provider: {event.provider}")
                            if event.model:
                                console.print(f"    model: {event.model}")
                            if event.base_url_host:
                                console.print(f"    host: {event.base_url_host}")
                    return

                if event.type == "group_saved" or event.type == "group_done":
                    _group_results.append({
                        "action": event.action,
                        "group_name": event.group_name,
                        "output_path": event.output_path,
                        "labels": event.labels,
                        "elapsed": event.elapsed,
                    })
                    if not quiet:
                        action_map = {
                            "updated": "[green]v 已更新[/green]",
                            "skipped": "[yellow]~ 已跳过[/yellow]",
                        }
                        styled = action_map.get(event.action, event.action)
                        console.print(f"  {styled}")
                    return

                if event.type == "group_skipped":
                    _group_results.append({
                        "action": "skipped",
                        "group_name": event.group_name,
                        "output_path": event.output_path,
                        "elapsed": 0.0,
                        "labels": {},
                    })
                    if not quiet:
                        console.print(f"  [yellow]~ 已跳过[/yellow] (今日已更新)")
                    return

                if event.type == "group_failed":
                    _failed_groups.append({
                        "group_name": event.group_name,
                        "error": event.error,
                        "action": event.action,
                    })
                    _group_results.append({
                        "action": "failed",
                        "group_name": event.group_name,
                        "error": event.error,
                        "elapsed": event.elapsed,
                        "labels": {},
                    })
                    if not quiet:
                        console.print(
                            f"  [red]x 失败[/red]: {event.error[:80]}"
                        )
                    return

                if event.type == "batch_done":
                    # ---------- 汇总表 ----------
                    if not quiet:
                        console.print()
                        console.print("[bold]批量更新完成[/bold]")

                        if _group_results:
                            table = Table(title="更新汇总")
                            table.add_column("分组", style="cyan")
                            table.add_column("状态", style="green")
                            table.add_column("标签", style="yellow")
                            table.add_column("成员刷新", style="blue", justify="right")
                            table.add_column("报告路径", style="dim")
                            table.add_column("耗时", style="dim", justify="right")

                            for r in _group_results:
                                action = r.get("action", "unknown")
                                if action == "updated":
                                    status_text = "[green]已更新[/green]"
                                elif action == "skipped":
                                    status_text = "[yellow]已跳过[/yellow]"
                                elif action == "failed":
                                    status_text = "[red]失败[/red]"
                                else:
                                    status_text = action

                                labels = r.get("labels", {})
                                label_parts = []
                                if labels.get("trend_status"):
                                    label_parts.append(labels["trend_status"])
                                label_text = " ".join(label_parts) if label_parts else "-"

                                console.print()  # spacing before table
                                break  # 只用来判断是否非空

                            for r in _group_results:
                                action = r.get("action", "unknown")
                                if action == "updated":
                                    status_text = "[green]已更新[/green]"
                                elif action == "skipped":
                                    status_text = "[yellow]已跳过[/yellow]"
                                elif action == "failed":
                                    status_text = f"[red]失败[/red]"
                                else:
                                    status_text = action

                                labels = r.get("labels", {})
                                label_parts = []
                                if labels.get("trend_status"):
                                    label_parts.append(labels["trend_status"])
                                if labels.get("strength_level") and verbose:
                                    label_parts.append(labels["strength_level"])
                                label_text = " ".join(label_parts) if label_parts else "-"

                                table.add_row(
                                    r.get("group_name", "-"),
                                    status_text,
                                    label_text,
                                    "-",  # member refresh per-group (not tracked here)
                                    r.get("output_path") or "-",
                                    format_elapsed_time(r.get("elapsed", 0)),
                                )

                            console.print(table)

                        # 统计
                        console.print()
                        console.print(f"  成功: [green]{event.success_count}[/green]")
                        console.print(f"  跳过: [yellow]{event.skipped_count}[/yellow]")
                        console.print(f"  失败: [red]{event.failed_count}[/red]")
                        if not no_refresh_members:
                            console.print(
                                f"  成员刷新成功: [green]{event.member_refresh_success}[/green]"
                            )
                            if event.member_refresh_failed > 0:
                                console.print(
                                    f"  成员刷新失败: [red]{event.member_refresh_failed}[/red]"
                                )
                    else:
                        # quiet 模式：只输出一行汇总
                        parts = [
                            f"success={event.success_count}",
                            f"skipped={event.skipped_count}",
                            f"failed={event.failed_count}",
                        ]
                        if not no_refresh_members:
                            parts.append(f"member_refresh_failed={event.member_refresh_failed}")
                        console.print(" ".join(parts))

                    # 失败重试建议
                    if _failed_groups and not quiet:
                        console.print()
                        console.print("[bold]可重试:[/bold]")
                        for fg in _failed_groups:
                            gname = fg["group_name"]
                            if "member_refresh" in fg.get("error", "").lower():
                                console.print(
                                    f"  wchat ai sector-trends groups update "
                                    f"--group {gname} --no-refresh-members --force"
                                )
                            else:
                                console.print(
                                    f"  wchat ai sector-trends groups update "
                                    f"--group {gname} --force"
                                )

                    if not quiet:
                        console.print()
                        console.print(f"[dim]总耗时: {format_elapsed_time(event.elapsed)}[/dim]")
                    return

            result = await service.update_all_group_trends(
                ai_processor=ai_processor,
                force=force,
                no_refresh_members=no_refresh_members,
                force_refresh_members=force_refresh_members,
                days=days,
                continue_on_error=continue_on_error,
                limit=limit,
                progress_callback=_render_event,
                report_date=parsed_report_date,
            )
            return

        # 单分组更新 - 阶段式输出
        from src.services.sector_group_service import SectorGroupService

        end_date = parsed_report_date or service._get_latest_trade_date()

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
            report_date=parsed_report_date,
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


# ---------------------------------------------------------------------------
# 趋势矩阵命令
# ---------------------------------------------------------------------------


@sector_trends.group("matrix")
def matrix() -> None:
    """趋势矩阵视图。"""
    pass


@matrix.command("sectors")
@click.option("--latest", is_flag=True, help="仅显示最新快照")
@click.option("--dates", "max_dates", type=int, default=5, help="日期列数（默认 5）")
@click.option("--export", "export_path", type=str, default=None, help="导出 Markdown 路径")
def matrix_sectors(latest: bool, max_dates: int, export_path: str | None) -> None:
    """板块趋势矩阵。"""
    async def _run() -> None:
        from src.services.trend_matrix_render import (
            export_markdown,
            render_sector_matrix_markdown,
            render_sector_matrix_rich,
        )
        from src.services.trend_matrix_service import TrendMatrixService

        db = await get_db()
        service = TrendMatrixService(db)

        with console.status("[bold blue]构建板块矩阵...[/bold blue]"):
            rows, dates = await service.build_sector_matrix(
                latest_only=latest,
                max_dates=max_dates,
            )

        if not rows:
            console.print("[yellow]暂无板块趋势数据[/yellow]")
            return

        table = render_sector_matrix_rich(rows, dates)
        console.print(table)

        if export_path is not None:
            from pathlib import Path

            md = render_sector_matrix_markdown(rows, dates)
            path = export_markdown(md, Path(export_path) if export_path else None)
            console.print(f"[green]已导出: {path}[/green]")

    run_async(_run())


@matrix.command("groups")
@click.option("--latest", is_flag=True, help="仅显示最新快照")
@click.option("--dates", "max_dates", type=int, default=5, help="日期列数（默认 5）")
@click.option("--export", "export_path", type=str, default=None, help="导出 Markdown 路径")
def matrix_groups(latest: bool, max_dates: int, export_path: str | None) -> None:
    """分组趋势矩阵。"""
    async def _run() -> None:
        from src.services.trend_matrix_render import (
            export_markdown,
            render_group_matrix_markdown,
            render_group_matrix_rich,
        )
        from src.services.trend_matrix_service import TrendMatrixService

        db = await get_db()
        service = TrendMatrixService(db)

        with console.status("[bold blue]构建分组矩阵...[/bold blue]"):
            rows, dates = await service.build_group_matrix(
                latest_only=latest,
                max_dates=max_dates,
            )

        if not rows:
            console.print("[yellow]暂无分组趋势数据[/yellow]")
            return

        table = render_group_matrix_rich(rows, dates)
        console.print(table)

        if export_path is not None:
            from pathlib import Path

            md = render_group_matrix_markdown(rows, dates)
            path = export_markdown(md, Path(export_path) if export_path else None)
            console.print(f"[green]已导出: {path}[/green]")

    run_async(_run())


@matrix.command("expand")
@click.option("--group", "group_name", required=True, help="分组名称")
@click.option("--dates", "max_dates", type=int, default=5, help="日期列数（默认 5）")
@click.option("--export", "export_path", type=str, default=None, help="导出 Markdown 路径")
def matrix_expand(group_name: str, max_dates: int, export_path: str | None) -> None:
    """展开分组矩阵（含成员板块）。"""
    async def _run() -> None:
        from src.services.trend_matrix_render import (
            export_markdown,
            render_expanded_group_markdown,
            render_expanded_group_rich,
        )
        from src.services.trend_matrix_service import TrendMatrixService

        db = await get_db()
        service = TrendMatrixService(db)

        with console.status(f"[bold blue]构建分组展开矩阵: {group_name}...[/bold blue]"):
            result = await service.build_expanded_group_matrix(
                group_name,
                max_dates=max_dates,
            )

        if result is None:
            console.print(f"[yellow]分组 '{group_name}' 未找到[/yellow]")
            return

        # 收集日期
        all_dates = sorted(
            set(result.group_row.cells.keys())
            | {d for mr in result.member_rows for d in mr.cells.keys()},
            reverse=True,
        )[:max_dates]

        table = render_expanded_group_rich(result, all_dates)
        console.print(table)

        if export_path is not None:
            from pathlib import Path

            md = render_expanded_group_markdown(result, all_dates)
            path = export_markdown(md, Path(export_path) if export_path else None)
            console.print(f"[green]已导出: {path}[/green]")

    run_async(_run())
