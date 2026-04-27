# 设计文档: 新增看盘数据 API

## 概述

财联社看盘数据 API 用于获取实时市场热点数据，包括个股点评、题材板块等信息。这些数据将作为 AI 生成市场摘要的重要输入源之一。

## 数据源

- **API 端点**: `https://www.cls.cn/v1/roll/get_roll_list`
- **参数差异**: 使用 `category` 参数区分数据类型
  - `red`: 重要电报（已实现）
  - 其他 category: 看盘数据（本次新增）

## 架构设计

### 文件结构

```
cls-watch 模块
├── src/api/cls_watch.py              # API 客户端，复用签名算法
├── src/services/cls_watch_service.py # 服务层，处理数据存储和查询
├── src/models/schema.py              # 新增 CLSWatchData 模型
├── src/cli.py                        # 新增 cls-watch 命令组
└── tests/test_cls_watch.py           # 测试文件
```

### 数据模型

```python
class CLSWatchData(Base):
    """财联社看盘数据模型。"""
    __tablename__ = "cls_watch_data"

    id: int               # 主键
    watch_id: str         # 数据唯一标识
    title: str            # 标题
    content: str          # 内容
    ctime: int            # 发布时间戳
    category: str         # 分类
    data_type: str        # 数据类型 (hot/arrow 等)
    stocks: str           # 关联股票 (JSON)
    sectors: str          # 关联板块 (JSON)
    fetched_at: datetime  # 抓取时间
```

### API 客户端设计

复用 `CLSRollClient` 的签名算法：

```python
class CLSWatchClient:
    """财联社看盘数据客户端。"""

    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout

    def fetch_hot_data(self, limit: int = 20) -> list[dict]:
        """获取热点数据（股票、题材、板块点评）。"""
        pass

    def fetch_by_time_range(self, start_time: int, end_time: int) -> list[dict]:
        """按时间范围获取看盘数据。"""
        pass

    def parse_watch_item(self, item: dict) -> dict:
        """解析单条看盘数据。"""
        pass
```

### CLI 命令设计

```bash
# 获取看盘数据
wchat cls-watch fetch [--start YYYY-MM-DD] [--end YYYY-MM-DD]

# 查看已保存数据
wchat cls-watch ls [--limit N] [--start YYYY-MM-DD] [--end YYYY-MM-DD]
```

## 与现有系统的集成

### 复用组件

1. **签名算法**: 从 `src/api/cls_roll.py` 复用 `generate_sign` 函数
2. **数据库**: 复用现有的 `Database` 类
3. **CLI 框架**: 使用 Click 命令组模式

### 独立性

- 看盘数据使用独立的数据库表 `cls_watch_data`
- 独立的 API 客户端，不影响现有 `CLSRollClient`
- 独立的 CLI 命令组 `cls-watch`

## 数据流

```
1. CLI 命令 (wchat cls-watch fetch)
       ↓
2. CLSWatchClient.fetch_by_time_range()
       ↓
3. API 响应解析
       ↓
4. CLSWatchService.save_watch_data()
       ↓
5. 数据库存储
```

## 速率限制和缓存

- **请求间隔**: 0.5 秒（与 CLSRollClient 一致）
- **缓存策略**: 5 分钟内存缓存
- **降级方案**: httpx 失败时使用 curl

## 测试策略

1. **单元测试**
   - 签名算法测试
   - 数据解析测试
   - 客户端初始化测试

2. **集成测试**
   - API 调用测试（跳过网络测试）
   - 数据库存储测试
