## Context

这类问题不直接属于功能缺陷，但会持续影响维护体验：

- [config/settings.py](/Users/jie.hua/Documents/Developments/Projects/wchat_doc/config/settings.py) 中 `weread_api_base` 被重复定义
- [README.md](/Users/jie.hua/Documents/Developments/Projects/wchat_doc/README.md) 仍只描述最初的订阅文章系统，没有反映当前 AI、股票和市场总结能力
- 仓库可见 `src/services/market_analyzer.py.bak` 及大量 `__pycache__` 产物

这些问题在多人协作和持续迭代中会不断制造误导，因此适合通过一次小范围 change 明确清理。

## Goals / Non-Goals

**Goals:**
- 收敛配置定义中的重复项
- 让 README 与当前主要功能面保持一致
- 清理不应长期进入仓库上下文的备份与缓存产物
- 为后续协作提供更干净的工程表面

**Non-Goals:**
- 不进行功能重构
- 不在本次变更中重写全部文档
- 不触碰业务逻辑实现，除非为了清理配置重复必须做极小修正

## Decisions

### 1. 配置清理以“去重且不改语义”为原则

配置层只去掉重复定义和明显噪音，不借机调整环境变量命名或默认值语义。

### 2. README 只对齐当前稳定功能面

README 更新只覆盖已存在且对用户可见的主要命令与能力，不提前写尚未实施完成的未来功能。

### 3. 仓库卫生以“删除无效产物 + 防止再次出现”为目标

对 `.bak`、`__pycache__` 等产物，既要清理现有文件，也要通过忽略策略降低再次进入仓库的概率。

## Risks / Trade-offs

- [README 更新不完整] → 以当前 CLI help 和已稳定命令面为依据更新
- [删除备份文件误伤人工留档] → 仅清理明显的派生文件和已可从版本控制恢复的备份文件
- [配置清理引发测试依赖变动] → 保持字段语义与环境变量名不变

## Migration Plan

1. 清理重复配置定义
2. 更新 README 对齐当前命令面
3. 删除备份与缓存产物
4. 补充或校正忽略策略

回滚策略：
- 若文档调整出现争议，可单独回退 README，不影响其他卫生清理

## Open Questions

- 当前仓库是否已有 `.gitignore` 覆盖 `__pycache__` 和测试缓存；如无，需要在实现阶段一并补齐
