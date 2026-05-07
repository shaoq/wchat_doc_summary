## ADDED Requirements

### Requirement: 主动限速减少被动熔断触发
通过全局速率限制器和请求级间隔，系统 SHALL 主动控制请求密度，降低触发 WeRead API 限流的概率。已有的被动熔断机制（RateLimitError 捕获、批量熔断）保持不变，作为兜底保护。

#### Scenario: 主动限速与被动熔断协同工作
- **WHEN** 全局 RateLimiter 正常工作
- **THEN** 大部分情况下请求密度低于 API 限流阈值
- **AND** 已有的 RateLimitError 熔断逻辑仍然有效，作为最终安全网
