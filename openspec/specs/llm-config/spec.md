# llm-config Specification

## Purpose
TBD - created by archiving change llm-custom-platform-config. Update Purpose after archive.
## Requirements
### Requirement: 环境变量配置

系统 SHALL 支持通过环境变量配置 LLM 参数：
- `LLM_BASE_URL`: API 基础地址
- `LLM_API_KEY`: API 密钥
- `LLM_MODEL`: 模型名称

#### Scenario: 使用智谱 GLM

- **WHEN** 用户配置 `LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/`、`LLM_API_KEY=xxx`、`LLM_MODEL=glm-4-flash`
- **THEN** 系统使用智谱 GLM 模型处理 AI 请求

#### Scenario: 使用官方 Anthropic

- **WHEN** 用户配置 `LLM_BASE_URL=https://api.anthropic.com`、`LLM_API_KEY=sk-xxx`、`LLM_MODEL=claude-3-5-haiku-latest`
- **THEN** 系统使用官方 Anthropic Claude 模型处理 AI 请求

### Requirement: 启动时配置验证

系统 SHALL 在启动时验证 LLM 配置完整性。

#### Scenario: 缺少 API Key

- **WHEN** 用户未配置 `LLM_API_KEY`
- **THEN** 系统抛出 `ValueError`，提示 "LLM API Key 未配置，请设置 LLM_API_KEY"

#### Scenario: 配置完整

- **WHEN** 用户配置了所有必需的 `LLM_*` 环境变量
- **THEN** 系统正常初始化 AIProcessor

### Requirement: 默认值

系统 SHALL 提供合理的默认配置：
- `LLM_BASE_URL` 默认为 `https://api.anthropic.com`
- `LLM_MODEL` 默认为 `claude-3-5-haiku-latest`

#### Scenario: 未指定 base_url

- **WHEN** 用户未配置 `LLM_BASE_URL`
- **THEN** 系统使用 `https://api.anthropic.com` 作为默认值

#### Scenario: 未指定 model

- **WHEN** 用户未配置 `LLM_MODEL`
- **THEN** 系统使用 `claude-3-5-haiku-latest` 作为默认模型

### Requirement: AIProcessor 简化

AIProcessor SHALL 移除 `provider` 参数，仅使用 Anthropic 兼容客户端。

#### Scenario: 初始化客户端

- **WHEN** 创建 AIProcessor 实例
- **THEN** 使用 `AsyncAnthropic(api_key=..., base_url=...)` 初始化客户端
- **AND** 使用配置的 `LLM_MODEL` 作为模型名称

