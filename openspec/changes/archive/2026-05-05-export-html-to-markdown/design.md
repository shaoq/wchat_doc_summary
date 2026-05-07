## Context

当前 `wchat export` 命令导出的 `.md` 文件中，文章正文是经 `_clean_content()` 清洗后的原始 HTML。虽然 `<script>`/`<style>` 已移除、`data-src` 已转为 `src`，但内容仍包含大量 `<div>`、`<section>`、`<p>`、`<span>` 等标签，在 Markdown 阅读器中无法正确渲染。

转换入口是 `src/cli/article.py` 中的 `build_article_markdown()` 函数（第 155-180 行），当前第 178 行直接写入 `article.content`。

## Goals / Non-Goals

**Goals:**
- 将 HTML 正文转换为格式良好的 Markdown
- 正确处理微信公众号常见元素：标题、段落、加粗/斜体、列表、引用、代码块、图片、链接
- 转换后导出的 `.md` 文件在主流 Markdown 阅读器中可读性好

**Non-Goals:**
- 不改变数据库中 HTML 的存储格式（仍保留原始 HTML）
- 不做 100% 完美的格式还原（微信公众号 HTML 结构复杂，追求"可读"而非"像素级一致"）
- 不修改抓取/清洗流程

## Decisions

### 1. 选择 `markdownify` 作为转换库

**选择**: `markdownify`（基于 BeautifulSoup）

**理由**:
- 轻量，仅依赖 `beautifulsoup4`（项目已有）
- API 简洁：`markdownify(html)` 一行调用
- 支持自定义转换规则（通过 `MarkdownConverter` 子类）
- 社区活跃，维护良好

**备选**:
- `html2text`：功能类似，但配置项较少，对复杂 HTML 结构处理不如 `markdownify` 灵活
- `pypandoc`：功能强大但依赖外部 Pandoc 二进制，过重

### 2. 转换函数独立于导出逻辑

新建 `src/utils/html_converter.py`，封装 `html_to_markdown()` 函数。`build_article_markdown()` 调用此函数。

**理由**: 关注点分离，便于单独测试和未来复用（如 API 返回 Markdown）。

### 3. 微信公众号 HTML 特殊处理

- **图片**: 确保带 `src` 的 `<img>` 转为 `![alt](src)` 格式
- **内联样式**: 忽略 `style` 属性中的样式信息，关注语义标签（`<strong>`、`<em>`、`<blockquote>` 等）
- **嵌套 `<section>`**: 微信文章常见深层嵌套 `<section>`，需正确提取文本内容
- **换行**: 微信文章 `<br>` 使用频繁，需转为 Markdown 换行

## Risks / Trade-offs

- **[复杂 HTML 格式丢失]** → 微信公众号文章可能包含复杂的排版（多栏布局、特殊字体等），这些在 Markdown 中无法完美还原。接受这一限制，优先保证文本内容可读。
- **[图片链接失效]** → 微信图片 URL 有时效性和防盗链。这是已有问题，非本次变更引入。
- **[转换性能]** → `markdownify` 基于 BeautifulSoup，对大文章可能有性能开销，但 export 是离线操作，可接受。
