## ADDED Requirements

### Requirement: API 签名算法

系统 SHALL 实现财联社 API 签名算法，用于验证 API 请求合法性。

签名算法:
1. 对请求参数按键名排序
2. 使用 URL 编码生成查询字符串
3. 对查询字符串计算 SHA1 哈希
4. 对 SHA1 结果计算 MD5 哈希作为最终签名

#### Scenario: 生成正确签名

- **WHEN** 给定参数 `{app: "CailianpressWeb", category: "red", last_time: "1774332705", os: "web", refresh_type: "1", rn: "20", sv: "8.4.6"}`
- **THEN** 系统生成签名 `cbb737601896bed10d48aedf2f0e08d5`

---

### Requirement: 分页获取重要电报

系统 SHALL 支持通过 `last_time` 参数分页获取 `category=red` 重要电报数据。

#### Scenario: 获取第一页数据

- **WHEN** 调用 API 且 `last_time` 为当前时间戳
- **THEN** 系统返回早于该时间的最多 `rn` 条重要电报数据

#### Scenario: 获取下一页数据

- **WHEN** 使用上一页最后一条的 `ctime` 作为 `last_time`
- **THEN** 系统返回更早的重要电报数据

---

### Requirement: 时间范围查询

系统 SHALL 支持查询指定时间范围内的重要电报数据。

#### Scenario: 查询指定时间范围

- **WHEN** 指定 `start_time` 和 `end_time`
- **THEN** 系统返回该时间范围内的所有重要电报数据

#### Scenario: 时间范围无数据

- **WHEN** 指定的时间范围内无数据
- **THEN** 系统返回空列表

---

### Requirement: CLI 命令支持

系统 SHALL 提供 CLI 命令用于查询重要电报数据。

#### Scenario: 获取最新重要电报

- **WHEN** 执行 `wchat cls-roll --limit 20`
- **THEN** 系统输出最新的 20 条重要电报

#### Scenario: 按时间范围查询

- **WHEN** 执行 `wchat cls-roll --start "2024-01-01" --end "2024-01-02"`
- **THEN** 系统输出该时间范围内的所有重要电报
