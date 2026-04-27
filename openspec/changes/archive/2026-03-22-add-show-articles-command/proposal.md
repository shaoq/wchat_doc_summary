## Why

用户需要一个 CLI 命令来查看某个公众号下已抓取的完整文章列表。现有的 `info` 命令只显示最新 5 篇文章，无法查看全部已抓取内容，也不支持分页浏览。

## What Changes

- 新增 `wchat show <mp_id>` 命令，显示指定公众号的文章列表
- 支持分页参数：`--limit/-n` 控制每页数量，`--offset/-o` 控制偏移量
- 支持 `--all/-a` 标志一次性显示全部文章
- 输出表格包含：文章 ID、标题、原文链接、发布时间

## Capabilities

### New Capabilities

- `show-articles`: 查看公众号文章列表的 CLI 命令，支持分页和完整列表显示

### Modified Capabilities

无（这是新增功能，不修改现有规格）

## Impact

- **代码**: `src/cli.py` - 添加新的 `show` 命令
- **依赖**: 无新增依赖，复用现有的 SQLAlchemy 查询和 Rich 表格组件
