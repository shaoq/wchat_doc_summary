## Context

`sector-trends` 当前以 `TrackedSector` 为核心，面向单个细分板块做候选发现、初始化、趋势更新和历史回看。这个模型适合保存细颗粒度证据，例如机器人、减速器、传感器、机器视觉、PEEK材料各自的强弱变化。

用户的实际复盘还需要上层主题视角，例如“人形机器人”不是替代这些细分板块，而是把多个独立板块放入同一个主线观察篮子，判断是否出现产业链共振、扩散、补涨或退潮。

现有设计刻意避免把大板块和细分方向自动合并。因此本次变更应新增映射层，而不是改变 `TrackedSector` 的颗粒度。

## Goals / Non-Goals

**Goals:**

- 在细分板块之上新增主题分组层，支持一个分组包含多个细分板块。
- 支持一个细分板块属于多个分组。
- 支持分组建议，而不是完全依赖用户手工维护。
- 支持建议新建分组、向已有分组补充成员、调整成员关系类型。
- 支持用户确认建议后再进入正式映射，避免系统静默污染分组体系。
- 支持组级趋势跟踪报告，关注共振、扩散、轮动、核心/补涨结构和风险。
- 分组跟踪默认自动补齐已跟踪成员当天缺失的单板块 AI 分析，避免分组报告依赖过期成员结论。
- 分组跟踪允许显式跳过成员刷新，用于成本或耗时敏感场景。
- 为板块和分组总结命令提供阶段式终端反馈，展示执行计划、阶段结论、成员刷新状态、关键标签和最终文件路径。
- 总结生成命令默认不输出完整报告正文，避免长链路执行后终端被大段内容淹没。
- 保持现有 `sector-trends` 单板块命令语义不变。

**Non-Goals:**

- 不把现有细分板块合并、降采样或重命名为粗颗粒度板块。
- 不在第一版实现全自动行业知识图谱。
- 不默认自动接受 AI 或规则生成的分组建议。
- 不对 candidate、inactive 或 ignored 成员默认触发 AI 分析。
- 不要求所有候选板块必须归组后才能被单独跟踪。
- 不在生成命令中提供完整报告阅读体验；完整内容查看由 `show` 或后续专用查看参数承担。

## Decisions

### 1. 新增 `SectorGroup` 和多对多成员映射

选择：

```text
SectorGroup
- id
- canonical_name
- aliases
- keywords
- description
- status
- created_at
- updated_at

SectorGroupMember
- group_id
- sector_id
- relation_type
- weight
- source
- confidence
- created_at
- updated_at
```

`SectorGroupMember` 对 `(group_id, sector_id)` 做唯一约束。

理由：

- 一个主题组需要包含多个细分板块。
- 一个细分板块可能同时属于多个主题，例如 AI芯片可同时属于半导体、算力链、国产替代。
- `TrackedSector.category` 只能表达单值分类，不适合表达复杂产业链归属。

替代方案：

- 在 `TrackedSector` 上加 `parent_group_id`。放弃原因：无法表达多归属。
- 使用 `aliases` 表示归拢。放弃原因：别名是同义关系，不能表达“减速器属于人形机器人产业链”这种成员关系。

### 2. 分组成员关系保留交易语义

成员关系类型使用一组受控枚举：

```text
core / upstream / downstream / material / equipment / catalyst / related
```

理由：

- 组级报告需要区分核心方向、上游零部件、材料、补涨和相关催化。
- 只保存成员列表会让组级分析退化为简单拼接。

替代方案：

- 只用自由文本标签。放弃原因：CLI 展示、过滤和测试都不稳定。

### 3. 分组建议独立存储，用户确认后才生效

新增建议模型：

```text
SectorGroupSuggestion
- id
- suggestion_type       # new_group / add_members / update_members
- target_group_id
- suggested_group_name
- status                # pending / accepted / ignored / expired
- confidence
- reason
- evidence_json
- created_at
- updated_at

SectorGroupSuggestionMember
- suggestion_id
- sector_id
- suggested_relation_type
- current_relation_type
- suggested_weight
- current_weight
- confidence
- reason
```

理由：

- 系统可以主动给出归组建议，但正式映射必须由用户确认。
- 建议需要可查看、可部分接受、可忽略、可去重。
- 同一结构可表达新建组、补充已有组、调整成员关系。

替代方案：

