## ADDED Requirements

### Requirement: 获取行业板块实时行情

系统 SHALL 使用 akshare `stock_sector_spot()` 接口获取 A 股行业板块的实时行情数据。

#### Scenario: 交易日成功获取板块数据
- **WHEN** 在交易时间内调用板块数据获取接口
- **THEN** 系统返回至少 40 个行业板块的数据
- **AND** 每个板块包含名称、涨跌幅、总成交额等字段

#### Scenario: 按涨跌幅排序板块
- **WHEN** 获取板块数据后进行排序
- **THEN** 系统能够按涨跌幅升序或降序排列板块列表

#### Scenario: 获取涨幅榜和跌幅榜
- **WHEN** 调用 get_sector_data(top_n=5)
- **THEN** 系统返回涨幅前 5 和跌幅前 5 的板块

### Requirement: 板块数据字段映射

系统 SHALL 将 akshare 返回的板块数据映射到标准数据结构。

#### Scenario: 字段完整映射
- **WHEN** 获取到板块原始数据
- **THEN** 系统映射以下字段：
  - 板块名称 (板块) -> name
  - 涨跌幅 -> change_pct
  - 总成交额 -> amount

#### Scenario: 处理空数据
- **WHEN** akshare 返回空 DataFrame
- **THEN** 系统返回空列表而不是抛出异常
