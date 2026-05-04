## Why

`wchat fetch --all` 当前按订阅创建时间顺序抓取，无法区分公众号的重要性。高价值公众号（如市场要闻类）应优先抓取以确保时效性，低优先级的可以后抓。

## What Changes

- Feed 模型新增 `weight` 字段（Integer, 取值 0/5/10, 默认 5）
- 新增 `list_subscriptions_for_fetch()` 方法，按权重排序返回抓取队列
- `fetch_all()` 使用新方法替换原有 `list_subscriptions()`
- `wchat sub ls` 表格新增"权重"列
- `wchat sub info` 显示权重信息
- 新增 CLI 命令 `wchat sub set-weight <mp_id> <0|5|10>` 设置权重

## Capabilities

### New Capabilities

- `feed-weight`: Feed 权重管理 — 定义权重字段、排序策略、CLI 交互

### Modified Capabilities

- `subscription`: 订阅列表展示增加权重列
- `article-fetcher`: `fetch_all` 排序策略从创建时间改为权重优先

## Impact

- 数据库: `feeds` 表新增 `weight` 列 (ALTER TABLE, 默认值 5)
- 模型: `Feed` 新增 `weight` 字段
- 服务层: `SubscriptionService` 新增方法
- CLI: `subscription` 命令组新增 `set-weight` 子命令, `ls`/`info` 展示调整
- 向后兼容: 默认值 5 确保现有订阅行为不变
