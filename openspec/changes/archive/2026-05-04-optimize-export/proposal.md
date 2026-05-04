## Why

当前 `wchat export` 命令将所有文章导出为单一文件（json/markdown），不支持按公众号分目录、单文章单文件的组织方式。随着文章数量增长，单文件导出难以管理和阅读，也不便于增量更新。

## What Changes

- **BREAKING**: `--mp-id` 从可选参数变为必选参数，强制指定导出的公众号
- 移除 `--format` 选项，仅支持 markdown 格式输出
- 移除 `--output` 选项，输出路径固定为 `output/export_articles/<mp_id>/` 目录
- 每篇文章导出为独立的 `.md` 文件，文件名格式 `{YYYY-MM-DD}_{标题前30字}.md`
- 默认增量导出：已存在的同名文件自动跳过
- 新增 `--force` 选项：强制全量导出，覆盖已存在文件
- 单篇文章 Markdown 结构包含：标题、元信息（发布时间/原文链接/封面）、AI 摘要、正文内容

## Capabilities

### New Capabilities
- `article-export`: 文章导出功能 — 按公众号分目录、单文件 markdown、增量/全量导出

### Modified Capabilities
<!-- 无需修改现有 spec -->

## Impact

- **代码**: `src/cli/article.py` 中 `export` 命令需重写
- **CLI 接口**: `wchat export` 参数变更，为 breaking change
- **文件系统**: 使用 `output/export_articles/` 目录，与现有 `output/extract_stocks/`、`output/market_summaries/` 保持一致
- **依赖**: 无新增依赖
