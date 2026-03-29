## ADDED Requirements

### Requirement: 电报数据持久化

系统 SHALL 将抓取的财联社电报数据保存到数据库。

#### Scenario: 保存新电报

- **WHEN** 执行 `wchat cls-roll fetch` 抓取到新电报
- **THEN** 系统将电报数据保存到 `cls_telegraphs` 表

#### Scenario: 跳过已存在电报

- **WHEN** 抓取的电报 `telegraph_id` 已存在于数据库
- **THEN** 系统跳过该电报，不重复插入

---

### Requirement: 电报数据查询

系统 SHALL 支持查询已保存的电报数据。

#### Scenario: 列出所有电报

- **WHEN** 执行 `wchat cls-roll ls`
- **THEN** 系统返回数据库中的电报列表

#### Scenario: 按时间范围查询

- **WHEN** 执行 `wchat cls-roll ls --start "2024-01-01" --end "2024-01-02"`
- **THEN** 系统返回指定时间范围内的电报

#### Scenario: 按重要程度过滤

- **WHEN** 执行 `wchat cls-roll ls --level 3`
- **THEN** 系统只返回 level >= 3 的重要电报
