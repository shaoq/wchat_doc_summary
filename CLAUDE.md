# 订阅文章系统 - 项目规约

## 技术栈

- Python 3.10+
- SQLite + aiosqlite
- Click + Rich (CLI)
- httpx + SQLAlchemy (API 客户端)

## OpenSpec 变更管理 (v1.2.0)

**必须** 遵循 opsx 流程进行功能变更。

### 快速路径 (Core Profile)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  /propose   │───▶│   /apply    │───▶│  /archive   │
│  创建提案   │    │  实施变更   │    │  归档完成   │
└─────────────┘    └─────────────┘    └─────────────┘
```

### 核心命令

| 命令 | 用途 | 说明 |
|------|------|------|
| `/opsx:explore` | 探索模式 | 思考、调研、明确需求（不写代码，可选） |
| `/opsx:propose` | 创建变更 | 一步创建 proposal、specs、design、tasks |
| `/opsx:apply` | 实施变更 | 按 tasks.md 执行代码修改 |
| `/opsx:archive` | 归档 | 完成后归档到 archive/ |

### 扩展命令 (可选)

| 命令 | 用途 | 说明 |
|------|------|------|
| `/opsx:new` | 创建脚手架 | 仅创建变更目录，等待指令 |
| `/opsx:continue` | 继续变更 | 逐个创建工件（精细控制） |
| `/opsx:ff` | 快速推进 | 一次生成所有规划工件 |
| `/opsx:verify` | 验证 | 检查实现是否匹配工件 |
| `/opsx:sync` | 同步规格 | 合并 delta specs 到主规格 |

### 典型工作流

```bash
# 1. 探索阶段（可选，需求不明确时使用）
/opsx:explore 如何实现文章自动分类？

# 2. 创建变更（推荐：一步到位）
/opsx:propose add-article-classification

# 3. 实施变更
/opsx:apply

# 4. 归档
/opsx:archive
```

### CLI 常用命令

```bash
openspec list              # 列出活跃变更
openspec status            # 查看工件状态
openspec show <change>     # 查看变更详情
openspec validate --all    # 验证所有变更
```

**禁止跳过 opsx 流程直接实施代码修改。**

### 执行规则

- **归档前确认**: 除非用户明确要求，否则不要自动执行 `/opsx:archive`
- 归档是不可逆操作，应等待用户确认后再执行

## 项目结构

```
wchat_doc/
├── src/                    # 源代码
│   ├── api/               # 微信读书 API 客户端
│   ├── services/          # 业务服务
│   ├── models/            # 数据模型
│   └── utils/             # 工具函数
├── scripts/               # 脚本
│   └── start.sh           # 启动脚本
├── openspec/              # OpenSpec 变更管理
│   ├── changes/           # 活跃变更
│   │   └── archive/       # 已归档变更
│   └── specs/             # 规格文档
└── tests/                 # 测试代码
```

## 常用命令

```bash
wchat --help                  # 查看帮助
wchat init                    # 初始化系统
wchat fetch                   # 抓取文章
wchat status                  # 查看状态
```

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **wchat_doc_summary** (9578 symbols, 15599 relationships, 289 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/wchat_doc_summary/context` | Codebase overview, check index freshness |
| `gitnexus://repo/wchat_doc_summary/clusters` | All functional areas |
| `gitnexus://repo/wchat_doc_summary/processes` | All execution flows |
| `gitnexus://repo/wchat_doc_summary/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
