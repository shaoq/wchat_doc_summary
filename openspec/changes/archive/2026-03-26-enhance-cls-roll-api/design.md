## Context

现有财联社电报客户端使用 `/nodeapi/telegraphs` 端点，仅支持获取最新 50 条数据。为实现完整历史数据获取能力，需要接入 `/v1/roll/get_roll_list` API，该 API 需要签名验证并支持时间范围查询。

**签名算法** (已验证):
```
参数 dict → sorted() → urlencode → SHA1 → MD5 → 签名
```

**API 参数**:
| 参数 | 说明 |
|------|------|
| `app` | `CailianpressWeb` |
| `category` | `red` = 重要电报 |
| `last_time` | Unix 时间戳，返回早于该时间的记录 |
| `os` | `web` |
| `refresh_type` | `1` = 加载更多 |
| `rn` | 每页条数 |
| `sv` | 版本号 `8.4.6` |
| `sign` | 签名 |

## Goals / Non-Goals

**Goals:**
- 实现财联社 API 签名算法
- 支持分页获取 `category=red` 重要电报数据
- 支持按时间范围查询历史数据
- 提供 CLI 命令行接口

**Non-Goals:**
- 不修改现有 `cls_telegraph.py` 的行为
- 不实现其他 category 类型的支持（如全部、A股等）
- 不实现数据持久化存储（由后续变更处理）

## Decisions

### 1. 新建独立客户端类 vs 扩展现有类

**决定**: 新建 `CLSRollClient` 类

**理由**:
- 现有 `CLstTelegraphClient` 使用 curl 绕过 SSL 问题，API 端点不同
- 签名逻辑独立，职责单一
- 便于单独测试和维护

### 2. HTTP 客户端选择

**决定**: 优先使用 httpx，失败时降级到 curl

**理由**:
- httpx 是项目现有依赖，API 更友好
- 保留 curl 作为备选方案处理 SSL 兼容性问题

### 3. 时间范围查询实现

**决定**: 循环分页拉取 + 客户端过滤

**算法**:
```
1. 用 end_time 作为初始 last_time
2. 调用 API 获取 rn 条数据
3. 过滤出 >= start_time 的数据
4. 用返回中最早的 ctime 作为下次 last_time
5. 重复直到数据早于 start_time 或无更多数据
```

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| SSL 连接问题 | 保留 curl 降级方案 |
| API 速率限制 | 添加请求间隔，默认 0.5 秒 |
| 大时间范围数据量大 | 支持分批获取，提供进度反馈 |
