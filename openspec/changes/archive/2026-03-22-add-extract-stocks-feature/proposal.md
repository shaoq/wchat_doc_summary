## Why

用户需要从公众号文章中自动提取A股股票信息（股票名称和代码），以便快速了解文章涉及的股票内容。当前系统仅支持摘要、关键词、分类和情感分析，缺少针对财经类文章的股票信息提取功能。

## What Changes

- 新增 `ArticleProcessing` 数据表，用于记录文章的 AI 处理状态和结果
- 新增 `extract_stocks` AI 处理功能，从文章内容中提取 A股股票信息
- 新增 `wchat ai extract-stocks <mp_id>` CLI 命令
- 支持 `--output` 参数导出结果到文件
- 支持 `--force` 参数强制重新处理已处理的文章

## Capabilities

### New Capabilities

- `stock-extraction`: 从公众号文章中提取A股股票信息（股票名称和代码），支持批量处理和去重

### Modified Capabilities

- 无（新增功能，不修改现有能力的需求）

## Impact

- **数据模型**: 新增 `ArticleProcessing` 表
- **服务层**: `AIProcessor` 类新增 `extract_stocks` 方法
- **CLI**: `ai` 命令组新增 `extract-stocks` 子命令
- **依赖**: 无新增外部依赖，复用现有 LLM API 调用能力
