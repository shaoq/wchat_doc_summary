## Why

当前 `WeReadClient` 的请求入口和返回结构并不统一，尤其是登录结果接口绕过了通用 `_request()` 路径，导致认证服务、客户端实现和测试 mock 点三者之间出现分叉。继续在现有结构上补功能会放大认证链路的不确定性，因此需要先统一客户端契约。

## What Changes

- 统一 `WeReadClient` 各接口的请求入口，避免单个接口绕过通用请求封装。
- 明确登录二维码、登录结果、公众号信息和文章列表接口的标准返回结构。
- 统一客户端的错误处理策略，使网络错误、HTTP 错误和状态型响应的行为一致且可预测。
- 让 `AuthService` 基于稳定的客户端返回契约处理登录状态和 token 保存。
- 调整测试，使 mock 点与真实调用路径一致，减少“测试通过但生产行为不同”的问题。

## Capabilities

### New Capabilities
- `weread-api-client`: 为微信读书代理 API 提供统一的请求封装、标准化返回结构和一致的错误处理契约。

### Modified Capabilities

## Impact

- **Affected code**:
  - `src/api/weread.py`
  - `src/services/auth.py`
  - 可能少量影响 `src/services/fetcher.py`
- **Affected tests**:
  - `tests/test_api.py`
  - `tests/test_services.py`
- **Affected behaviors**:
  - `wchat login`
  - `wchat logout`
  - 公众号信息获取
  - 文章列表获取
