## Why

当前 market-summary 命令存在降级逻辑：当 AI 调用失败时，会输出填充好的模板内容作为降级输出，而非直接报错。这导致用户看到的是原始 prompt 模板而非预期的总结内容。

同时，模板加载逻辑在 `ai_processor.py` 和 `market_analyzer.py` 两处重复实现，违反了单一职责原则。

## What Changes

- **BREAKING** 移除 cli.py 中 AI 生成失败时的降级逻辑，失败时直接抛出错误
- 移除 `market_analyzer.generate_summary()` 方法（降级方案的实现）
- 移除 `market_analyzer._load_template()` 方法（重复的模板加载逻辑）
- 确保模板加载和格式化只在 `ai_processor.py` 中实现

## Capabilities

### New Capabilities

无（此变更为移除功能，不引入新能力）

### Modified Capabilities

- `market-summary`: 修改失败行为，移除降级逻辑，AI 失败时直接报错

## Impact

**修改文件**:
- `src/cli.py` - 移除 try/except 降级分支和 `ai_failed` 变量
- `src/services/market_analyzer.py` - 移除 `generate_summary()` 和 `_load_template()` 方法

**行为变更**:
- AI 调用失败时，用户将看到明确的错误信息，而非填充好的模板
