## Context

当前文章发布时间来源主要有两类：

1. provider 列表返回的 `publishTime` / `publish_time`
2. 微信文章 HTML 页面里的 `publish_time`

其中 `weread` provider 会返回 Unix 时间戳。现有实现中，[fetcher.py](/Users/jie.hua/Documents/Developments/Projects/wchat_doc/src/services/fetcher.py) 对整数时间戳使用 `datetime.fromtimestamp(..., tz=timezone.utc)` 解析，随后直接写入 `Article.publish_time`。但 `articles.publish_time` 是 SQLite 无时区 `DateTime` 字段，时区信息会在持久化时丢失，导致 UTC 时间被错误地作为本地时间使用。

问题不是局部展示偏差，而是一个跨链路的时间语义错误：

- 文章详情和文章列表显示早 8 小时
- 增量抓取比较使用错误基准时间
- `market-summary` 的文章窗口查询会漏掉本应命中的盘后文章
- 后续任何依赖 `Article.publish_time` 的排序与过滤都带着错误前提

由于该字段已经有存量错误数据，本次变更不仅要修入库逻辑，还要给出历史修复方案，否则新旧数据会混杂，窗口查询仍不稳定。

## Goals / Non-Goals

**Goals:**
- 明确 `Article.publish_time` 的单一 contract：数据库内统一保存上海时区的 naive datetime。
- 在入库前统一处理 Unix 时间戳、ISO 带时区字符串和页面解析时间，避免不同来源混用 UTC 和本地时间。
- 保证抓取、回填、增量比较和市场总结文章窗口基于同一时间语义运行。
- 提供对现有错误历史数据的修复路径，并尽量限制误伤范围。

**Non-Goals:**
- 不在本次变更中把数据库字段升级为 timezone-aware 类型。
- 不重构 `Article` 表结构或引入新的时间字段。
- 不修复 CLS 电报、看盘等其他数据源的时间语义。
- 不在本次变更中改变市场总结文章窗口本身的业务定义。

## Decisions

### 1. 将数据库中的 `Article.publish_time` 定义为“上海时区本地时间的 naive datetime”

选择：所有文章在写入 `articles.publish_time` 前，统一归一化到 `Asia/Shanghai`，然后去掉 `tzinfo` 再入库。

理由：
- 当前数据库列就是无时区 `DateTime`，继续混用 aware/naive 只会扩大歧义。
- 项目中绝大多数查询、CLI 展示、市场总结窗口判断都按中国本地交易时间理解文章发布时间。
- 相比“统一存 UTC，展示时再转本地”，这个方案与现有数据模型和查询方式改动更小，也更符合本次明确选择。

备选方案：
- 统一存 UTC naive，再在所有读取点做时区转换。放弃原因：读取点较多，且任何遗漏都会再次产生用户可见偏差。
- 改列为 timezone-aware 类型。放弃原因：SQLite 支持和现有 ORM 使用方式都不适合在本次小范围修复里引入。

### 2. 新增一个专门的发布时间归一化入口，禁止直接把 provider 时间写入数据库

选择：在抓取服务中增加单一归一化函数，用于处理：
- Unix 时间戳
- 带时区的 ISO 时间字符串
- 无时区字符串或页面解析时间

规则：
- aware datetime：转换到 `Asia/Shanghai` 后去掉 `tzinfo`
- Unix 时间戳：按绝对时刻解释，再转换到 `Asia/Shanghai`
- naive datetime：视为已经是本地时间，原样保留

理由：
- 当前 `_parse_publish_time()` 和 `_to_naive_utc()` 分别服务于不同语义，容易把“比较用 UTC”和“入库存储语义”混在一起。
- 需要把“比较语义”和“持久化语义”明确拆开，避免再次把 UTC 结果写入数据库。

备选方案：
- 仅修改整数时间戳分支。放弃原因：带时区字符串同样可能触发相同问题，局部修补不够稳。

### 3. 历史修复只针对可确定为 UTC naive 误写的文章记录

选择：为历史数据提供一次性修复脚本或实现入口，优先针对 `provider='weread'` 的文章记录，把现有 `publish_time` 加 8 小时回写为上海时区本地时间。

理由：
- `weread` 路径已经通过现网样本确认存在系统性 UTC naive 误写。
- 页面解析得到的发布时间本身通常是本地 naive，不适合一刀切整体平移。
- 按 provider 限定可以降低误伤面，并与问题根因对齐。

备选方案：
- 不修历史，只修新入库。放弃原因：`market-summary` 等窗口查询会长期混合旧错数据和新正确数据。
- 所有文章统一加 8 小时。放弃原因：会误伤原本已正确的本地时间记录。

### 4. 增量比较与窗口查询继续使用 naive datetime，但前提改为“这些 naive 值都代表上海本地时间”

选择：不改现有大部分比较代码的类型，只修数据来源 contract，确保数据库和新抓取数据都使用相同的上海本地 naive 语义。

理由：
- 这样可以减少对 `fetch_incremental()`、`market_analyzer.get_related_articles()` 等调用点的侵入式修改。
- 只要存储 contract 一致，现有基于 naive datetime 的 SQL 比较仍然成立。

备选方案：
- 所有比较逻辑升级成 timezone-aware。放弃原因：改动范围过大，不符合本次修复目标。

## Risks / Trade-offs

- [历史 `weread` 记录中可能混入个别已正确时间] → 通过限定 provider、抽样验证和实现前后的 SQL 对账降低误修风险。
- [页面解析与 provider 时间存在冲突] → 统一以归一化后的 provider 时间为主，但在测试中加入回退路径覆盖，确保 provider 缺失时页面解析仍维持本地时间语义。
- [未来引入新 provider 再次混入不同时间语义] → 通过单一归一化入口和测试约束，要求所有 provider 入库前都先归一化。
- [修复后影响既有 market-summary 命中结果] → 这是预期行为变化，应通过回归测试锁定“盘后文章被正确命中”的新结果。

## Migration Plan

1. 增加发布时间归一化函数，并将文章入库与回填路径全部切到该入口。
2. 保持数据库字段类型不变，但保证新写入数据全部为上海时区 naive datetime。
3. 实现一次性历史修复入口，仅修复 `weread` provider 可确认受影响的记录。
4. 用 SQL 抽样和测试验证修复前后文章时间、增量抓取比较和市场总结文章窗口命中情况。

回滚策略：
- 若修复逻辑出现误判，可先停用历史修复步骤，仅保留新入库归一化逻辑。
- 若新归一化实现导致异常，可回滚到变更前版本，并通过修复前的数据快照恢复被批量修改的历史记录。

## Open Questions

- 历史修复入口是做成独立 CLI/脚本，还是集成到一次性维护命令中。
- 对于历史 `provider` 为空但实际来自旧 `weread` 路径的文章，是否需要在实施阶段定义额外识别规则，还是先只修已标注 `provider='weread'` 的记录。
