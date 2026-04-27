# Tasks: LLM 自定义平台配置

## 1. 配置变更

- [x] 1.1 更新 `config/settings.py`：移除 `openai_api_key` 和 `anthropic_api_key` 配置项
- [x] 1.2 更新 `config/settings.py`：添加 `llm_base_url`、`llm_api_key`、`llm_model` 配置项
- [x] 1.3 创建 `.env.example` 文件，包含智谱和 Anthropic 的配置示例

## 2. AIProcessor 重构

- [x] 2.1 更新 `src/services/ai_processor.py`：移除 `provider` 参数
- [x] 2.2 更新 `src/services/ai_processor.py`：简化客户端初始化为单一 Anthropic 客户端
- [x] 2.3 更新 `src/services/ai_processor.py`：添加 `base_url` 参数支持
- [x] 2.4 更新 `src/services/ai_processor.py`：使用配置的 `llm_model` 作为模型名称
- [x] 2.5 移除 `_call_openai` 方法，保留 `_call_anthropic`

## 3. 测试与验证

- [x] 3.1 更新测试用例以适配新的配置结构
- [x] 3.2 验证智谱 GLM 配置可用
- [x] 3.3 验证默认 Anthropic 配置可用
