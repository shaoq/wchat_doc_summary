## Why

登录 service 已经能区分“等待扫码”“二维码过期”“明确错误”等终态，但当前 CLI 只检查 `success`，其他状态会一直轮询到统一超时。这样用户在二维码过期或登录失败时拿不到即时反馈，体验和可诊断性都较差。

## What Changes

- 让登录 CLI 正确处理 `expired`、`error` 等终态，而不是继续无意义轮询。
- 在二维码过期或明确错误时立即停止轮询并输出对应提示。
- 保持等待扫码 / 待确认状态的轮询行为不变。
- 补充登录 CLI 对终态处理的回归测试。

## Capabilities

### New Capabilities
- `login-terminal-states`: 提供对登录终态的显式 CLI 处理，使过期和错误状态能立即反馈给用户。

### Modified Capabilities

## Impact

- **Affected code**:
  - `src/cli/auth.py`
  - 可能少量影响 `src/services/auth.py` 返回字段的消费方式
- **Affected tests**:
  - 需要新增登录 CLI 终态处理测试
- **Affected behaviors**:
  - `wchat login`
