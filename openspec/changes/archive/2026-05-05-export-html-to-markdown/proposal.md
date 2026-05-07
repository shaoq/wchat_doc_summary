## Why

`wchat export` 导出的 `.md` 文件中，文章正文仍然是原始 HTML（`<div>`、`<p>`、`<img>` 等标签），在 Markdown 阅读器中无法正确渲染，导致格式混乱、可读性差。需要将 HTML 内容转换为真正的 Markdown 格式。

## What Changes

- 引入 HTML → Markdown 转换库（如 `markdownify`）
- 在 `build_article_markdown()` 中对 `article.content` 做 HTML → Markdown 转换后再写入文件
- 处理微信公众号特有的 HTML 结构（图片 `data-src`、内联样式、自定义标签等）
- 确保 Markdown 输出的格式质量（标题层级、列表、引用块、代码块、图片链接等）

## Capabilities

### New Capabilities
- `html-to-markdown`: HTML 内容到 Markdown 的转换能力，处理微信公众号文章的 HTML 结构，输出格式良好的 Markdown

### Modified Capabilities

（无现有 spec 需要修改）

## Impact

- **依赖**: 新增 `markdownify`（或 `html2text`）依赖到 `pyproject.toml`
- **代码**: 修改 `src/cli/article.py` 中的 `build_article_markdown()` 函数
- **输出**: 导出的 `.md` 文件内容格式从 HTML 变为 Markdown
- **向后兼容**: 已导出的文件不受影响，仅影响新导出行为
