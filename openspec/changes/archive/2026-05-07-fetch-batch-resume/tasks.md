## 1. 数据模型

- [x] 1.1 在 `src/models/schema.py` 新增 `FetchBatch` 模型（id, mp_id, batch_date, status, created_at, updated_at, UniqueConstraint）
- [x] 1.2 在 `src/storage/database.py` 的 `_ensure_compatible_schema` 中添加 `fetch_batches` 表的自动创建逻辑

## 2. Batch 管理逻辑

- [x] 2.1 在 `FetcherService` 中实现 `_ensure_today_batch` 方法：检查/创建当日 batch，补充新增订阅，清理 7 天前的旧记录
- [x] 2.2 在 `FetcherService` 中实现 `_get_pending_feeds` 方法：查询今日 status=pending 的订阅，JOIN feeds 按 weight DESC 排序
- [x] 2.3 在 `FetcherService` 中实现 `_mark_batch_done` 方法：将指定 mp_id 的当日 batch 记录更新为 done
- [x] 2.4 在 `FetcherService` 中实现 `_reset_today_batch` 方法：删除当日所有 batch 记录（供 --force 使用）

## 3. fetch_all 集成

- [x] 3.1 重构 `fetch_all` 方法：调用 `_ensure_today_batch` → `_get_pending_feeds` 获取队列，循环中调用 `_mark_batch_done`
- [x] 3.2 处理全部完成的场景：`_get_pending_feeds` 为空时输出"今日所有订阅已同步完成"并提前返回
- [x] 3.3 处理 RateLimitError：当前 feed 保持 pending（不调用 `_mark_batch_done`），break 循环

## 4. CLI 层改动

- [x] 4.1 在 `subscription.py` 的 `fetch` 命令中新增 `--force` 选项
- [x] 4.2 `--force` 时调用 `_reset_today_batch` 清除当日 batch 后重新执行
- [x] 4.3 调整进度显示：显示 `[2/8]` 格式的进度时，总数应为当日 pending 数而非全部订阅数

## 5. 测试

- [x] 5.1 测试 `FetchBatch` 模型的 CRUD 操作（创建、查询、状态更新）
- [x] 5.2 测试 `_ensure_today_batch`：首次创建、恢复已有 batch、补充新增订阅
- [x] 5.3 测试 `_get_pending_feeds`：返回 pending 订阅、排除 done 订阅、排序正确性
- [x] 5.4 测试 `fetch_all` 断点续传：首次运行 → 限流中断 → 重跑从断点继续
- [x] 5.5 测试每日重置：同日 batch 隔离、次日自动创建新 batch
- [x] 5.6 测试 `--force`：清除今日 batch 后全新开始
- [x] 5.7 测试旧数据清理：7 天前的记录被自动删除
- [x] 5.8 测试单独 `fetch <mp_id>` 不受 batch 影响
