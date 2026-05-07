## Why

`wchat fetch --all` 限流中断后重新执行，总是从第一个公众号开始抓取，导致排序靠后的公众号永远无法被同步。核心原因：批量抓取没有进度持久化，每次运行都从头开始。

## What Changes

- 新增 `fetch_batches` 表，记录每个订阅每日的抓取状态（pending / done）
- `fetch_all` 方法改为基于 batch 的断点续传：同日内重跑自动跳过已完成（done）的订阅，从 pending 状态的订阅继续
- 每日自动重置：`batch_date = date.today()`，新的一天自动创建全新 batch
- CLI 新增 `--force` 参数，允许忽略 batch 强制全新开始
- 当日新增的订阅自动补充到 batch 中（pending 状态）
- 所有订阅已完成时给出"今日已同步完成"提示，避免浪费 API 调用

## Capabilities

### New Capabilities

- `fetch-batch-progress`: 批量抓取的每日进度跟踪与断点续传机制

### Modified Capabilities

- `article-fetcher`: `fetch_all` 方法需集成 batch 逻辑，改变抓取队列的选取方式
- `subscription`: `list_subscriptions_for_fetch` 排序需配合 batch 状态查询

## Impact

- **数据库**: 新增 `fetch_batches` 表（需 schema 迁移）
- **FetcherService**: `fetch_all` 方法核心逻辑重构
- **CLI**: `subscription.py` fetch 命令新增 `--force` 选项
- **向后兼容**: `wchat fetch <mp_id>` 不受影响，仅 `fetch --all` 使用 batch 机制
