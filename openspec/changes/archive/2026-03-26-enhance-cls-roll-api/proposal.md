## Why

现有财联社电报客户端 (`cls_telegraph.py`) 使用 `/nodeapi/telegraphs` 端点，只能获取最新 50 条数据，且无法按时间范围查询历史记录。为了支持获取完整的重要电报历史数据，需要实现财联社 `roll/get_roll_list` API 的签名算法和时间范围查询功能。

## What Changes

- 新增财联社 API 签名算法 (`sorted → urlencode → SHA1 → MD5`)
- 新增 `CLSRollClient` 类，支持 `category=red` (重要电报) 数据获取
- 支持按时间范围分页拉取历史数据
- 支持 CLI 命令行查询指定时间段的重要电报

## Capabilities

### New Capabilities

- `cls-roll-api`: 财联社 roll API 客户端，包含签名算法、分页拉取、时间范围查询功能

### Modified Capabilities

- None (新功能，不修改现有能力)

## Impact

- 新增 `src/api/cls_roll.py` 文件
- 修改 `src/cli.py` 添加新的 CLI 命令
- 可能新增 `src/services/cls_roll_service.py` 用于批量数据获取逻辑
