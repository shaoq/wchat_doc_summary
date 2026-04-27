## ADDED Requirements

### Requirement: 模板唯一加载
系统 SHALL 确保市场总结模板只从 `templates/market_summary.md` 加载，且加载逻辑只在 `ai_processor.py` 中实现。

#### Scenario: 模板文件存在
- **WHEN** 调用 AI 生成市场总结
- **THEN** 系统从 `templates/market_summary.md` 加载模板
- **THEN** 模板被正确格式化并传递给 LLM

#### Scenario: 模板文件不存在
- **WHEN** 调用 AI 生成市场总结
- **AND** `templates/market_summary.md` 文件不存在
- **THEN** 系统抛出 `FileNotFoundError` 异常
- **THEN** 用户看到明确的错误提示

### Requirement: AI 失败时直接报错
系统 SHALL 在 AI 调用失败时直接抛出异常，不使用降级方案。

#### Scenario: AI 调用成功
- **WHEN** 调用 AI 生成市场总结
- **AND** LLM API 返回正常响应
- **THEN** 系统返回 AI 生成的总结内容
- **THEN** 总结保存到数据库和文件

#### Scenario: AI 调用失败
- **WHEN** 调用 AI 生成市场总结
- **AND** LLM API 调用失败（网络错误、API 错误等）
- **THEN** 系统抛出异常
- **THEN** 用户看到错误信息，而非填充好的模板

### Requirement: 无降级逻辑
系统 SHALL NOT 在 AI 失败时输出填充好的模板内容。

#### Scenario: 验证无降级代码
- **WHEN** 检查 `cli.py` 中的 market-summary 命令实现
- **THEN** 不存在捕获 AI 异常后调用 `analyzer.generate_summary()` 的代码
- **THEN** 不存在 `ai_failed` 变量或类似的降级标志

## REMOVED Requirements

### Requirement: market_analyzer 模板加载
**Reason**: 模板加载逻辑统一到 `ai_processor.py`
**Migration**: 使用 `ai_processor._load_market_summary_template()` 替代

### Requirement: 降级总结生成
**Reason**: AI 失败时直接报错，不再生成降级输出
**Migration**: 确保 LLM API 配置正确，或在网络恢复后重试
