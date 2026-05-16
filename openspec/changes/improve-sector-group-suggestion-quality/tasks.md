## 1. Candidate Generation

- [x] 1.1 Audit current `SectorGroupService.generate_suggestions` flow and isolate candidate collection, co-occurrence building, suggestion persistence, and duplicate refresh responsibilities
- [x] 1.2 Add a typed internal representation for group suggestion candidates, including members, source signals, co-occurrence counts, theme matches, confidence, and evidence metadata
- [x] 1.3 Preserve CLS watch `sectors` as the preferred co-occurrence source and mark `market_sectors` fallback candidates as weak market-cache signals
- [x] 1.4 Ensure ignored sectors remain excluded and inactive sectors remain excluded unless existing behavior explicitly includes them

## 2. Theme Constraints

- [x] 2.1 Add first-stage built-in semantic theme definitions for current high-signal areas such as 光伏产业链, 锂电储能链, 军工信息链, 医药服务链, 消费农业链, and 新能源电力链
- [x] 2.2 Implement theme matching for candidate sectors using canonical names and `SectorIdentity.comparison_key`
- [x] 2.3 Split or reject cross-theme market-cache clusters instead of persisting mixed-theme `new_group` suggestions
- [x] 2.4 Generate deterministic rule-only suggestions for coherent theme matches when AI is unavailable or disabled

## 3. AI Semantic Cleaning

- [x] 3.1 Add an AI prompt/template for sector group candidate cleaning with strict JSON output
- [x] 3.2 Implement an AI cleaning method that accepts only existing candidate sector IDs and returns accepted members, rejected members, group name, relation types, confidence, and reasons
- [x] 3.3 Validate AI output against the candidate pool, confidence thresholds, minimum member counts, and allowed relation types
- [x] 3.4 Fall back safely when AI fails, times out, returns invalid JSON, adds unknown members, or produces low-confidence mixed-theme results
- [x] 3.5 Ensure AI cleaning never creates `TrackedSector` records, accepts suggestions, or mutates formal group memberships

## 4. Suggestion Persistence and Review

- [x] 4.1 Persist cleaned suggestions into existing `SectorGroupSuggestion` and `SectorGroupSuggestionMember` tables
- [x] 4.2 Store source signals, theme matches, AI cleaning status, accepted members, rejected members, and confidence rationale in `evidence_json`
- [x] 4.3 Refresh equivalent pending suggestions instead of creating duplicates after cleaning changes the member list or group name
- [x] 4.4 Keep ignored suggestions suppressed unless new evidence materially changes
- [x] 4.5 Update suggestion reasons so weak market-cache co-occurrence is clearly labelled as a clue rather than confirmed industry-chain evidence

## 5. CLI Output

- [x] 5.1 Keep `wchat ai sector-trends groups suggest` command syntax compatible
- [x] 5.2 Update `groups suggestions` display only if needed to expose cleaned final members, source labels, confidence, and concise cleaning summaries
- [x] 5.3 Ensure rejected AI-cleaned members are available through stored evidence or a testable service return path

## 6. Tests

- [x] 6.1 Add service tests proving market-cache-only mixed clusters such as 宽带提速 + 猪肉 do not create a mixed `new_group` suggestion
- [x] 6.2 Add service tests proving coherent theme clusters such as 光伏 + TOPCon + BC电池 + HIT电池 + 钙钛矿 create a cleaned pending suggestion
- [x] 6.3 Add AI cleaning tests for accepted clusters, rejected members, unknown AI-added members, invalid JSON, low confidence, and timeout/failure fallback
- [x] 6.4 Add duplicate refresh and ignored-suggestion suppression tests for cleaned suggestions
- [x] 6.5 Add CLI tests for `groups suggest` and `groups suggestions` output after semantic cleaning
- [x] 6.6 Run focused sector group tests and relevant sector trend regression tests

## 7. Verification

- [x] 7.1 Run OpenSpec validation/status checks for `improve-sector-group-suggestion-quality`
- [x] 7.2 Run GitNexus impact analysis before editing service symbols during implementation
- [x] 7.3 Run GitNexus detect-changes before committing implementation changes
