## 1. 统一客户端请求入口

- [x] 1.1 梳理 `WeReadClient` 当前公开方法的请求路径与返回字段
- [x] 1.2 重构 `get_login_result()` 走统一请求封装，不再绕过 `_request()`
- [x] 1.3 为登录二维码、登录结果、公众号信息和文章列表定义稳定的标准返回结构

## 2. 对齐认证服务与客户端契约

- [x] 2.1 调整 `AuthService` 对登录结果的消费逻辑，显式依赖标准化字段
- [x] 2.2 统一客户端对网络错误、HTTP 错误和状态型响应的处理方式
- [x] 2.3 审查并修正 `FetcherService` 等调用方对 WeRead 返回结构的隐式假设

## 3. 补测试并验证真实路径

- [x] 3.1 更新 `tests/test_api.py`，让 mock 点与真实客户端调用路径一致
- [x] 3.2 更新 `tests/test_services.py` 中认证相关测试，覆盖 waiting、expired、success 和 error 场景
- [x] 3.3 运行相关测试并确认 `wchat login` 所依赖的客户端契约与服务层逻辑一致
