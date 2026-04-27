# 任务清单: 新增看盘数据 API

## 任务列表

### 1. 数据模型
- [x] 1.1 在 `src/models/schema.py` 中添加 `CLSWatchData` 模型

### 2. API 客户端
- [x] 2.1 创建 `src/api/cls_watch.py`
- [x] 2.2 实现 `CLSWatchClient` 类
- [x] 2.3 复用签名算法 `generate_sign`
- [x] 2.4 实现 `fetch_hot_data` 方法
- [x] 2.5 实现 `fetch_by_time_range` 方法
- [x] 2.6 实现 `parse_watch_item` 方法

### 3. 服务层
- [x] 3.1 创建 `src/services/cls_watch_service.py`
- [x] 3.2 实现 `CLSWatchService` 类
- [x] 3.3 实现 `save_watch_data` 方法
- [x] 3.4 实现 `list_watch_data` 方法
- [x] 3.5 实现 `get_watch_data_for_summary` 方法

### 4. CLI 命令
- [x] 4.1 在 `src/cli.py` 中添加 `cls_watch` 命令组
- [x] 4.2 实现 `cls-watch fetch` 命令
- [x] 4.3 实现 `cls-watch ls` 命令

### 5. 测试
- [x] 5.1 创建 `tests/test_cls_watch.py`
- [x] 5.2 测试签名算法（复用）
- [x] 5.3 测试客户端初始化
- [x] 5.4 测试数据解析
- [x] 5.5 测试服务层方法

### 6. 验证
- [x] 6.1 运行所有测试
- [x] 6.2 手动验证 CLI 命令
- [x] 6.3 验证数据库存储

## 完成标准

- 所有测试通过
- CLI 命令可用
- 数据正确存储到数据库
- 代码符合项目规范
