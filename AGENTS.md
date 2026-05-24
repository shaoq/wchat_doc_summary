# User-Level Codex Rules

## Language

- Always reply in Chinese.

## OpenSpec Workflow

- Treat `/opsx:*` as historical aliases, not required slash commands.
- Do not rely on the Codex UI to display or autocomplete `/opsx:*`.
- Map natural-language requests to the corresponding OpenSpec stage automatically.

### Natural-Language Triggers

- Enter explore mode when the user asks to analyze, discuss, plan, compare options, evaluate tradeoffs, clarify scope, or explicitly says not to change code yet.
- Treat phrases such as `先分析`, `先讨论`, `进入 explore 模式`, `先不要改代码`, `先看方案`, `帮我评估一下` as equivalent to `/opsx:explore`.
- Treat phrases such as `创建 proposal`, `生成提案`, `整理成 OpenSpec`, `把方案落成变更` as equivalent to `/opsx:propose`.
- Treat phrases such as `开始实现`, `进入实施阶段`, `按 tasks.md 做`, `开始改代码` as equivalent to `/opsx:apply`.
- Treat phrases such as `归档这个 change`, `完成后归档`, `archive 这个变更` as equivalent to `/opsx:archive`.

## Default Workflow

- For requests involving requirement design, feature planning, architecture discussion, solution analysis, tradeoff evaluation, or unclear implementation scope, default to explore mode first.
- In explore mode, do not directly modify application code or execute implementation changes.
- First analyze the requirement, inspect the codebase if needed, and summarize the conclusions in Chinese.
- After the analysis is confirmed by the user, create an OpenSpec proposal.
- Do not run the implementation stage and do not directly implement changes unless the user explicitly asks to enter the implementation stage.
- If the user only wants discussion or analysis, stay in explore mode and do not create or apply changes automatically.

## Behavior Rules

- If the user types a literal `/opsx:explore`, `/opsx:propose`, `/opsx:apply`, or `/opsx:archive`, follow that stage even if the command is not shown in the UI.
- If the user does not type a slash command but clearly expresses the intent in natural language, follow the matching OpenSpec stage anyway.
- When intent is ambiguous, prefer explore mode over implementation.
- Unless the user explicitly asks to archive, do not archive automatically.

## Priority

- These rules apply by default at user scope unless a higher-priority system, developer, or user instruction overrides them.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **wchat_doc_summary** (12781 symbols, 21130 relationships, 300 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

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
