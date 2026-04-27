## Why

当前 `wchat cls-roll list` 命令只实时获取并显示数据，无法持久化保存。需要将抓取的电报数据保存到数据库以便后续查询和分析，同时重构 CLI 命令使其更符合语义（fetch 表示抓取保存，ls 表示查看）。

## What Changes

- **BREAKING**: `wchat cls-roll list` → `wchat cls-roll fetch` (抓取并保存到数据库)
- 新增 `wchat cls-roll ls` 命令用于查看已保存的电报
- 新增 `CLSTelegraph` 数据库表存储电报数据
- 新增 `--category` 参数支持不同分类（默认 red）
- 实现基于 `telegraph_id` 的去重（跳过已存在）

## Capabilities

### New Capabilities

- `cls-telegraph-storage`: 财联社电报数据持久化存储，包含数据库模型、去重逻辑、查询功能

### Modified Capabilities

- `cls-roll-api`: CLI 命令行为变更（list → fetch），新增 category 参数

## Impact

- 新增 `src/models/schema.py` 中的 `CLSTelegraph` 模型
- 修改 `src/cli.py` 中的 cls-roll 命令组
- 新增 `src/services/cls_telegraph_service.py` 用于数据存储和查询逻辑
