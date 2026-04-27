# Trade Date Logic Specification

## ADDED Requirements

### Requirement: Intelligent Trade Date Selection
`get_latest_trade_date()` 方法 SHALL 根据当前时间智能选择交易日:
- 在交易日当天 **09:00 之前** 调用时，返回**上一个已结束的交易日**
- 在交易日当天 **09:00 及之后** 调用时，返回**当天交易日**
- 对于非交易日。保持现有行为（往前找最近的交易日）

#### Scenario: Trade day before market open (weekday 08:30)
- **WHEN** 今天是 2026-03-26（周四，交易日）
- **AND** 当前时间是 08:30
- **THEN** `get_latest_trade_date()` 返回 2026-03-25（周三，上一个交易日）

#### Scenario: Trade day after market open (weekday 10:00)
- **WHEN** 今天是 2026-03-26（周四，交易日）
- **AND** 当前时间是 10:00
- **THEN** `get_latest_trade_date()` 返回 2026-03-26（当天）

#### Scenario: Non-trade day (Saturday)
- **WHEN** 今天是 2026-03-28（周六，非交易日）
- **AND** 当前时间是任意时间
- **THEN** `get_latest_trade_date()` 返回 2026-03-27（周五，最近交易日）

#### Scenario: Non-trade day (Sunday)
- **WHEN** 今天是 2026-03-29（周日，非交易日）
- **AND** 当前时间是任意时间
- **THEN** `get_latest_trade_date()` 返回 2026-03-27（周五，最近交易日）
