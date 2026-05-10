## 1. 配置层

- [ ] 1.1 在 `config/settings.py` 中新增 `fetch_page_jitter` 和 `fetch_article_jitter` 配置项（默认 3.0，ge=0，le=30）

## 2. 核心实现

- [ ] 2.1 在 `FetcherService.__init__` 中读取新配置项为 `self._page_jitter` 和 `self._article_jitter`
- [ ] 2.2 新增 `_jittered_wait(base, jitter, mp_id, reason, on_progress)` 方法，实际等待 = base + random.uniform(0, jitter)
- [ ] 2.3 替换 `_fetch_feed_summary` 中 2 处固定等待为抖动等待（翻页 + 文章间）
- [ ] 2.4 替换 `_fetch_incremental_summary` 中 2 处固定等待为抖动等待（翻页 + 文章间）
- [ ] 2.5 替换 `backfill_publish_time` 中 1 处固定等待为抖动等待（翻页）

## 3. 测试

- [ ] 3.1 为 `_jittered_wait` 方法编写单元测试，验证等待范围在 [base, base+jitter] 内
- [ ] 3.2 更新现有测试中依赖固定间隔的断言（如 `assert sleep >= 8.0` 改为 `>= base`）
- [ ] 3.3 验证 jitter=0 时行为与变更前完全一致
