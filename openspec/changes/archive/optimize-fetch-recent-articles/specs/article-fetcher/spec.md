## MODIFIED Requirements

### Requirement: fetch_feed 支持时间范围过滤

`fetch_feed` 方法 SHALL 支持通过 `days` 参数限制抓取时间范围，默认只抓取最近 5 天的文章。

```python
async def fetch_feed(
    self,
    mp_id: str,
    max_pages: int = 5,
    days: int | None = 5  # 新增参数，None 表示不限制
) -> list[Article]:
    """抓取指定公众号的文章。

    Args:
        mp_id: 公众号 ID
        max_pages: 最大抓取页数
        days: 抓取最近 N 天的文章，None 表示不限制

    Returns:
        抓取到的文章列表
    """
```

#### Scenario: 默认抓取最近 5 天文章
- **WHEN** 调用 `fetch_feed("MP_WXS_xxx")` 不指定 days 参数
- **THEN** 系统只返回最近 5 天内发布的文章

#### Scenario: 指定抓取天数
- **WHEN** 调用 `fetch_feed("MP_WXS_xxx", days=10)`
- **THEN** 系统只返回最近 10 天内发布的文章

#### Scenario: 抓取全部历史文章
- **WHEN** 调用 `fetch_feed("MP_WXS_xxx", days=None)`
- **THEN** 系统返回所有历史文章（原有行为）

### Requirement: CLI fetch 命令支持 --days 和 --full 参数

`wchat fetch` 命令 SHALL 支持 `--days` 和 `--full` 参数控制抓取范围。

```bash
# 抓取所有订阅，最近 5 天（默认）
wchat fetch --all

# 抓取所有订阅，最近 10 天
wchat fetch --all --days 10

# 抓取所有订阅，全部历史
wchat fetch --all --full

# 抓取指定公众号，最近 5 天（默认）
wchat fetch MP_WXS_xxx

# 抓取指定公众号，全部历史
wchat fetch MP_WXS_xxx --full
```

#### Scenario: 默认抓取最近 5 天
- **WHEN** 用户执行 `wchat fetch --all`
- **THEN** 系统抓取所有订阅最近 5 天的文章
- **AND** 显示提示信息 "抓取范围: 最近 5 天"

#### Scenario: 指定抓取天数
- **WHEN** 用户执行 `wchat fetch --all --days 10`
- **THEN** 系统抓取所有订阅最近 10 天的文章
- **AND** 显示提示信息 "抓取范围: 最近 10 天"

#### Scenario: 全量抓取
- **WHEN** 用户执行 `wchat fetch --all --full`
- **THEN** 系统抓取所有订阅的全部历史文章
- **AND** 显示提示信息 "抓取范围: 全部历史"
