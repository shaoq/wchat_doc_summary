## Why

执行 `wchat market-summary` 命令时报错 `KeyError: 'cls_telegrams'`，原因是模板文件 `templates/market_summary.md` 中使用的占位符 `{cls_telegrams}` 与代码中传递的参数名 `telegraphs` 不匹配，导致模板格式化失败。

## What Changes

- **ai_processor.py**: 将 `generate_market_summary` 方法中的参数名 `telegraphs` 改为 `cls_telegrams`，与模板保持一致
- **market_analyzer.py**: 在 `generate_summary` 降级方法中添加 `cls_telegraphs` 参数，传递空字符串（降级逻辑不需要电报数据）

## Capabilities

### New Capabilities

无新能力引入。

### Modified Capabilities

无现有规格修改。此变更为代码修复，不涉及规格层面的行为变更。

## Impact

- **Affected Files**:
  - `src/services/ai_processor.py` - 参数名重命名
  - `src/services/market_analyzer.py` - 添加缺失参数
- **API**: 无公共 API 变更
- **Dependencies**: 无依赖变更
- **Systems**: 仅影响 `market-summary` CLI 命令
