## Why

`groups suggest` 已通过内置主题词典和 AI 清洗降低误聚类，但主题词典仍主要靠代码维护。新市场主线出现时，例如机器人主线，需要人工改代码后才能进入建议体系，难以及时响应复盘中的新主题。

本变更要把主题词典升级为可配置、可审查、可学习的体系：系统能从结构化行情、CLS 看盘和市场总结中发现主题词候选，生成待确认建议，用户接受后再写入主题词典并反哺后续分组建议。

## What Changes

- 新增可配置主题词典，合并内置默认词典、用户配置词典、已确认分组元数据和已接受主题词建议。
- 新增主题词典 CLI，用于查看主题、查看成员、校验冲突、手工新增/删除/禁用主题词。
- 新增主题词建议生成能力，从 `market_sectors`、`cls_watch_data` 标题/内容、`market_summaries` 和已有分组中发现新主题词候选。
- 引入规则评分和 AI 归属判断，判断候选词属于已有主题、新主题，还是应进入噪声/不可归组词。
- 新增主题词建议审查流：建议以 pending 状态展示，用户接受后才写入主题词典；拒绝后不会在证据无变化时反复出现。
- 支持用户接受分组建议后反哺主题词典：系统生成“是否将这些成员加入主题词典”的 pending 建议，而不是自动固化。
- 新增噪声词/不可归组词机制，过滤 `本月解禁`、`含GDR`、`送转潜力` 等交易属性或制度属性词。
- 保持正式分组、正式成员和 tracked sector 生命周期不被主题词建议自动修改。

## Capabilities

### New Capabilities
- `sector-group-theme-learning`: 可配置主题词典、主题词候选发现、AI 归属判断、主题词建议审查和接受后学习。

### Modified Capabilities
- None.

## Impact

- Affected code:
  - `src/services/sector_group_service.py`: 加载主题词典、使用动态主题匹配、分组建议反哺主题词候选。
  - New or existing theme service module: 主题词典加载、合并、校验、建议生成和持久化。
  - `src/services/ai_processor.py`: 新增主题词归属/新主题判断的结构化 AI 调用。
  - `src/cli/sector_trends.py`: 新增 `groups themes` 命令组和主题词建议 review/accept/ignore 命令。
  - `src/models/schema.py` / `src/storage/database.py`: 如采用数据库持久化，新增主题词建议和已接受主题词记录表；如采用配置文件持久化，新增配置读写和 schema 校验。
  - `tests/`: 增加配置加载、冲突校验、候选抽取、AI 归属、建议接受、噪声词过滤和 CLI 测试。
- Data impact:
  - 新增主题词典配置文件或数据库表，不迁移现有 `tracked_sectors`。
  - 既有内置词典作为 fallback，用户配置和 accepted 学习结果优先级更高。
- Behavior impact:
  - `groups suggest` 将使用动态主题词典，能更快覆盖新主线。
  - 新主题词不会自动进入正式词典，必须经过 pending 建议确认。
  - 被标记为噪声词的候选不会污染产业链分组建议。
