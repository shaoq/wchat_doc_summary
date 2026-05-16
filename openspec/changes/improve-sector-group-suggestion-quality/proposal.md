## Why

当前 `wchat ai sector-trends groups suggest` 在 CLS 看盘板块标签缺失时会退化为基于行情缓存的同日共现建议，容易把仅在同一天出现在强弱榜里的无关板块聚成同一组，例如把 `猪肉` 放入 `宽带提速链`。这会降低分组建议可信度，并增加用户人工筛选成本。

## What Changes

- 优化分组建议生成质量：将候选生成拆成规则候选、主题约束、AI 语义清洗、建议落库四个阶段。
- 新增内置主题/产业链词典，用于约束明显同主题的板块聚类，并过滤跨主题误聚类。
- 将 `market_sectors` 行情缓存兜底建议标记为低置信线索，避免把纯同日共现误称为强语义产业链。
- 引入 AI 对候选聚类做结构化语义清洗：判断成员是否属于同一主题/产业链，剔除无关成员，建议分组名、关系类型、置信度和理由。
- 约束 AI 只能清洗、命名和标注候选池内已有板块，不能凭空新增板块、自动接受建议或修改正式分组。
- 增强建议的 evidence/reason，展示数据来源、规则命中、AI 清洗摘要、被剔除成员和置信度依据。
- 保持现有 `groups suggestions`、`groups accept`、`groups ignore` 工作流不变；所有建议仍以 pending 状态等待用户确认。

## Capabilities

### New Capabilities
- None.

### Modified Capabilities
- `sector-group-tracking`: 提升分组建议质量，要求基于主题约束和 AI 语义清洗生成更可解释、低误聚类的 pending 建议。

## Impact

- Affected code:
  - `src/services/sector_group_service.py`: 调整建议生成流程、候选聚类、去重、证据保存和 AI 清洗调用。
  - `src/services/ai_processor.py`: 新增或复用结构化 AI 调用，用于分组候选语义清洗。
  - `src/cli/sector_trends.py`: 如有需要，补充建议输出中的数据来源、AI 清洗摘要和被剔除成员展示。
  - `tests/`: 增加规则候选、跨主题过滤、AI 清洗、AI 失败兜底、CLI 展示和回归测试。
- Data model impact:
  - 优先复用 `SectorGroupSuggestion.evidence_json` 和 `SectorGroupSuggestionMember.reason/confidence`。
  - 不要求新增表；如实现中需要更丰富的字段，优先存入现有 JSON evidence。
- Behavior impact:
  - `groups suggest` 的建议数量可能减少，但建议质量和可解释性提升。
  - 行情缓存共现不再直接产生高置信跨主题分组。
  - AI 不可用时仍可输出规则高置信建议，但不得输出明显跨主题混杂建议。
