## 1. Provider 抽象与配置

- [x] 1.1 新增统一的文章列表 Provider 接口与标准文章项结构，隔离外部列表源与抓取服务
- [x] 1.2 在 `config/settings.py` 中新增列表 Provider 选择与 `Wechat2RSS` 相关配置项

## 2. Wechat2RSS Provider 接入

- [x] 2.1 实现 `Wechat2RSSProvider`，支持按公众号获取文章列表并映射为统一文章项
- [x] 2.2 为订阅解析流程补充 provider-aware 解析能力，支持通过文章 URL 解析公众号并记录 provider 侧标识

## 3. 抓取链路与数据模型适配

- [x] 3.1 调整 `FetcherService`，使其通过配置选择列表 Provider，并继续复用现有正文抓取/解析/入库流程
- [x] 3.2 扩展文章正文抓取入口以支持完整文章 URL，而不是只依赖 `/s/<article_id>` 短 ID
- [x] 3.3 扩展 `Feed` / `Article` 模型与数据库 schema，增加 provider 相关字段并定义去重策略

## 4. 测试与兼容性回归

- [x] 4.1 新增或更新 Provider 层测试，覆盖 `Wechat2RSS` 响应映射、配置选择与错误处理
- [x] 4.2 更新抓取与订阅相关测试，覆盖 provider 模式下的 `fetch` / `subscribe` 兼容行为
- [x] 4.3 更新必要文档，说明如何配置 `Wechat2RSS` Provider 以及何时回退到 `weread`
