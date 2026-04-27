## Why

当前 `wchat` 抓取公众号文章列表强依赖单一 WeRead 代理接口，而实际排查已经确认部分公众号会在上游列表接口阶段稳定返回 `id(...): WeReadError400`，即使缩小 `pageSize`、切换页码也无法恢复。这使得“订阅公众号并稳定抓取文章”这一核心目标被上游单点故障绑死。

从代码结构看，项目已经具备文章正文抓取、HTML 解析、文章入库和 AI 后处理能力，真正脆弱的是“如何拿到文章列表”。因此需要把文章列表获取从 WeRead 专有实现中解耦出来，引入可替换的 Provider 抽象，并优先接入 `Wechat2RSS` 作为新的列表来源。

## What Changes

- 新增统一的文章列表 Provider 能力，定义从外部来源获取公众号文章列表的标准接口与标准文章项结构。
- 接入 `Wechat2RSS` Provider，支持通过 `Wechat2RSS` API 获取公众号文章列表，并将其映射为项目内部统一文章项。
- 调整文章抓取流程，使 `FetcherService` 不再只依赖 WeRead 列表接口，而是从配置选择列表 Provider。
- 调整文章正文抓取入口，使其支持完整文章 URL，而不再要求列表源必须提供微信 `/s/<article_id>` 风格的短 ID。
- 扩展订阅模型与订阅行为，支持记录订阅来源 Provider 及 Provider 专属元数据，为后续多 Provider 并存做准备。
- 补充 Provider、抓取流程与订阅兼容性测试，确保 `Wechat2RSS` 接入后仍兼容现有 `fetch/show/export/ai` 后续链路。

## Capabilities

### New Capabilities

- `article-list-provider`: 定义统一文章列表 Provider 抽象，并支持接入 `Wechat2RSS` 作为新的公众号文章列表来源。

### Modified Capabilities

- `article-fetcher`: 抓取流程从固定 WeRead 列表接口改为可替换 Provider，并要求正文抓取支持完整文章 URL 输入。
- `subscription`: 订阅能力需要支持保存 Provider 信息与 Provider 侧订阅标识，以便后续按来源同步公众号文章。

## Impact

- 受影响代码:
  - `src/services/fetcher.py`
  - `src/api/article.py`
  - `src/api/weread.py`
  - 新增 `src/api/providers/` 或等价目录
  - `src/services/subscription.py`
  - `src/models/schema.py`
  - `config/settings.py`
- 受影响测试:
  - `tests/test_services.py`
  - `tests/test_api.py`
  - `tests/test_fetcher_integration.py`
  - `tests/test_cli_commands.py`
  - 视实现方式新增 Provider 相关测试
- 外部系统与依赖:
  - `Wechat2RSS` API / 部署实例
  - 数据库 schema 迁移（如新增 provider 相关字段）
