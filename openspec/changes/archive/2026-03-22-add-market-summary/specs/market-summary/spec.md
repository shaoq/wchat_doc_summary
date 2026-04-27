## ADDED Requirements

### Requirement: 系统应能判断 A 股交易日

系统 SHALL 正确判断给定日期是否为 A 股交易日，排除周末和中国法定节假日。

#### Scenario: 工作日判断
- **WHEN** 用户查询一个普通工作日（如 2026-03-23，周一）
- **THEN** 系统返回该日期为交易日

#### Scenario: 周末判断
- **WHEN** 用户查询周末日期（如 2026-03-22，周日）
- **THEN** 系统返回该日期为非交易日

#### Scenario: 节假日判断
- **WHEN** 用户查询法定节假日（如 2026-01-01，元旦）
- **THEN** 系统返回该日期为非交易日

#### Scenario: 获取最近交易日
- **WHEN** 当前日期为非交易日
- **THEN** 系统返回最近一个已过去的交易日

---

### Requirement: 系统应能生成市场总结

系统 SHALL 根据模板格式生成结构化的市场总结报告。

#### Scenario: 自动生成总结
- **WHEN** 用户执行 `wchat ai market-summary` 命令
- **THEN** 系统生成包含市场概览和市场消息的总结

#### Scenario: 指定日期生成
- **WHEN** 用户执行 `wchat ai market-summary --date 2026-03-21`
- **THEN** 系统生成指定日期的市场总结

#### Scenario: 离线模式
- **WHEN** 用户执行 `wchat ai market-summary --offline`
- **THEN** 系统仅使用已抓取的公众号文章生成总结，不联网获取行情

---

### Requirement: 系统应能保存市场总结

系统 SHALL 将生成的市场总结同时保存到数据库和文件。

#### Scenario: 保存到数据库
- **WHEN** 市场总结生成完成
- **THEN** 总结内容保存到 `market_summaries` 表

#### Scenario: 保存到文件
- **WHEN** 市场总结生成完成
- **THEN** 总结内容保存到 `output/market_summaries/YYYY-MM-DD.md` 文件

#### Scenario: 避免重复生成
- **WHEN** 用户对同一交易日重复执行命令
- **THEN** 系统提示已存在总结，询问是否覆盖

---

### Requirement: 系统应支持可编辑模板

系统 SHALL 使用外部模板文件，用户可自定义总结格式。

#### Scenario: 使用默认模板
- **WHEN** 模板文件 `templates/market_summary.md` 存在
- **THEN** 系统按模板格式生成总结

#### Scenario: 用户自定义模板
- **WHEN** 用户修改 `templates/market_summary.md` 文件
- **THEN** 后续生成的总结使用新模板格式
