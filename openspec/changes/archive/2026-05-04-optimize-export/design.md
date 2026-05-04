## Context

当前 `wchat export` 命令位于 `src/cli/article.py:122-196`，将所有文章导出为单个文件（json 或 markdown），支持 `--mp-id` 可选过滤。项目已有的输出目录模式：
- `output/extract_stocks/` — 股票提取结果
- `output/market_summaries/` — 市场总结

本次重写将改为按公众号分目录、每篇文章独立 markdown 文件的结构。

## Goals / Non-Goals

**Goals:**
- 按公众号 mp_id 分目录导出文章
- 每篇文章一个独立 .md 文件
- 默认增量导出，跳过已存在文件
- `--force` 支持全量覆盖

**Non-Goals:**
- 不支持 json 格式（仅 markdown）
- 不支持自定义输出路径（固定 `output/export_articles/`）
- 不支持并发写入（串行处理即可，文章量不大）
- 不做文件内容 diff 比对（仅按文件名是否存在判断增量）

## Decisions

### 1. 文件命名：`{YYYY-MM-DD}_{标题前30字}.md`

- 发布日期为空时使用 `unknown-date` 占位
- 标题中的文件系统不安全字符（`/ \ : * ? " < > |`）替换为 `_`
- 截断 30 个字符（按 Unicode 字符计数）
- 如有重名文件，追加 `_2`, `_3` 等序号

**替代方案**: 用 `article_id` 命名 — 简单但不可读，用户浏览目录时无法识别文章。

### 2. mp_id 改为必选参数

- 使用 `@click.argument('mp_id')` 替代 `@click.option`
- 减少误操作（全量导出可能导致大量文件写入）

**替代方案**: 保持可选 — 增加复杂度，需遍历所有公众号分别建目录，且使用场景不明确。

### 3. 增量判断：文件名存在即跳过

- 不做内容 diff，仅检查 `output/export_articles/<mp_id>/<filename>.md` 是否存在
- `--force` 时先清空目标目录再全量写入
- 简单可靠，避免复杂的文件内容比对逻辑

### 4. Markdown 文件结构

```markdown
# 文章标题

- **发布时间**: 2026-05-04 10:30
- **原文链接**: https://mp.weixin.qq.com/...
- **封面图片**: https://...

> AI 摘要内容...

正文内容...
```

### 5. 实现位置

仅修改 `src/cli/article.py` 中的 `export` 函数，不涉及 service 层或 model 层改动。

## Risks / Trade-offs

- **[文件名冲突]** → 发布日期相同 + 标题前 30 字相同 → 追加序号 `_2`, `_3` 解决
- **[Breaking Change]** → `wchat export` 参数完全变更 → 此项目为个人工具，影响可控
- **[标题特殊字符]** → 文件系统不安全字符可能破坏路径 → sanitize 函数统一处理
- **[大文件名]** → 30 字中文 + 日期前缀可能在某些系统超限 → 主流文件系统（APFS/ext4）支持 255 字节，30 个中文字符约 90 字节，安全
