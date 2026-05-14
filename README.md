# wchat

微信公众号文章订阅与 A 股市场分析 CLI。

这个项目主要做 4 件事：

- 订阅公众号并抓取文章
- 在本地数据库中管理文章与订阅
- 对文章做 AI 摘要、关键词、分类、情感、股票提取
- 结合市场数据、财联社数据和文章，生成 `market-summary`

## 功能概览

- 微信 RSS SaaS 文章同步（推荐路径）
- 微信读书登录（兼容路径）
- 公众号订阅管理
- 文章抓取、查看、导出
- AI 摘要、关键词、分类、情感分析
- 文章股票提取与股票反查
- A 股市场总结
- 财联社电报 / 看盘数据抓取与查看

## 安装

要求：

- Python 3.10+

推荐在项目根目录执行：

```bash
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
```

安装完成后可以直接使用：

```bash
wchat --help
```

如果你还没有安装到当前环境，也可以直接用模块方式运行：

```bash
python -m src.cli --help
```

下文默认都用 `wchat` 举例，`python -m src.cli` 等价。

## 配置

项目通过 `.env` 读取配置。最小可用配置示例：

```bash
# RSS SaaS 配置（推荐路径）
ARTICLE_LIST_PROVIDER=rss
WECHAT_RSS_API_KEY=你的RSS服务API密钥

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./data/wchat.db

# AI 处理（wchat ai ... 命令需要）
LLM_BASE_URL=https://api.anthropic.com
LLM_API_KEY=你的密钥
LLM_MODEL=claude-3-5-haiku-latest
```

### 配置说明

| 配置项 | 说明 |
|--------|------|
| `ARTICLE_LIST_PROVIDER` | 文章列表 Provider，推荐 `rss`；兼容 `weread` / `wechat2rss` |
| `WECHAT_RSS_API_KEY` | 微信 RSS SaaS 全局 API Key（放在 `.env` 中） |
| `RSS_CONTENT_MODE` | 内容模式: `feed_only` / `prefer_feed`（默认）/ `fetch_missing` |
| `RSS_AUTO_SUBSCRIBE_DISCOVERED_FEEDS` | 是否自动订阅 RSS 中发现的未知公众号（默认 `false`） |
| `RSS_DISCOVERED_FEED_DEFAULT_STATUS` | 自动发现的公众号默认状态: `active` / `inactive`（默认） |
| `RSS_UNKNOWN_FEED_POLICY` | 未知公众号处理策略: `skip`（默认）/ `create_placeholder` |

说明：

- `DATABASE_URL` 默认就是 `sqlite+aiosqlite:///./data/wchat.db`
- 使用 RSS 路径时，`subscribe` / `fetch` 不需要 `wchat login`
- RSS Feed URL 通过 `wchat source add` 管理为本地源，不写在 `.env` 里
- 只有 `wchat ai ...` 相关命令需要 `LLM_API_KEY`
- WeRead 路径仍然需要 `wchat login`

## 初始化

第一次使用先初始化数据库：

```bash
wchat init
```

查看主命令：

```bash
wchat --help
wchat ai --help
wchat cls --help
wchat source --help
```

## 最常用的使用流程

### 1. 配置 RSS 源（推荐）

RSS SaaS 路径不需要微信读书登录。

#### 单个聚合源模式

如果你有一个包含所有公众号的 RSS Feed：

```bash
wchat source add 全部 https://your-rss-service.com/feed/all
```

#### 多个分类源模式

如果按分类有多个 RSS Feed：

```bash
wchat source add 财经 https://your-rss-service.com/feed/finance
wchat source add 科技 https://your-rss-service.com/feed/tech
wchat source add 投资 https://your-rss-service.com/feed/invest
```

查看已配置的源：

```bash
wchat source list
```

查看源健康状态：

```bash
wchat source health
```

#### 自动发现公众号

当 RSS Feed 包含尚未手动订阅的公众号文章时，系统可以自动创建本地订阅：

```bash
# 在 .env 中启用自动发现
RSS_AUTO_SUBSCRIBE_DISCOVERED_FEEDS=true
RSS_DISCOVERED_FEED_DEFAULT_STATUS=inactive   # 发现后先不激活
```

启用后，`wchat source fetch` 会：
1. 从 RSS Feed 提取公众号身份（优先使用 `__biz` ID，回退到作者名称）
2. 匹配已有的本地订阅（避免重复）
3. 创建新订阅并记录发现来源
4. 在输出中报告新发现的公众号

发现的公众号会出现在 `wchat ls` 列表中。如果默认状态是 `inactive`，需要手动启用：

```bash
# 目前通过重新订阅来激活（保留元数据）
# 或者在 .env 中设置 RSS_DISCOVERED_FEED_DEFAULT_STATUS=active
```

### 2. 从 RSS 源抓取文章

```bash
# 从所有活跃 RSS 源抓取
wchat source fetch
```

### 3. WeRead 路径（兼容）

如果你仍然使用微信读书代理：

```bash
# 登录
wchat login

# 订阅公众号（通过文章 URL）
wchat subscribe "https://mp.weixin.qq.com/s/xxxx"

# 抓取
wchat fetch MP_WXS_xxx
```

