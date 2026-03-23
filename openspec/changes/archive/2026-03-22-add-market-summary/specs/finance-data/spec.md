## ADDED Requirements

### Requirement: 系统应能获取 A 股指数数据

系统 SHALL 通过财经 API 获取主要 A 股指数的实时/历史数据。

#### Scenario: 获取上证指数
- **WHEN** 系统请求上证指数数据
- **THEN** 返回上证指数的当日开盘、收盘、涨跌幅

#### Scenario: 获取深证成指
- **WHEN** 系统请求深证成指数据
- **THEN** 返回深证成指的当日开盘、收盘、涨跌幅

#### Scenario: 获取创业板指
- **WHEN** 系统请求创业板指数据
- **THEN** 返回创业板指的当日开盘、收盘、涨跌幅

---

### Requirement: 系统应能获取成交量数据

系统 SHALL 获取沪深两市成交额数据。

#### Scenario: 获取两市成交额
- **WHEN** 系统请求成交量数据
- **THEN** 返回沪市和深市的当日成交额（亿元）

---

### Requirement: 系统应能获取涨跌统计

系统 SHALL 获取当日个股涨跌统计数据。

#### Scenario: 获取涨跌家数
- **WHEN** 系统请求涨跌统计
- **THEN** 返回上涨家数、下跌家数、平盘家数

---

### Requirement: 系统应能获取板块数据

系统 SHALL 获取当日板块涨跌排行。

#### Scenario: 获取涨幅板块
- **WHEN** 系统请求板块涨幅榜
- **THEN** 返回涨幅前 N 的板块名称和涨幅

#### Scenario: 获取跌幅板块
- **WHEN** 系统请求板块跌幅榜
- **THEN** 返回跌幅前 N 的板块名称和跌幅

---

### Requirement: 系统应能获取连板数据

系统 SHALL 获取当日个股连板统计。

#### Scenario: 获取连板个股
- **WHEN** 系统请求连板数据
- **THEN** 返回 2 连板及以上的个股列表（股票名称、代码、连板数）

---

### Requirement: 系统应能处理 API 错误

系统 SHALL 优雅处理财经 API 调用失败的情况。

#### Scenario: API 超时
- **WHEN** 财经 API 请求超时
- **THEN** 系统记录错误并返回空数据，不中断总结生成

#### Scenario: API 不可用
- **WHEN** 财经 API 不可用
- **THEN** 系统提示用户使用 `--offline` 模式
