## Context

登录链路本身已经在 service 层归一化了状态：

- `waiting` / `pending` / `scanned`
- `expired`
- `error`
- `success`

但 CLI 只关心 `success`，其余状态全部继续轮询。这等于把 service 层已经表达出来的终态信息丢掉了。

## Goals / Non-Goals

**Goals:**
- 让 CLI 对 `expired` 和 `error` 立即停止并反馈。
- 保持等待类状态继续轮询。
- 用回归测试锁住用户可见行为。

**Non-Goals:**
- 不改写二维码登录协议。
- 不调整 token 存储逻辑。

## Decisions

### 1. 终态在 CLI 层立即终止轮询

如果 service 返回 `expired` 或 `error`，CLI 应立即停止进度轮询并显示对应消息。

### 2. 等待态继续轮询

`waiting` / `pending` / `scanned` 仍然是预期中的中间态，保持原有轮询机制即可。

## Risks / Trade-offs

- [更早暴露错误会让用户更频繁看到失败提示] → 这是正确反馈，而不是回归。

## Migration Plan

1. 调整登录 CLI 的状态分支。
2. 补终态测试。

## Open Questions

- 是否要在 `expired` 时额外提示用户重新执行 `wchat login`。
