## Context

当前 `fetch --all` 按订阅创建时间倒序遍历公众号，所有公众号无优先级区分。对于金融信息类系统，时效性至关重要 — 市场要闻类公众号应当比资讯聚合类更早被抓取。

涉及的代码路径:
- `FetcherService.fetch_all()` (fetcher.py:611) — 批量抓取入口
- `SubscriptionService.list_subscriptions()` (subscription.py:120) — 提供订阅列表
- `Feed` 模型 (schema.py:17) — 无权重字段
- CLI `ls` (subscription.py:136) — 展示订阅列表

## Goals / Non-Goals

**Goals:**
- Feed 模型增加权重字段，支持三档 (0/5/10)
- `fetch --all` 按权重降序抓取，同权重下未同步优先
- CLI 支持查看和设置权重
- `ls` 显示权重列

**Non-Goals:**
- 不做自动权重推断（如基于文章频率、阅读量等）
- 不做权重级别的自定义扩展（固定三档）
- 不改变单公众号 `fetch <mp_id>` 的行为

## Decisions

### D1: 权重取值 — 固定三档 0/5/10

**选择**: Integer 字段，取值 0 (低) / 5 (中，默认) / 10 (高)

**替代方案**:
- 连续整数 1-100: 灵活但增加选择负担，当前场景不需要
- 枚举字符串 high/medium/low: 数据库查询需要映射，不如整数直接排序

**理由**: 三档足够表达优先级，默认 5 确保现有订阅不受影响，CLI 交互简单。

### D2: 排序策略放置 — 独立方法 `list_subscriptions_for_fetch()`

**选择**: 在 `SubscriptionService` 新增专用方法

**替代方案**:
- 修改 `list_subscriptions()` 加排序参数: 影响所有调用方
- 在 `fetch_all()` 内排序: 职责泄漏，fetcher 不应关心排序细节

**理由**: 职责清晰，不影响现有展示用的 `list_subscriptions()`，且未来可独立演进（如加入"未同步优先"逻辑）。

### D3: 排序规则 — weight DESC + 未同步优先 + name ASC

```
ORDER BY weight DESC,
         CASE WHEN sync_time IS NULL THEN 0 ELSE 1 END,
         name ASC
```

**理由**: 高权重先抓确保时效性；未同步的优先确保新订阅尽早初始化；name ASC 保证确定性便于日志排查。

### D4: 数据库迁移 — ALTER TABLE ADD COLUMN

SQLite 支持 `ALTER TABLE ... ADD COLUMN ... DEFAULT 5`，无需复杂迁移。database.py 的 `init_db()` 中已有表结构检查逻辑，新增列检测即可。

### D5: CLI 命令 — 新增 `set-weight` 子命令

```
wchat sub set-weight <mp_id> <0|5|10>
```

使用 Click 的 `@click.choice` 校验取值范围，避免无效输入。

## Risks / Trade-offs

- **[迁移风险]** 旧版 SQLite 客户端可能不识别新列 → 实际无风险，SQLite 3.x 都支持 ADD COLUMN
- **[权重膨胀]** 用户可能要求更多档位 → 三档先上线，后续按需扩展，Integer 字段天然兼容
- **[排序逻辑固化]** fetch 排序策略可能随需求变化 → 独立方法封装，修改成本低
