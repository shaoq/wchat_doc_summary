## 1. Batch Sync Strategy

- [ ] 1.1 调整 `fetch --all` 的默认无范围语义，使其走批量增量同步而不是每订阅最新 10 条
- [ ] 1.2 为未初始化订阅补充有界初始化抓取策略，避免批量增量路径失效
- [ ] 1.3 在 `FetcherService.fetch_all()` 中增加订阅间等待、抖动和异常后退避

## 2. Empty-Result Hardening

- [ ] 2.1 为第一页空列表增加可疑空页重试与分类结果
- [ ] 2.2 收紧 `WeReadClient.get_articles()` 和相关 provider 的响应校验，禁止异常格式静默转空列表
- [ ] 2.3 调整 `sync_time` 更新条件，确保异常空结果和无效响应不会推进同步时间

## 3. Reporting and CLI

- [ ] 3.1 为抓取服务增加结果摘要结构，区分上游返回数、新增数、已存在数、失败数和最终状态
- [ ] 3.2 更新 `wchat fetch` CLI 输出，明确展示“无新增”与“上游空结果/异常空结果”的区别

## 4. Verification

- [ ] 4.1 补充 `fetch_all` 默认增量语义与节流/退避测试
- [ ] 4.2 补充可疑空页、非法响应、sync_time 不更新和细粒度结果摘要测试
