## Why

当前 `cls_roll.py` 的 `parse_telegraph` 方法返回的 `publish_time` 是 datetime 对象，导致在 `market_analyzer.py` 中调用 `json.dumps()` 时抛出 `TypeError: Object of type datetime is not JSON serializable` 错误，使得市场总结功能无法正常保存。

这个问题在执行 `wchat ai market-summary` 命令时触发，阻塞了整个市场总结生成流程。

## What Changes

- 修改 `src/api/cls_roll.py` 的 `parse_telegraph` 方法，将 `publish_time` 从 datetime 对象转换为 ISO 8601 格式字符串
- 保持数据语义不变（时间信息完整保留），仅改变序列化格式
- 与 `finance.py` 中 `fetch_time` 的处理方式保持一致（已使用 `.isoformat()`）

## Capabilities

### New Capabilities

- `cls-telegraph-data-format`: 定义财联社电报数据的序列化格式要求，确保所有时间字段为 JSON 可序列化的字符串格式

### Modified Capabilities

无（这是新规范的引入，不修改现有 spec 的需求）

## Impact

**影响范围**：
- `src/api/cls_roll.py` - 修改 `parse_telegraph` 方法的返回格式
- `src/services/ai_processor.py` - 使用 `publish_time` 的地方（f-string 格式化，兼容 ISO 字符串）
- `src/services/market_analyzer.py` - 保存 `data_sources` 时不再抛出序列化错误

**向后兼容性**：
- ✅ 完全兼容 - ISO 字符串在 f-string 中显示效果与 datetime 对象相同
- ✅ 无破坏性变更 - 所有使用场景（prompt 格式化、JSON 序列化）均兼容

**风险评估**：
- 风险极低，仅改变数据表示形式，不改变语义