- `groups suggest` 只打印建议不落库。放弃原因：无法去重、无法稍后接受、无法记录忽略状态。
- 高置信建议自动生效。放弃原因：分组语义会影响后续跟踪和报告，第一版不应静默修改。

### 4. 建议生成优先补充已有分组，其次新建分组

建议生成顺序：

```text
1. 已有正式成员：跳过
2. 已有 pending 建议：更新证据和置信度，不重复创建
3. 命中已有分组：生成 add_members 或 update_members
4. 没有合适分组：生成 new_group
```

匹配已有分组时使用：

- 分组名、别名、关键词命中。
- 与已有成员在近期数据中共现。
- 与分组描述和成员结构相似。
- 可选 AI 判断。

理由：

- 市场跟踪中更常见的是已有主题逐步补入新细分方向，例如人形机器人组补入丝杠、灵巧手、PEEK材料。
- 优先补充已有分组可以避免主题越用越散。

### 5. 建议可以使用 candidate 板块，但正式跟踪要尊重状态

板块状态参与规则：

```text
tracked:
  可用于建议，也可直接用于正式组级跟踪。

candidate:
  可用于分组建议；接受建议时默认提升为 tracked，允许 --keep-status。

inactive:
  默认不参与建议和组级更新，除非显式 include。

ignored:
  默认完全排除。
```

理由：

- 如果排除 candidate，系统很难发现“新候选应该补进已有主题”。
- 如果接受建议后仍默默保持 candidate，组级跟踪可能出现用户已确认主题关系但成员不参与跟踪的割裂。
- 默认提升为 tracked 更符合“接受归组”的用户意图，但必须在 CLI 输出中明确展示状态变化。

### 6. 组级更新默认补齐已跟踪成员的当天分析

默认行为：

```text
groups update --group 人形机器人
  -> 读取已确认成员
  -> 检查 tracked 成员是否已有目标日期 SectorTrendSummary
  -> 对缺失目标日期报告的 tracked 成员执行单板块 update
  -> 读取成员目标日期或最新 SectorTrendSummary
  -> 收集成员近期基础证据
  -> 生成组级报告
  -> 标注每个成员的新鲜度
```

显式控制：

```text
groups update --group 人形机器人 --no-refresh-members
  -> 不触发单板块 AI 分析，只使用已有成员总结和近期基础证据

groups update --group 人形机器人 --refresh-members --force
  -> 强制刷新全部 tracked 成员，再生成组级报告
```

理由：

- 分组总结的主要价值是主线级判断，如果成员结论过期，会让组级判断天然滞后。
- 默认补齐缺失成员可以让组级报告基于目标日期的成员分析，符合“跟踪”语义。
- 成本和耗时风险通过 CLI 输出刷新计划、`--limit`、`--continue-on-error`、`--no-refresh-members` 和 `--force` 控制。
- 组级报告仍要展示 freshness，说明哪些成员是本次刷新、哪些已是当日报告、哪些缺少正式分析。

### 7. CLI 使用 `sector-trends groups` 子命令组

建议命令：

```text
wchat ai sector-trends groups ls
wchat ai sector-trends groups show --group <name>
wchat ai sector-trends groups create --group <name>
wchat ai sector-trends groups add --group <name> --sector <name> --type <relation>
wchat ai sector-trends groups suggest --days N
wchat ai sector-trends groups suggestions
wchat ai sector-trends groups accept <suggestion-id>
wchat ai sector-trends groups ignore <suggestion-id>
wchat ai sector-trends groups update --group <name>
wchat ai sector-trends groups history --group <name>
```

理由：

- 保持 `sector-trends` 作为板块趋势工作台入口。
- 分组生命周期和单板块生命周期相关但不同，独立子命令更清晰。

### 8. 总结命令采用阶段式终端反馈，不默认输出正文

单板块更新使用类似 `market-summary` 的阶段输出：

```text
板块: 减速器
交易日: 2026-05-16
执行模式: 在线
回看窗口: 10 天

[1/4] 初始化板块
  v 已处于 tracked 状态

[2/4] 收集板块证据
  v 证据收集完成
      v 行情强弱榜: 3 条
      v 看盘标签: 5 条
      ~ 证据质量: 偏稀疏

[3/4] 生成趋势总结
  v AI 生成完成 (耗时 12.3s)
      趋势: 低位启动
      强度: 中
      倾向: 观察

[4/4] 保存结果
  v 保存完成
      报告: output/sector_trends/减速器/2026-05-16.md
```

