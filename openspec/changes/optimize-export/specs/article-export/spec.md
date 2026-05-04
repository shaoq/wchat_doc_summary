## ADDED Requirements

### Requirement: Export directory structure
系统 SHALL 将文章导出到 `output/export_articles/<mp_id>/` 目录下，其中 `<mp_id>` 为公众号的唯一标识。系统 SHALL 自动创建所需目录（`mkdir -p` 语义）。

#### Scenario: Export with valid mp_id
- **WHEN** 用户执行 `wchat export MP_WXS_xxx`
- **THEN** 系统创建 `output/export_articles/MP_WXS_xxx/` 目录并将文章文件写入其中

#### Scenario: Export with non-existent mp_id
- **WHEN** 用户执行 `wchat export MP_WXS_nonexist`
- **THEN** 系统显示错误提示 `订阅不存在: MP_WXS_nonexist`

### Requirement: One article per file
系统 SHALL 为每篇文章生成一个独立的 `.md` 文件。文件名格式为 `{YYYY-MM-DD}_{标题前30字}.md`。

#### Scenario: Normal article export
- **WHEN** 文章标题为 "深度解读：2026年AI行业发展趋势分析"，发布时间为 2026-05-04
- **THEN** 文件名为 `2026-05-04_深度解读：2026年AI行业发展趋势分析.md`

#### Scenario: Article with special characters in title
- **WHEN** 文章标题包含 `/ \ : * ? " < > |` 等文件系统不安全字符
- **THEN** 这些字符 SHALL 被替换为 `_`

#### Scenario: Article with no publish time
- **WHEN** 文章的 publish_time 为空
- **THEN** 文件名使用 `unknown-date` 作为日期前缀

#### Scenario: Duplicate filenames
- **WHEN** 同一目录下已存在同名文件
- **THEN** 系统 SHALL 追加 `_2`, `_3` 等序号以避免覆盖

### Requirement: Markdown file content structure
每个导出的 .md 文件 SHALL 包含以下结构：一级标题为文章标题，元信息列表（发布时间、原文链接、封面图片），AI 摘要以 blockquote 格式，正文内容。

#### Scenario: Full article with all fields
- **WHEN** 文章包含完整的 title、publish_time、original_url、pic_url、summary、content
- **THEN** 导出文件包含所有字段，格式为 Markdown

#### Scenario: Article with missing optional fields
- **WHEN** 文章的 summary 或 pic_url 为空
- **THEN** 对应字段 SHALL 被省略，不输出空行

### Requirement: mp_id as required argument
`mp_id` SHALL 为必选的位置参数（argument），而非可选的 option。

#### Scenario: Export without mp_id
- **WHEN** 用户执行 `wchat export` 不带任何参数
- **THEN** Click 框架 SHALL 显示用法错误提示

### Requirement: Incremental export by default
系统 SHALL 默认以增量模式导出：当目标文件已存在时自动跳过，不覆盖。

#### Scenario: Incremental skip existing file
- **WHEN** 目标目录下已存在同名文件，且未指定 `--force`
- **THEN** 系统 SHALL 跳过该文章并记录跳过数量

#### Scenario: All articles already exported
- **WHEN** 所有文章文件均已存在于目标目录
- **THEN** 系统 SHALL 显示 "没有新文章需要导出"

### Requirement: Force full export
系统 SHALL 支持 `--force` 选项，强制全量导出并覆盖已存在文件。

#### Scenario: Force export
- **WHEN** 用户执行 `wchat export MP_WXS_xxx --force`
- **THEN** 系统 SHALL 清空目标目录后重新导出所有文章

### Requirement: Export summary
导出完成后，系统 SHALL 显示汇总信息：导出文章数量、跳过数量（增量模式）、输出目录路径。

#### Scenario: Export with some skipped
- **WHEN** 100 篇文章中有 20 篇已存在（增量模式）
- **THEN** 显示 "导出 80 篇，跳过 20 篇，共 100 篇"
