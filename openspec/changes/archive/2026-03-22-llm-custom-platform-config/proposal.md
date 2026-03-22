# Proposal: LLM 自定义平台配置

## Why

当前 AIProcessor 只支持硬编码的 OpenAI 和 Anthropic 两种提供商：

- 模型名称硬编码在代码中（`gpt-4o-mini`、`claude-3-5-haiku-latest`）
- 无法配置自定义 API 地址
- 无法使用第三方兼容服务（如智谱 GLM、DeepSeek 等）

需要支持用户自定义 LLM 平台，只要兼容 Anthropic 协议即可使用。

## What Changes

- **BREAKING**: 移除 `openai_api_key` 和 `anthropic_api_key` 配置项
- 新增 `LLM_BASE_URL` 配置项（默认 Anthropic 官方地址）
- 新增 `LLM_API_KEY` 配置项
- 新增 `LLM_MODEL` 配置项（默认 `claude-3-5-haiku-latest`）
- AIProcessor 简化为单一 Anthropic 客户端，支持自定义 `base_url`
- 移除 `provider` 参数选择逻辑

## Capabilities

### New Capabilities

- `llm-config`: 通用 LLM 配置能力，支持任意兼容 Anthropic 协议的平台（智谱、DeepSeek、自建代理等）

### Modified Capabilities

- 无（这是全新能力）

## Impact

### 配置变更

| 文件 | 变更 |
|------|------|
| `config/settings.py` | 移除旧配置，新增 `llm_base_url`、`llm_api_key`、`llm_model` |
| `.env.example` | 更新示例配置 |

### 代码变更

| 文件 | 变更 |
|------|------|
| `src/services/ai_processor.py` | 移除 provider 参数，简化为单一 Anthropic 客户端 |

### 环境变量迁移

```bash
# 旧配置 (废弃)
OPENAI_API_KEY=sk-xxx
ANTHROPIC_API_KEY=sk-xxx

# 新配置
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
LLM_API_KEY=your-zhipu-api-key
LLM_MODEL=glm-4-flash
```

## 示例用法

智谱 GLM 配置：

```env
LLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4/
LLM_API_KEY=your-zhipu-api-key
LLM_MODEL=glm-4-flash
```

官方 Anthropic 配置：

```env
LLM_BASE_URL=https://api.anthropic.com
LLM_API_KEY=your-anthropic-key
LLM_MODEL=claude-3-5-haiku-latest
```
