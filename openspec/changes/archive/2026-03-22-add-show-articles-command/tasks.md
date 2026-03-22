## 1. CLI Implementation

- [x] 1.1 Add `show` command to `src/cli.py` after `info` command (line 626)
  - Accept `mp_id` argument
  - Add `--limit/-n` option (default 20)
  - Add `--offset/-o` option (default 0)
  - Add `--all/-a` flag

- [x] 1.2 Implement subscription validation
  - Query subscription by mp_id
  - Display error if not found

- [x] 1.3 Implement article query
  - Query articles by feed_id with count
  - Order by publish_time desc
  - Apply limit/offset when not using --all

- [x] 1.4 Implement table display
  - Create Rich Table with columns: ID, 标题, 原文链接, 发布时间
  - Truncate long titles (>40 chars) and URLs (>35 chars)
  - Handle missing URL (显示 "无") and publish_time (显示 "未知")

- [x] 1.5 Add pagination hint
  - Show current range when articles exceed displayed count
  - Suggest next offset command

## 2. Verification

- [x] 2.1 Test basic functionality: `wchat show <mp_id>`
- [x] 2.2 Test pagination: `wchat show <mp_id> --limit 10 --offset 10`
- [x] 2.3 Test show all: `wchat show <mp_id> --all`
- [x] 2.4 Test error handling: `wchat show NOT_EXIST`
