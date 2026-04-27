## Context

东方财富 API 通过 Python HTTP 库访问时存在 SSL 问题，导致 `akshare.stock_board_concept_name_em()` 等接口全部失败。项目已在其他模块使用 `subprocess` 调用 curl 命令绕过 SSL 问题。

需要使用相同方式获取板块数据，包括概念板块和行业板块。

## Goals / Non-Goals

**Goals:**
- 使用 curl 命令直接访问东方财富板块 API
- 实现概念板块列表获取
- 实现行业板块列表获取
- 添加请求头伪装和重试机制
- 添加 5 分钟缓存避免频繁请求
- 提供降级策略：curl 失败时回退到 akshare

**Non-Goals:**
- 不修改 akshare 的实现
- 不实现板块成分股查询（由后续变更处理）
- 不实现板块数据持久化（由后续变更处理）

## Decisions

### 1. 数据获取方式

**决定**: 使用 curl + subprocess 绕过 SSL 问题

**理由**:
- 项目已有成功经验（cls_telegraph.py）
- Python HTTP 库（httpx/aiohttp/requests）在访问东方财富时都存在 SSL 问题
- curl 命令行工具能稳定访问

### 2. API 端点

**决定**:
- 概念板块: `http://82.push2.eastmoney.com/api/qt/clist/get`
- 行业板块: `http://82.push2.eastmoney.com/api/qt/clist/get` (不同参数)

**理由**:
- 这是东方财富公开的 API 端点
- 返回 JSON 格式数据，易于解析
- 支持分页和字段选择

### 3. 缓存策略

**决定**: 使用内存缓存，5 分钟过期

**理由**:
- 板块数据更新频率较低
- 避免频繁请求被限流
- 简单实现，无需额外依赖

### 4. 降级策略

**决定**: curl 失败时尝试 akshare

**理由**:
- 保持向后兼容
- 某些环境可能没有 SSL 问题
- 提高系统健壮性

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| API 端点变更 | 封装为独立模块，易于更新 |
| curl 不可用 | 降级到 akshare |
| 请求频率限制 | 添加缓存和请求间隔 |
| 数据格式变化 | 完善的错误处理和日志 |
