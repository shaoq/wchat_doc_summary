## Why

`extract-stocks` 命令使用 `asyncio.gather` 同时启动所有文章的处理任务，当文章数量超过数据库连接池大小（SQLite 默认 5+10 overflow=15）时，会导致 "QueuePool limit reached" 错误。同时，当前输出文件是可选的，用户需要手动指定路径，缺乏默认保存机制。

## What Changes

- 添加并发控制：使用 `asyncio.Semaphore` 限制并发数为 3，防止连接池耗尽
- 添加默认输出：自动保存到 `output/extract_stocks/{mp_id}_stocks_{YYMMDD}.txt`
- 用户仍可通过 `-o` 参数覆盖默认输出路径

## Capabilities

### New Capabilities

- `concurrency-control`: 批量处理任务时的并发控制能力

### Modified Capabilities

- `extract-stocks`: 添加默认输出路径，行为变更（自动保存文件）

## Impact

- **受影响代码**:
  - `src/services/ai_processor.py`：`batch_extract_stocks` 方法添加并发控制
  - `src/cli.py`：`extract_stocks` 命令添加默认输出逻辑
- **新增目录**：`output/extract_stocks/`
