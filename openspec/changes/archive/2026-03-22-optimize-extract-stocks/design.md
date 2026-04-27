## Context

当前 `batch_extract_stocks` 使用 `asyncio.gather` 无限制并发，每个任务需要获取数据库连接。SQLite 默认连接池为 5+10 overflow，当文章数 > 15 时导致连接池耗尽。

## Goals / Non-Goals

**Goals:**
- 限制并发数，防止连接池耗尽
- 默认保存输出文件，提升用户体验

**Non-Goals:**
- 不修改数据库连接池配置
- 不改变输出文件格式

## Decisions

### 1. 并发控制方案：Semaphore

**选择**: 使用 `asyncio.Semaphore(3)`
**备选方案**:
- 分批处理（batch）: 实现更复杂，需要等待整批完成
- 连接池扩容: 治标不治本，仍有上限

**理由**: Semaphore 是 Python 原生方案，实现简单，能有效控制并发，且不需要等待整批完成。

### 2. 默认输出路径

**选择**: `output/extract_stocks/{mp_id}_stocks_{YYMMDD}.txt`
**格式示例**: `output/extract_stocks/MP_WXS_3917032509_stocks_260322.txt`

**理由**:
- 按功能划分子目录，便于管理
- 文件名包含公众号 ID 和日期，易于识别和追溯
- 使用 YYMMDD 格式，简洁且排序友好

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| 并发数 3 可能影响处理速度 | 可接受，稳定性优先；后续可配置化 |
| 默认输出可能覆盖同名文件 | 同一天同一公众号的输出会覆盖，符合预期（保留最新） |
