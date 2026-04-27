# 规格说明: 财联社看盘数据 API

## API 规格

### 端点

```
GET https://www.cls.cn/v1/roll/get_roll_list
```

### 请求参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| app | string | 是 | 固定值: `CailianpressWeb` |
| category | string | 是 | 分类标识 |
| last_time | string | 是 | Unix 时间戳，返回早于该时间的记录 |
| os | string | 是 | 固定值: `web` |
| refresh_type | string | 是 | 刷新类型: `1`=加载更多 |
| rn | string | 是 | 每页条数 |
| sv | string | 是 | 版本号: `8.4.6` |
| sign | string | 是 | 签名（通过签名算法生成） |

### 签名算法

```python
def generate_sign(params: dict) -> str:
    # 1. 对参数按键名排序
    sorted_params = sorted(params.items())
    # 2. URL 编码生成查询字符串
    query_string = urlencode(sorted_params)
    # 3. 对查询字符串计算 SHA1 哈希
    sha1_hash = hashlib.sha1(query_string.encode()).hexdigest()
    # 4. 对 SHA1 结果计算 MD5 哈希
    sign = hashlib.md5(sha1_hash.encode()).hexdigest()
    return sign
```

### 响应格式

```json
{
  "errno": 0,
  "errmsg": "",
  "data": {
    "roll_data": [
      {
        "id": "xxx",
        "title": "标题",
        "content": "内容",
        "ctime": 1700000000,
        "level": "A",
        "category": "xxx",
        "stocks": ["股票1", "股票2"],
        "sectors": ["板块1", "板块2"]
      }
    ]
  }
}
```

## 数据库模型规格

### cls_watch_data 表

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | INTEGER | PRIMARY KEY, AUTOINCREMENT | 主键 |
| watch_id | VARCHAR(64) | NOT NULL, UNIQUE | 数据唯一标识 |
| title | VARCHAR(512) | NOT NULL | 标题 |
| content | TEXT | NULLABLE | 内容 |
| ctime | INTEGER | NOT NULL, INDEX | 发布时间戳 |
| category | VARCHAR(32) | NOT NULL | 分类 |
| data_type | VARCHAR(32) | NULLABLE | 数据类型 |
| stocks | TEXT | NULLABLE | 关联股票 (JSON) |
| sectors | TEXT | NULLABLE | 关联板块 (JSON) |
| fetched_at | DATETIME | DEFAULT NOW | 抓取时间 |

## CLI 命令规格

### cls-watch fetch

```bash
wchat cls-watch fetch [OPTIONS]
```

**选项:**
- `--category, -c`: 分类过滤（默认: 所有）
- `--start`: 开始时间 (YYYY-MM-DD)
- `--end`: 结束时间 (YYYY-MM-DD)
- `--type`: 数据类型过滤

**输出:**
- 获取条数
- 新增条数
- 跳过条数（已存在）

### cls-watch ls

```bash
wchat cls-watch ls [OPTIONS]
```

**选项:**
- `--limit, -n`: 显示数量（默认: 20）
- `--start`: 开始时间 (YYYY-MM-DD)
- `--end`: 结束时间 (YYYY-MM-DD)
- `--format`: 输出格式 (table/json)
- `--type`: 数据类型过滤

**输出格式:**
- 表格: 时间 | 类型 | 标题
- JSON: 完整数据结构

## 服务层规格

### CLSWatchService

```python
class CLSWatchService:
    """财联社看盘数据服务。"""

    async def save_watch_data(
        self,
        items: list[dict],
        category: str = "watch"
    ) -> tuple[int, int]:
        """保存看盘数据到数据库。

        Args:
            items: 原始数据列表
            category: 分类标识

        Returns:
            (inserted_count, skipped_count)
        """
        pass

    async def list_watch_data(
        self,
        start_time: int | None = None,
        end_time: int | None = None,
        data_type: str | None = None,
        limit: int = 20
    ) -> list[CLSWatchData]:
        """查询看盘数据。"""
        pass

    async def get_watch_data_for_summary(
        self,
        trade_date: date
    ) -> list[dict]:
        """获取指定交易日的看盘数据（用于 AI 摘要生成）。"""
        pass
```

## 错误处理

| 错误类型 | 处理方式 |
|----------|----------|
| 网络超时 | 降级到 curl，记录日志 |
| API 错误 | 记录错误信息，返回空列表 |
| 数据解析错误 | 跳过该条数据，继续处理 |
| 数据库错误 | 抛出异常，由上层处理 |

## 性能要求

- 单次请求超时: 10 秒
- 请求间隔: 0.5 秒
- 批量插入: 每 100 条提交一次
- 内存缓存: 5 分钟有效期
