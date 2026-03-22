## 1. 配置层修改

- [x] 1.1 在 `config/settings.py` 中增加 `fetch_page_size` 配置项，默认值 50

## 2. API 客户端层修改

- [x] 2.1 在 `src/api/weread.py` 的 `WeReadClient.get_articles()` 方法中增加 `page_size` 参数
- [x] 2.2 将 `page_size` 参数传递给 API 请求（`pageSize`）

## 3. 服务层修改

- [x] 3.1 在 `src/services/fetcher.py` 的 `FetcherService.fetch_feed()` 方法中增加 `page_size` 参数
- [x] 3.2 在调用 `get_articles()` 时传递 `page_size` 参数
- [x] 3.3 从配置读取 `page_size` 默认值

## 4. 验证

- [x] 4.1 运行现有测试确保向后兼容
- [x] 4.2 手动测试 fetch 命令验证抓取数量提升 (待用户验证)
