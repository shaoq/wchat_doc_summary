## Context

当前 `extract_stocks` 命令使用 `console.print` 输出每篇文章的处理结果，无法显示整体进度。需要使用 Rich 的 Progress 组件来增强用户体验。

## Goals / Non-Goals

**Goals:**
- 显示进度条和处理进度（N/M）
- 显示当前处理的文章标题
- 实时更新成功/跳过/失败计数

**Non-Goals:**
- 不改变命令的其他行为
- 不添加日志文件输出

## Decisions

### 使用 Rich Progress 组件

**选择**: 使用 `rich.progress.Progress` 配合自定义列
**实现**:
```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    console=console,
) as progress:
    task = progress.add_task("提取股票信息", total=len(article_ids))
    # 处理循环中更新进度
```

**理由**: Rich 已在项目中使用，无需引入新依赖；Progress 组件功能完善，支持自定义列。

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 进度条可能与日志输出冲突 | 使用 Progress 的 transient 模式或确保日志输出在 Progress 上下文外 |
