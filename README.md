# wchat

微信公众号文章订阅与 A 股市场分析 CLI。

这个项目主要做 4 件事：

- 订阅公众号并抓取文章
- 在本地数据库中管理文章与订阅
- 对文章做 AI 摘要、关键词、分类、情感、股票提取
- 结合市场数据、财联社数据和文章，生成 `market-summary`

## 功能概览

- 微信读书登录
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
WEREAD_API_BASE=https://weread.111965.xyz
DATABASE_URL=sqlite+aiosqlite:///./data/wchat.db

LLM_BASE_URL=https://api.anthropic.com
LLM_API_KEY=你的密钥
LLM_MODEL=claude-3-5-haiku-latest
```

说明：

- `DATABASE_URL` 默认就是 `sqlite+aiosqlite:///./data/wchat.db`
- 只有 `wchat ai ...` 相关命令需要 `LLM_API_KEY`
- `wchat login`、`subscribe`、`fetch` 依赖微信读书代理接口可用

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
```

## 最常用的使用流程

### 1. 登录

```bash
wchat login
```

登录成功后可用：

```bash
wchat logout
```

### 2. 订阅公众号

通过一篇公众号文章 URL 反查并订阅：

```bash
wchat subscribe "https://mp.weixin.qq.com/s/xxxx"
```

查看订阅列表：

```bash
wchat ls
```

查看某个订阅详情：

```bash
wchat info MP_WXS_xxx
```

取消订阅：

```bash
wchat unsubscribe MP_WXS_xxx
```

### 3. 抓取文章

抓取单个公众号最近 5 天文章：

```bash
wchat fetch MP_WXS_xxx
```

抓取单个公众号最近 30 天文章：

```bash
wchat fetch MP_WXS_xxx --days 30
```

抓取单个公众号全部历史文章：

```bash
wchat fetch MP_WXS_xxx --full
```

抓取所有订阅最近 5 天文章：

```bash
wchat fetch --all
```

### 4. 查看和导出文章

查看某个公众号已抓取文章：

```bash
wchat show MP_WXS_xxx
```

查看更多文章：

```bash
wchat show MP_WXS_xxx --limit 50 --offset 50
```

查看单篇文章详情：

```bash
wchat article 123
```

导出文章：

```bash
wchat export --format json --output articles.json
wchat export --format markdown --output articles.md
wchat export --mp-id MP_WXS_xxx --format markdown --output mp_articles.md
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

同时输出简化股票列表：

```bash
wchat ai extract-stocks MP_WXS_xxx --simple-info
```

指定输出文件：

```bash
wchat ai extract-stocks MP_WXS_xxx --output output/extract_stocks/custom.txt
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

查看某只股票出现在哪些文章里：

```bash
wchat ai stocks show 优博讯
wchat ai stocks show 优博讯 --limit 50
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

查看历史总结：

```bash
wchat ai market-summary --list
```

输出文件默认保存在：

```bash
output/market_summaries/<trade_date>.md
```

适合的使用方式：

1. 日常盘后直接执行 `wchat ai market-summary`
2. 想跳过旧缓存时执行 `wchat ai market-summary --force`
3. 想验证历史交易日结果时执行 `wchat ai market-summary --date YYYY-MM-DD`
4. 只想看历史记录时执行 `wchat ai market-summary --list`

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

查看本地电报：

```bash
wchat cls list-telegraphs
wchat cls list-telegraphs --limit 50 --min-level A
```

查看本地看盘数据：

```bash
wchat cls list-watch
wchat cls list-watch --limit 50
```

## 常见问题

### 1. 执行 `wchat ai ...` 报 `LLM API Key 未配置`

说明没有配置：

```bash
LLM_API_KEY=你的密钥
```

### 2. 执行 `subscribe` 或 `fetch` 提示先登录

先执行：

```bash
wchat login
```

### 3. `market-summary` 没有生成新结果

先检查：

- 是否已经存在同交易日总结
- 是否需要加 `--force`
- 是否在 `--offline` 模式下缺少本地缓存

### 4. 数据文件和输出文件在哪里

默认路径：

- 数据库：`data/wchat.db`
- 股票提取输出：`output/extract_stocks/`
- 市场总结输出：`output/market_summaries/`

## 开发

运行测试：

```bash
pytest
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