分组更新需要额外展示成员刷新计划和成员刷新结果：

```text
分组: 人形机器人
交易日: 2026-05-16
执行模式: 默认刷新缺失 tracked 成员
成员数: 6

[1/5] 检查成员状态
  v 检查完成
      今日已更新: 机器人、减速器
      待刷新: 丝杠、灵巧手、PEEK材料
      跳过 candidate: 机器视觉

[2/5] 刷新成员板块
  v 丝杠: 已更新 -> output/sector_trends/丝杠/2026-05-16.md
  v 灵巧手: 已更新 -> output/sector_trends/灵巧手/2026-05-16.md
  x PEEK材料: 失败，继续执行

[3/5] 收集分组证据
  v 证据收集完成
      成员报告: 4 份
      原始证据: 12 条
      缺失/失败成员: 1 个

[4/5] 生成分组总结
  v AI 生成完成 (耗时 18.6s)
      组级状态: 主线扩散
      核心成员: 机器人、减速器

[5/5] 保存结果
  v 保存完成
      分组报告: output/sector_groups/人形机器人/2026-05-16.md
```

批量命令使用逐项摘要表，不输出任何报告正文：

```text
批量更新分组趋势
目标: tracked 分组
数量: 4
成员刷新: 默认刷新缺失 tracked 成员

[1/4] 人形机器人  已更新  成员刷新 3/4  output/sector_groups/人形机器人/2026-05-16.md
[2/4] 半导体      已更新  成员刷新 2/2  output/sector_groups/半导体/2026-05-16.md
[3/4] 算力链      失败    成员刷新失败  -

批量更新完成
  成功: 3
  失败: 1
  成员刷新成功: 9
  成员刷新失败: 2
```

理由：

- 板块和分组总结链路包含初始化、证据收集、成员刷新、AI 生成、保存等多个环节，阶段式输出比单个 spinner 更容易定位进度和失败点。
- 报告正文可能较长，默认打印会淹没关键执行结果；生成命令应优先告诉用户产物是否成功、保存在哪里、关键标签是什么。
- `show`、`history` 或显式内容查看参数更适合承担报告阅读。

## Risks / Trade-offs

- [Risk] 系统建议错误归组 → 默认只创建 pending 建议，用户确认后才生效。
- [Risk] 同一板块多归属导致组级报告重复引用 → 报告按分组独立生成，多归属是预期行为；CLI 详情展示成员所属分组帮助用户理解。
- [Risk] candidate 接受后自动提升 tracked 扩大跟踪池 → CLI 必须明确显示状态变化，并提供 `--keep-status`。
- [Risk] 组级更新默认触发多个成员 AI 调用导致成本和耗时上升 → 更新前展示成员刷新计划，支持 `--no-refresh-members`、`--limit`、`--continue-on-error` 和 `--force` 控制执行范围。
- [Risk] 组级更新仍可能引用过期成员报告 → 报告必须展示成员 freshness，并标注未成功刷新或被跳过的成员。
- [Risk] AI 建议不可解释 → 每条建议必须保存 reason、confidence 和 evidence_json。
- [Risk] 分组建议过多影响可读性 → 建议列表支持 status、confidence、type、group 过滤，并对重复 pending 建议做合并更新。
- [Risk] 阶段式 CLI 输出过多影响批量更新可读性 → 单个更新显示阶段细节，`--all` 批量更新默认显示逐项摘要和最终统计，必要时后续再扩展 verbose 模式。

## Migration Plan

1. 新增表和索引，不改写现有 `tracked_sectors` 与 `sector_trend_summaries`。
2. 初始状态下没有任何正式分组，现有单板块命令行为不变。
3. 用户可手动创建分组，或运行 suggest 生成 pending 建议。
4. 如需回滚，删除新增命令入口并保留新增表；既有单板块数据不受影响。

## Open Questions

- 第一版是否启用 AI 分组建议，还是先实现规则/共现建议并预留 AI 接口？
- `relation_type` 的枚举是否需要根据后续使用再扩充，例如加入 `application` 或 `policy`？
- 组级报告输出路径采用 `output/sector_groups/{group}/{date}.md` 还是放在现有 `output/sector_trends/_groups/{group}/{date}.md`？
