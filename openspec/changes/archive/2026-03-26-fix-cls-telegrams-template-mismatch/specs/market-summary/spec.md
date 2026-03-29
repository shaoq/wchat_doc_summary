## ADDED Requirements

### Requirement: 模板参数名一致性

`market-summary` 命令中，代码传递给模板的参数名 SHALL 与模板文件中定义的占位符名称完全一致。

#### Scenario: AI 生成路径使用正确的参数名

- **WHEN** 执行 `wchat market-summary` 命令
- **AND** AI 处理器成功调用
- **THEN** `ai_processor.generate_market_summary()` 方法 SHALL 使用 `cls_telegraphs` 作为参数名传递电报数据

#### Scenario: 降级路径提供空电报数据

- **WHEN** 执行 `wchat market-summary` 命令
- **AND** AI 处理器调用失败，降级到 `market_analyzer.generate_summary()`
- **THEN** 降级方法 SHALL 传递 `cls_telegraphs=""` 以避免 KeyError
