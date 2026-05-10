## ADDED Requirements

### Requirement: 翻页间等待使用抖动间隔

系统 SHALL 在每次翻页请求之间等待 `base + random(0, jitter)` 秒，其中 `base` 为 `fetch_page_interval`，`jitter` 为 `fetch_page_jitter`。

#### Scenario: 翻页等待包含随机抖动
- **WHEN** 系统在抓取第 N+1 页之前执行等待
- **THEN** 实际等待时间 SHALL 大于等于 `fetch_page_interval`
- **AND** 实际等待时间 SHALL 小于等于 `fetch_page_interval + fetch_page_jitter`

#### Scenario: 翻页抖动设为 0 时退化为固定间隔
- **WHEN** `fetch_page_jitter` 配置为 0
- **THEN** 翻页间等待 SHALL 等于 `fetch_page_interval`，行为与变更前一致

### Requirement: 文章间等待使用抖动间隔

系统 SHALL 在每篇文章内容抓取之间等待 `base + random(0, jitter)` 秒，其中 `base` 为 `fetch_article_interval`，`jitter` 为 `fetch_article_jitter`。已存在的文章（跳过不抓取）不触发等待。

#### Scenario: 新文章抓取后等待包含随机抖动
- **WHEN** 系统成功抓取并保存一篇新文章后执行等待
- **THEN** 实际等待时间 SHALL 大于等于 `fetch_article_interval`
- **AND** 实际等待时间 SHALL 小于等于 `fetch_article_interval + fetch_article_jitter`

#### Scenario: 文章抖动设为 0 时退化为固定间隔
- **WHEN** `fetch_article_jitter` 配置为 0
- **THEN** 文章间等待 SHALL 等于 `fetch_article_interval`，行为与变更前一致

#### Scenario: 已存在文章不触发抖动等待
- **WHEN** 文章已存在于数据库中（状态为 "existing"）
- **THEN** 系统 SHALL 不执行抖动等待，行为不变

### Requirement: 抖动配置通过 settings 暴露

系统 SHALL 在 `Settings` 中提供 `fetch_page_jitter` 和 `fetch_article_jitter` 配置项，约束为 `ge=0, le=30`，默认值均为 3.0 秒。

#### Scenario: 使用默认抖动配置
- **WHEN** 用户未在 .env 中配置抖动参数
- **THEN** `fetch_page_jitter` SHALL 为 3.0
- **AND** `fetch_article_jitter` SHALL 为 3.0

#### Scenario: 用户自定义抖动范围
- **WHEN** 用户在 .env 中设置 `FETCH_PAGE_JITTER=5.0`
- **THEN** `fetch_page_jitter` SHALL 为 5.0
