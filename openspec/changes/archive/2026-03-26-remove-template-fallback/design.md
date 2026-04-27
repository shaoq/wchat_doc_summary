## Context

当前 market-summary 命令的 AI 生成流程存在降级机制：

```
cli.py
  └── try: processor.generate_market_summary()
        ├── ai_processor._load_market_summary_template()
        ├── 格式化模板
        └── 调用 LLM API
  └── except: analyzer.generate_summary()  ← 降级方案
        ├── market_analyzer._load_template()  ← 重复加载
        └── 仅格式化模板（不调用 AI）
```

问题：
1. 两处模板加载逻辑重复
2. AI 失败时输出填充模板，用户看到的是 prompt 而非总结

## Goals / Non-Goals

**Goals:**
- 模板加载逻辑只在 `ai_processor.py` 中保留一份
- AI 调用失败时直接抛出错误，提供清晰的错误信息
- 简化代码结构，移除冗余方法

**Non-Goals:**
- 不修改模板内容
- 不修改 AI 调用逻辑
- 不修改数据收集流程

## Decisions

### 1. 模板加载职责归属

**决定**: 保留在 `ai_processor.py`

**理由**:
- AI 生成是主路径，模板是为 AI prompt 服务的
- `ai_processor` 已经有完整的格式化方法（`_format_indices_for_prompt` 等）
- 移除 `market_analyzer` 中的重复实现

### 2. 错误处理方式

**决定**: 让异常向上传播，由 CLI 层统一处理

**理由**:
- Click 框架会自动捕获异常并显示错误信息
- 保持错误处理的一致性
- 用户会看到清晰的错误提示

## Risks / Trade-offs

| 风险 | 缓解措施 |
|-----|---------|
| AI 调用失败时用户无法获得任何总结 | 提供清晰的错误信息，引导用户检查 LLM 配置或重试 |

## Migration Plan

1. 修改 `cli.py` 移除降级逻辑
2. 修改 `market_analyzer.py` 移除冗余方法
3. 运行测试验证行为变更
4. 无需数据迁移
