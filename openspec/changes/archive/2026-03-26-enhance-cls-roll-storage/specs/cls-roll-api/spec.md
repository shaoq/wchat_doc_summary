## MODIFIED Requirements

### Requirement: CLI fetch 命令

系统 SHALL 提供 `wchat cls-roll fetch` 命令用于抓取并保存电报数据。

#### Scenario: 抓取默认分类

- **WHEN** 执行 `wchat cls-roll fetch`
- **THEN** 系统抓取 category=red 的重要电报并保存到数据库
- **THEN** 系统输出统计信息（新增数量、跳过数量）

#### Scenario: 抓取指定分类

- **WHEN** 执行 `wchat cls-roll fetch --category all`
- **THEN** 系统抓取指定分类的电报

#### Scenario: 按时间范围抓取

- **WHEN** 执行 `wchat cls-roll fetch --start "2024-01-01" --end "2024-01-02"`
- **THEN** 系统抓取指定时间范围内的电报

---

## REMOVED Requirements

### Requirement: CLI list 命令

**Reason**: 重命名为 fetch，语义更准确
**Migration**: 使用 `wchat cls-roll fetch` 替代 `wchat cls-roll list`
