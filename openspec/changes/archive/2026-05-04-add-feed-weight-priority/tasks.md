## 1. 数据模型与迁移

- [x] 1.1 Feed 模型新增 `weight` 字段 (Integer, default=5, comment="权重: 0-低, 5-中, 10-高")
- [x] 1.2 database.py 的 `init_db()` 添加 weight 列的迁移检测 (ALTER TABLE feeds ADD COLUMN weight INTEGER DEFAULT 5)

## 2. 服务层

- [x] 2.1 SubscriptionService 新增 `list_subscriptions_for_fetch()` 方法，排序: weight DESC, sync_time IS NULL 优先, name ASC
- [x] 2.2 FetcherService.fetch_all() 替换 `list_subscriptions()` 为 `list_subscriptions_for_fetch()`

## 3. CLI 命令

- [x] 3.1 新增 `set-weight` 子命令: `wchat sub set-weight <mp_id> <0|5|10>`，使用 Click choice 校验
- [x] 3.2 `wchat sub ls` 表格新增"权重"列，显示 0/5/10
- [x] 3.3 `wchat sub info` 面板新增权重显示
