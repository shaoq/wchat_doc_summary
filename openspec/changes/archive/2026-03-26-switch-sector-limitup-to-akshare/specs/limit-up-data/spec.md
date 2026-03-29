## ADDED Requirements

### Requirement: 获取涨停股数据

系统 SHALL 使用 akshare `stock_zt_pool_em(date)` 接口获取当日涨停股票列表。

#### Scenario: 交易日成功获取涨停股
- **WHEN** 在交易日内调用涨停股获取接口
- **THEN** 系统返回当日所有涨停股列表
- **AND** 每只股票包含代码、名称、涨跌幅、连板数等字段

#### Scenario: 非交易日返回空列表
- **WHEN** 在非交易日调用涨停股获取接口
- **THEN** 系统返回空列表

#### Scenario: 获取连板股
- **WHEN** 涨停股数据中包含连板数大于 1 的股票
- **THEN** 系统能够筛选并返回连板股列表

### Requirement: 涨停股数据字段

系统 SHALL 从 akshare 返回的涨停池数据中提取以下字段：

#### Scenario: 完整字段提取
- **WHEN** 获取到涨停股原始数据
- **THEN** 系统提取以下字段：
  - 代码 (代码)
  - 名称 (名称)
  - 涨跌幅 (涨跌幅)
  - 连板数 (连板数)
  - 封板时间 (首次封板时间)
  - 所属行业 (所属行业)

#### Scenario: 处理空数据
- **WHEN** akshare 返回空 DataFrame
- **THEN** 系统返回空列表而不是抛出异常