### 4. 查看订阅和文章

查看订阅列表（包含 RSS 源关联）：

```bash
wchat ls
```

`wchat ls` 显示每个订阅关联的 RSS 源名称。如果公众号出现在多个分类源中，会列出所有关联源。

查看某个订阅详情：

```bash
wchat info MP_WXS_xxx
```

查看某个公众号已抓取文章：

```bash
wchat show MP_WXS_xxx
```

导出文章：

```bash
wchat export --format json --output articles.json
wchat export --format markdown --output articles.md
```

### 5. 抓取所有订阅

```bash
# 抓取所有订阅最近 5 天文章
wchat fetch --all

# 抓取所有订阅全部历史
wchat fetch --all --full
```

## AI 使用

前提：`.env` 中已配置 `LLM_API_KEY`。

### 1. 单篇文章处理

生成摘要：

```bash
wchat ai summarize 123
wchat ai summarize 123 --max-length 300
```

提取关键词：

```bash
wchat ai keywords 123
wchat ai keywords 123 --max-keywords 15
```

分类：

```bash
wchat ai classify 123
```

情感分析：

```bash
wchat ai sentiment 123
```

### 2. 批量摘要

批量处理未生成摘要的文章：

```bash
wchat ai batch-summarize
```

只处理某个公众号：

```bash
wchat ai batch-summarize --mp-id MP_WXS_xxx --batch-size 20
```

### 3. 股票提取

从某个公众号所有文章中提取股票：

```bash
wchat ai extract-stocks MP_WXS_xxx
```

强制重新处理：

```bash
wchat ai extract-stocks MP_WXS_xxx --force
```

### 4. 股票查询

列出已提取股票：

```bash
wchat ai stocks list
wchat ai stocks list --mp-id MP_WXS_xxx --limit 100
```

搜索股票：

```bash
wchat ai stocks search 机器人
```

## 市场总结

`market-summary` 会组合以下信息：

- 市场行情数据
- 财联社电报
- 财联社看盘数据
- 本地文章观点
- AI 总结与后续策略

最常用命令：

```bash
wchat ai market-summary
```

指定交易日：

```bash
wchat ai market-summary --date 2026-03-27
```

强制刷新并重新生成：

```bash
wchat ai market-summary --force
```

离线模式，仅使用本地缓存 / 本地数据：

```bash
wchat ai market-summary --offline
```

## 财联社数据命令

抓取电报：

```bash
wchat cls fetch-telegraphs
wchat cls fetch-telegraphs --date 2026-03-27 --hours 36
```

抓取看盘数据：

```bash
wchat cls fetch-watch
wchat cls fetch-watch --date 2026-03-27 --hours 12
```

## 常见问题

### 1. RSS 路径需要登录吗？

不需要。使用 `ARTICLE_LIST_PROVIDER=rss` 时，`wchat source fetch` 和自动发现都不依赖 `wchat login`。只有 WeRead 路径需要登录。

### 2. API Key 放在哪里？

`WECHAT_RSS_API_KEY` 放在 `.env` 文件中，全局生效。RSS Feed URL 通过 `wchat source add` 管理，不要写在 `.env` 里。

### 3. RSS Feed URL 怎么管理？

使用 `wchat source` 命令：

```bash
wchat source add 全部 https://...    # 添加源
wchat source list                     # 列出所有源
wchat source remove 全部              # 删除源
wchat source health                   # 查看源健康状态
```

### 4. 自动发现功能安全吗？

自动发现默认关闭（`RSS_AUTO_SUBSCRIBE_DISCOVERED_FEEDS=false`）。开启后，发现的公众号默认状态为 `inactive`（`RSS_DISCOVERED_FEED_DEFAULT_STATUS=inactive`），不会自动进入抓取队列，可以在 `wchat ls` 中审核后手动启用。

### 5. 同一篇文章出现在多个 RSS 源中会重复吗？

不会。系统通过文章 ID 和原始 URL 去重，同一篇文章只保留一份，但会记录它在每个 RSS 源中的成员关系。

### 6. RSS 源健康状态怎么看？

```bash
wchat source health          # 查看所有源
wchat source health 全部     # 查看指定源
```

输出包含最近成功时间、连续失败次数、过期状态等信息。

### 7. 执行 `wchat ai ...` 报 `LLM API Key 未配置`

在 `.env` 中配置：

```bash
LLM_API_KEY=你的密钥
```

### 8. 数据文件和输出文件在哪里

默认路径：

- 数据库：`data/wchat.db`
- 股票提取输出：`output/extract_stocks/`
- 市场总结输出：`output/market_summaries/`

## 开发

运行测试：

```bash
pytest
```

只跑 RSS 相关测试：

```bash
pytest tests/test_rss_provider.py -q
pytest tests/test_rss_source_service.py -q
pytest tests/test_feed_discovery.py -q
```

只跑市场总结相关测试：

```bash
pytest tests/test_market_summary_structure.py -q
pytest tests/test_market_summary_cli_flow.py -q
```

代码检查：

```bash
ruff check .
```
