## 1. Progress Display Structure

- [x] 1.1 Refactor `market-summary` CLI output into persistent stage blocks for stage 1, stage 2, and stage 3
- [x] 1.2 Add an execution context section that shows trade date, execution mode, and market data strategy before stage execution begins
- [x] 1.3 Rename and close the final stage as “生成并保存市场总结” so the saved-result path is part of the final stage output

## 2. Stage Content Clarity

- [x] 2.1 Update stage 1 output to explicitly show market data source semantics such as API, cache, or offline/local data
- [x] 2.2 Update stage 2 output to show source status, input counts, and stable time-window ordering in a clearer block structure
- [x] 2.3 Keep offline-mode messaging prominent and understandable from the transcript alone

## 3. Regression Coverage

- [x] 3.1 Update CLI flow tests to verify persistent stage ordering and execution-context output
- [x] 3.2 Add assertions for market data source labels and final saved-output-path display
- [x] 3.3 Run targeted `market-summary` CLI tests to verify the refined progress transcript across success, offline, and failure paths
