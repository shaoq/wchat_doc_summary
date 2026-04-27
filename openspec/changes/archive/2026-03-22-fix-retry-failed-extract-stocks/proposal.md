## Why

`batch_extract_stocks` 的 `_get_processed_articles` 方法只检查 `task_type`，不检查 `status`。这导致处理失败的文章（`status='failed'`）也会被跳过，用户无法重试失败的任务，除非使用 `--force` 强制重新处理所有文章（包括已成功的）。

## What Changes

- 修改 `_get_processed_articles` 方法，只跳过 `status='success'` 的文章
- 失败的文章（`status='failed'`）应该可以被重新处理

## Capabilities

### New Capabilities

无新增能力。

### Modified Capabilities

- `ai-processing`: 修改任务重试逻辑，允许失败的任务被重新处理

## Impact

- **受影响代码**: `src/services/ai_processor.py` 中的 `_get_processed_articles` 方法
- **用户影响**: 用户可以直接重新运行命令来重试失败的文章，无需使用 `--force`
