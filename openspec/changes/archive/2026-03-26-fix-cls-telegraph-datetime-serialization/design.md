## Context

**当前问题**：
- `src/api/cls_roll.py:303` 的 `parse_telegraph` 方法返回 `publish_time` 为 `datetime` 对象
- 该数据流经 `finance.py:668` → `market_analyzer.py:185`，在 `json.dumps()` 时失败
- 错误：`TypeError: Object of type datetime is not JSON serializable`

**现有实践**：
- `finance.py:637` 的 `fetch_time` 已使用 `.isoformat()` 转换为字符串
- 这表明项目中已有使用 ISO 字符串格式的先例

**数据使用场景**：
1. **AI Processor** (`ai_processor.py:661`) - 用于 prompt 格式化（f-string）
2. **Market Analyzer** (`market_analyzer.py:185`) - 用于 JSON 序列化

## Goals / Non-Goals

**Goals:**
- 将 `publish_time` 从 `datetime` 对象转换为 ISO 8601 格式字符串
- 解决 JSON 序列化错误，恢复市场总结功能
- 保持数据语义完整，不丢失时间精度

**Non-Goals:**
- 不修改其他时间字段的格式（如 `fetch_time` 已正确处理）
- 不引入额外的序列化逻辑或自定义 encoder
- 不修改数据库模型或存储格式

## Decisions

### Decision 1: 使用 ISO 8601 字符串格式

**选择**：在 `parse_telegraph` 方法中将 `datetime` 对象转换为 ISO 字符串

```python
# Before
publish_time = datetime.fromtimestamp(ctime) if ctime else None

# After
publish_time = datetime.fromtimestamp(ctime).isoformat() if ctime else None
```

**理由**：
1. **标准格式** - ISO 8601 是国际标准，广泛支持
2. **项目一致性** - 与 `fetch_time` 的处理方式一致
3. **JSON 友好** - 字符串可直接序列化，无需自定义 encoder
4. **可读性好** - 在 f-string 中显示为 `2026-03-26T14:30:00`，清晰明了

**替代方案**：
- ❌ 使用自定义 JSON encoder - 增加复杂度，需要在多处使用
- ❌ 使用 `str(datetime)` - 格式不规范（`2026-03-26 14:30:00`），缺乏时区信息
- ❌ 在序列化时转换 - 职责不清，应在数据源头处理

### Decision 2: 修改位置选择

**选择**：在 `cls_roll.py` 的 `parse_telegraph` 方法中转换

**理由**：
1. **职责清晰** - API 客户端应返回可直接使用的数据格式
2. **一次性修复** - 修改一处，所有使用该数据的地方都受益
3. **符合 DRY 原则** - 避免在多个使用点重复转换逻辑

**替代方案**：
- ❌ 在 `finance.py` 转换 - 职责不清（数据收集 vs 数据转换）
- ❌ 在 `market_analyzer.py` 使用 encoder - 治标不治本，其他序列化点仍会失败

## Risks / Trade-offs

### Risk 1: 向后兼容性
**风险**：其他代码可能依赖 `publish_time` 是 datetime 对象

**缓解**：
- ✅ 已验证使用场景：
  - `ai_processor.py:661` - f-string 自动调用 `str()`，datetime 和字符串都兼容
  - `market_analyzer.py:185` - JSON 序列化需要字符串
- ✅ 无破坏性变更 - ISO 字符串在所有使用场景均正常工作

### Risk 2: 时间格式显示
**风险**：用户可能不熟悉 ISO 8601 格式（`2026-03-26T14:30:00`）

**缓解**：
- ✅ ISO 格式是国际标准，专业用户应熟悉
- ✅ 如果未来需要更友好的显示，可在 UI 层格式化（不影响数据层）
- ✅ 当前在 prompt 中显示，AI 可理解任何标准时间格式

## Migration Plan

**部署步骤**：
1. 修改 `src/api/cls_roll.py:303` 一行代码
2. 运行测试验证序列化功能
3. 测试市场总结生成流程

**回滚策略**：
- 单行修改，如需回滚直接还原即可
- 无数据库变更，无需数据迁移

## Open Questions

无 - 这是一个简单明确的 bug 修复，无需额外决策。
