## Context

The project already stores generated trend reports in two forms:

- Full Markdown reports under `output/sector_trends/` and `output/sector_groups/`.
- Structured summary rows in `sector_trend_summaries` and `sector_group_trend_summaries`.

The summary rows contain `end_date`, `trend_status`, `strength_level`, `judgement`, and `output_path`, which are sufficient to build a trend matrix. Group membership is stored separately in `sector_group_members`, allowing a group-expanded view that shows a group row followed by its member sector rows.

## Goals / Non-Goals

**Goals:**

- Provide a compact CLI trend matrix for latest and historical views.
- Provide group-expanded matrices that show member sector trends under a selected group.
- Provide Markdown export for review and archival.
- Use descriptive stage/strength data only by default.
- Reuse existing summary tables and report paths.

**Non-Goals:**

- Do not generate new AI trend reports.
- Do not define or modify trend-stage taxonomy.
- Do not add graphical UI, charts, or web dashboard in the first version.
- Do not use Markdown parsing as the primary data source.
- Do not show `action_bias` by default.

## Decisions

### 1. Add a Read-Only TrendMatrixService

Introduce a service focused on matrix assembly rather than trend generation. It should query existing summary and membership tables, produce normalized rows, and leave rendering to CLI/export helpers.

Rationale: existing `SectorTrendAnalyzer` and `SectorGroupService` own generation and history for individual objects. Matrix assembly crosses both domains and should not be mixed into AI generation logic.

Alternative considered: add matrix methods directly to both existing services. That would duplicate date-window handling and change-state calculation across sector and group paths.

### 2. Use Database Summary Rows as Source of Truth

Matrix cells should come from `SectorTrendSummary` and `SectorGroupTrendSummary`. Markdown files should only be linked via `output_path`.

Rationale: labels are already structured and validated in the database. Parsing Markdown would be brittle and unnecessary.

### 3. Start with Table and Markdown Output

The first version should support terminal table output and Markdown export. CSV or HTML can be added later if needed.

Rationale: the immediate user need is a trend table. Rich tables and Markdown fit the current CLI/document workflow without adding dependencies.

### 4. Separate Matrix Modes

The command should support three conceptual modes:

- latest snapshot: one row per sector/group with latest stage and latest change
- history matrix: rows across recent dates
- group expansion: one selected group plus its member sectors across dates

Rationale: a single global matrix and a group drilldown answer different questions. Keeping modes explicit avoids overly wide unreadable tables.

### 5. Use Descriptive Change States

Change state should describe trend movement, not recommend action. Initial mapping can use ordered stage scores per object type:

Sector stage order:

```text
高位退潮=-1, 暂无趋势=0, 短线脉冲=1, 低位启动=2, 轮动补涨=2, 分歧中继=3, 主线延续=4, 主线加强=5
```

Group stage order:

```text
高位退潮=-1, 暂无趋势=0, 短线脉冲=1, 低位启动=2, 轮动分化=3, 补涨蔓延=3, 主线扩散=4, 主线共振=5
```

The renderer can label movement as `新增`, `升温`, `延续`, `降温`, `转弱`, or `缺失`.

Rationale: this creates a stable display summary without introducing trading advice or complex scoring.

## Risks / Trade-offs

- [Risk] Matrix tables can become too wide. → Mitigation: default to a bounded recent date count and allow group-specific drilldown.
- [Risk] Group summaries currently have fewer dates than sector summaries. → Mitigation: render missing group cells as `-` and keep member sector history visible.
- [Risk] Stage score ordering may oversimplify qualitative states. → Mitigation: use scoring only for display change labels; keep original stage text in each cell.
- [Risk] Some sectors belong to multiple groups. → Mitigation: group-expanded views show the same sector under each selected group membership without merging identities.
- [Risk] Markdown export may be mistaken for generated analysis. → Mitigation: title exports as matrix/index views and link to original reports for details.
