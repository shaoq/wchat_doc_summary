## Context

当前 `FetcherService` 中有三类等待：
- **文章间等待**: `self._article_interval` (固定 6s)
- **翻页间等待**: `self._page_interval` (固定 6s)
- **订阅间等待**: `self._subscription_delay + random.uniform(0, self._subscription_jitter)` (8s + 0~4s)

前两者完全固定，节奏可被上游识别为机器人。

## Goals / Non-Goals

**Goals:**
- 为文章间和翻页间等待增加随机抖动
- 保持与 `subscription_jitter` 一致的设计模式，降低认知负担
- 保证抖动只加不减，不缩短安全下限

**Non-Goals:**
- 不引入指数退避（已有 `BATCH_BACKOFF_FACTOR` 处理异常后退避）
- 不修改全局限速器 (`RateLimiter`) 的行为
- 不修改订阅间抖动的现有实现

## Decisions

### 1. 新增 `_jittered_wait` 方法而非修改 `_wait_with_progress`

**选择**: 新增独立方法

**理由**: `_wait_with_progress` 是通用等待方法，订阅间调用已自带抖动逻辑。修改它会导致抖动叠加或需要额外参数区分场景。新增方法更清晰，调用点语义更明确。

### 2. 抖动方向：只加不减

**公式**: `actual = base + random.uniform(0, jitter)`

**理由**: base 是经过验证的安全下限，缩短可能触发限流。与订阅间抖动公式一致。

### 3. 默认抖动值：base × 50%

**配置**:
- `fetch_page_jitter`: 默认 3.0s (base=6s)
- `fetch_article_jitter`: 默认 3.0s (base=6s)

**理由**: 50% 是常见比例，足以打乱节奏，总耗时增加可控。

### 4. 配置层暴露，与 subscription_jitter 同构

新增配置项与 `fetch_subscription_jitter` 使用相同的 `Field(ge=0, le=30)` 约束，保持一致性。

## Risks / Trade-offs

- **[总耗时增加]** → 以 10 订阅 × 5 篇为例，抖动平均增加 ~75s，上限 ~270s。可接受，因为原节奏本就偏固定。
- **[测试断言需适配]** → 现有测试中 `assert sleep >= 8.0` 等断言需改为只检查 base 下限，不依赖精确值。
- **[Jitter 设为 0 时行为不变]** → 用户可通过配置关闭抖动，回退到固定间隔。
