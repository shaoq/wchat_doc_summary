## Why

文章抓取的翻页间隔和文章内容抓取间隔使用固定值（均为 6s），节奏过于规律，容易被上游服务识别为自动化行为。订阅间切换已有抖动机制（`subscription_delay + jitter`），但更细粒度的文章级和翻页级间隔缺少随机性。

## What Changes

- 为翻页间隔（`fetch_page_interval`）和文章内容抓取间隔（`fetch_article_interval`）增加随机抖动
- 新增 `fetch_page_jitter` 和 `fetch_article_jitter` 配置项，与 `fetch_subscription_jitter` 模式一致
- 实际等待时间 = base + random(0, jitter)，只加不减，保证安全下限

## Capabilities

### New Capabilities

- `fetch-jitter`: 抓取间隔的随机抖动机制，覆盖翻页间和文章内容抓取间的等待

### Modified Capabilities

- `article-fetcher`: 抓取流程中的等待行为从固定间隔变更为抖动间隔

## Impact

- `config/settings.py`: 新增 2 个配置项
- `src/services/fetcher.py`: 新增抖动等待方法，替换 6 处固定间隔调用
- 测试文件: 断言需适配抖动范围
