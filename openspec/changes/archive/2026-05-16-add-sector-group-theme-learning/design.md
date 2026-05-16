## Context

当前分组建议依赖 `THEME_DEFINITIONS` 内置主题词典做语义约束。这个策略能避免纯行情共现造成的误聚类，但也带来明显维护问题：新主线必须通过代码变更补充主题，例如新增 `人形机器人链` 后，`机器人` 和 `智能机器` 才能进入分组建议。

理想状态是系统能持续从市场数据、CLS 看盘和市场总结中发现主题词候选，但正式词典仍保持用户可控和可审查，避免把短期噪声或错误 AI 判断固化。

## Goals / Non-Goals

**Goals:**

- 将主题词典从硬编码常量升级为动态加载体系。
- 支持用户通过 CLI 查看、校验、手工维护主题词典。
- 自动发现可能的新主题词、新主题和噪声词。
- 使用规则评分和 AI 结构化判断辅助归属，但所有学习结果必须以 pending 建议等待用户确认。
- 接受主题词建议后，后续 `groups suggest` 自动使用新词典。
- 接受正式分组建议后，可反哺主题词建议，形成可审查学习闭环。
- 保留内置主题词典作为默认 fallback，确保离线和无配置场景可运行。

**Non-Goals:**

- 不让 AI 直接改正式分组、正式成员或 tracked sector 状态。
- 不自动把所有市场热词写入主题词典。
- 不实现完整行业知识图谱或全量行业分类体系。
- 不把主题词典当成正式分组事实；主题词只影响建议生成和候选过滤。

## Decisions

### 1. 使用“主题词典注册表”合并多来源

运行时构建 `ThemeRegistry`：

```text
builtin themes
  + user config themes
  + accepted learned terms
  + active group aliases/keywords/members
  - disabled terms
  - ignored/noise terms
```

优先级：

```text
ignored/noise > disabled > user config > accepted learned > active groups > builtin
```

理由：

- 用户配置必须能覆盖内置默认。
- 已确认分组有很强的本地语义价值，应参与匹配。
- 噪声词优先级最高，避免“本月解禁”等再次污染建议。

替代方案：

- 继续只用代码常量。放弃原因：新主题维护慢。
- 只从数据库读取。放弃原因：第一版需要保留可读、可版本化的默认词典。

### 2. 配置文件先行，数据库记录学习结果

采用混合持久化：

```text
config/sector_group_themes.json
  - 用户可读可编辑的主题词典、禁用词、噪声词

数据库表
  - pending/accepted/ignored 主题词建议
  - accepted learned terms
  - 建议 evidence 和 AI 判断结果
```

理由：

- 配置文件适合人工维护和版本化。
- 数据库适合保存建议状态、审查记录和 evidence。
- 两者组合能同时满足可控和可学习。

### 3. 主题词建议独立于正式分组建议

新增主题词建议概念：

```text
ThemeTermSuggestion
- suggestion_type: add_to_existing_theme / create_theme / mark_noise / disable_term
- target_theme_name
- suggested_theme_name
- term
- normalized_key
- status: pending / accepted / ignored / expired
- confidence
- reason
- evidence_json
```

主题词建议不直接创建分组，不直接添加成员，不改变 sector 状态。接受后只影响主题词典或噪声词表。

替代方案：

- 复用 `SectorGroupSuggestion`。放弃原因：分组建议和词典学习的生命周期、动作结果不同，混在一起容易误操作。

### 4. 候选发现使用多源证据评分

候选来源：

```text
market_sectors.sector_name
cls_watch_data.title/content/sectors
market_summaries content or structured labels
accepted sector group suggestions
active group aliases/keywords/members
```

候选评分示例：

```text
+3 出现在 market_summary 主线/策略/观察段
+2 出现在 market_sectors 强势/弱势榜
+2 多次出现在 CLS 看盘标题
+2 与已有主题成员同日共现
+3 AI 判断属于某主题
-5 命中噪声词或制度属性词
-3 AI 判断跨主题或不确定
```

达到阈值后生成 pending 主题词建议；未达阈值只保留诊断 evidence，不进入用户待办。

### 5. AI 只做归属判断和解释

AI 输入：

- 候选词及上下文证据。
- 已有主题列表、成员、别名、噪声词。
- 相关市场总结片段和 CLS 标题。
- 明确约束：只能建议归属、创建新主题或标记噪声，不能修改正式数据。

AI 输出 JSON：

```json
{
  "action": "add_to_existing_theme",
  "target_theme_name": "人形机器人链",
  "term": "智能机器",
  "confidence": 0.83,
  "reason": "与机器人概念同日领涨，并在市场总结中作为机器人主线出现",
  "evidence_refs": ["market_sectors:2026-05-15", "market_summary:2026-05-15"]
}
```

无效 JSON、低置信或违反约束时，系统只能生成低置信诊断或丢弃，不写入 pending 建议。

### 6. CLI 分为词典管理和建议审查

建议命令：

```text
wchat ai sector-trends groups themes
wchat ai sector-trends groups themes show --theme 人形机器人链
wchat ai sector-trends groups themes validate
wchat ai sector-trends groups themes add --theme 人形机器人链 --member 智能机器
wchat ai sector-trends groups themes remove --theme 人形机器人链 --member 智能机器
wchat ai sector-trends groups themes ignore-term --term 本月解禁

wchat ai sector-trends groups themes suggest --days 10
wchat ai sector-trends groups themes suggestions
wchat ai sector-trends groups themes accept <suggestion-id>
wchat ai sector-trends groups themes ignore <suggestion-id>
```

`groups suggest` 继续生成分组建议；`groups themes suggest` 生成词典学习建议。两者可以串联，但不互相自动接受。

## Risks / Trade-offs

- [Risk] 自动学习固化错误主题词 -> 所有学习结果必须 pending，用户确认后才生效。
- [Risk] 配置文件与数据库学习结果冲突 -> `themes validate` 标出多归属、禁用冲突和覆盖来源。
- [Risk] 主题词越积越多导致误匹配 -> 支持禁用词和噪声词优先级；建议需要 evidence 和置信度。
- [Risk] AI 成本增加 -> 先规则评分筛选候选，只对高潜力候选调用 AI。
- [Risk] 市场总结是二次生成内容 -> evidence 中保留原始来源引用，市场总结只作为高密度线索，不作为唯一证据。

## Migration Plan

1. 保留现有 `THEME_DEFINITIONS` 作为 builtin fallback。
2. 新增配置文件加载；如果配置不存在，系统行为与现有内置词典一致。
3. 新增主题词建议表和 CLI，不迁移现有分组建议。
4. 将已接受学习结果纳入 ThemeRegistry。
5. 后续可把当前硬编码词典导出成默认配置模板，但不要求用户立即迁移。

## Open Questions

- 主题词配置文件是否默认提交到仓库，还是生成到本地 `data/` 下作为用户状态？
- 接受主题词建议后，应写入配置文件、数据库 learned terms，还是两者都写？
- 是否需要 `groups suggest --auto-discover-themes` 这种一键串联命令，还是保持 theme suggest 和 group suggest 分离？
