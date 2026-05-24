## MODIFIED Requirements

### Requirement: 导出流程集成
`wchat export <mp_id>` SHALL export each article as a standalone HTML document and SHALL preserve the stored article HTML body instead of converting it to Markdown.

#### Scenario: 导出时生成 HTML 文件
- **WHEN** 执行 `wchat export <mp_id>` 且目标公众号存在已抓取文章
- **THEN** the system SHALL write one `.html` file per article under `output/export_articles/<mp_id>/`
- **AND** the filename SHALL use the existing date-prefix and sanitized-title naming strategy with an `.html` extension
- **AND** the system SHALL NOT generate `.md` files for the exported articles

#### Scenario: 导出正文保留 HTML
- **WHEN** an article has stored HTML content in `Article.content`
- **THEN** the exported file SHALL include that content as HTML inside the article body
- **AND** the export flow SHALL NOT call `html_to_markdown()` for the article body

#### Scenario: 导出文件包含完整 HTML 文档结构
- **WHEN** an article is exported
- **THEN** the exported file SHALL contain `<!doctype html>`, `<html>`, `<head>`, and `<body>` document structure
- **AND** it SHALL include UTF-8 charset metadata
- **AND** it SHALL include a responsive viewport meta tag
- **AND** it SHALL include the article title in the HTML `<title>` element

#### Scenario: 元信息被写入 HTML 模板
- **WHEN** an exported article has publish time, original URL, cover image URL, or summary
- **THEN** the exported HTML SHALL render those fields in a header or metadata area before the article body
- **AND** metadata values inserted into the template SHALL be HTML-escaped

#### Scenario: 空内容处理
- **WHEN** an article `content` field is empty or None
- **THEN** the system SHALL still generate a valid `.html` file with the article title and available metadata
- **AND** it SHALL NOT fail the export command

#### Scenario: 增量导出跳过已存在 HTML 文件
- **WHEN** `wchat export <mp_id>` is run without `--force`
- **AND** the target `.html` file for an article already exists
- **THEN** the system SHALL skip writing that article
- **AND** it SHALL count the article as skipped in the command summary

#### Scenario: 强制导出重建目录
- **WHEN** `wchat export <mp_id> --force` is run
- **AND** the export directory already exists
- **THEN** the system SHALL remove and recreate the export directory before writing article HTML files
- **AND** old files in that directory, including previously exported `.md` files, SHALL NOT remain after the forced export completes
