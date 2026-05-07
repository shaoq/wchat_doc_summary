## ADDED Requirements

### Requirement: HTML 转 Markdown 核心转换
系统 SHALL 提供 `html_to_markdown()` 函数，将微信公众号文章的 HTML 内容转换为格式良好的 Markdown 文本。

#### Scenario: 基本段落转换
- **WHEN** 输入包含 `<p>` 标签的 HTML
- **THEN** 输出对应的 Markdown 段落文本，段落之间以空行分隔

#### Scenario: 标题层级转换
- **WHEN** 输入包含 `<h1>` ~ `<h6>` 标签的 HTML
- **THEN** 输出对应的 Markdown 标题（`#` ~ `######`）

#### Scenario: 行内格式转换
- **WHEN** 输入包含 `<strong>`、`<em>`、`<code>` 标签
- **THEN** 分别输出 `**bold**`、`*italic*`、`` `code` ``

#### Scenario: 图片转换
- **WHEN** 输入包含 `<img src="url" alt="text">` 标签
- **THEN** 输出 `![text](url)`

#### Scenario: 链接转换
- **WHEN** 输入包含 `<a href="url">text</a>` 标签
- **THEN** 输出 `[text](url)`

#### Scenario: 列表转换
- **WHEN** 输入包含 `<ul>/<li>` 或 `<ol>/<li>` 标签
- **THEN** 分别输出 Markdown 无序列表（`-`）或有序列表（`1.`）

#### Scenario: 引用块转换
- **WHEN** 输入包含 `<blockquote>` 标签
- **THEN** 输出 Markdown 引用（`>` 前缀）

### Requirement: 导出流程集成
`build_article_markdown()` 函数 SHALL 在写入正文前调用 `html_to_markdown()` 进行转换，而非直接写入原始 HTML。

#### Scenario: 导出时自动转换
- **WHEN** 执行 `wchat export <mp_id>` 且文章内容为 HTML
- **THEN** 导出的 `.md` 文件中正文为 Markdown 格式，不包含 HTML 标签

#### Scenario: 空内容处理
- **WHEN** 文章 `content` 字段为空或 None
- **THEN** 导出的 `.md` 文件中无正文部分，不报错

### Requirement: 转换后格式清理
转换后的 Markdown SHALL 进行基本的格式清理，确保可读性。

#### Scenario: 移除多余空行
- **WHEN** 转换结果中出现连续多个空行
- **THEN** 压缩为最多两个连续换行（一个空行）

#### Scenario: 移除残留 HTML 标签
- **WHEN** 转换后仍有未识别的 HTML 标签残留（如 `<section>`、`<span>`）
- **THEN** 仅保留标签内的文本内容
