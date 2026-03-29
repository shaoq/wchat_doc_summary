## 1. 数据库模型

- [x] 1.1 在 `src/models/schema.py` 添加 `CLSTelegraph` 模型
- [x] 1.2 添加数据库迁移（表创建）

## 2. 服务层

- [x] 2.1 创建 `src/services/cls_telegraph_service.py`
- [x] 2.2 实现 `save_telegraphs()` 方法（批量保存，去重）
- [x] 2.3 实现 `list_telegraphs()` 方法（查询，过滤）

## 3. CLI 命令重构

- [x] 3.1 将 `cls-roll list` 重命名为 `cls-roll fetch`
- [x] 3.2 修改 fetch 命令：抓取后保存到数据库，只输出统计
- [x] 3.3 新增 `cls-roll ls` 命令查看已保存数据
- [x] 3.4 添加 `--category` 参数支持

## 4. 测试与验证

- [x] 4.1 编写服务层单元测试
- [x] 4.2 手动验证 CLI 命令功能
