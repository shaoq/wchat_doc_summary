# Design: LLM 自定义平台配置

## Context

当前 AIProcessor 使用硬编码的提供商选择逻辑：

```
┌─────────────────────────────────────────────────────────────┐
│                     AIProcessor (当前)                       │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   if provider == "openai":                                  │
│       client = AsyncOpenAI(api_key=...)                     │
│       model = "gpt-4o-mini"  # 硬编码                       │
│   else:                                                     │
│       client = AsyncAnthropic(api_key=...)                  │
│       model = "claude-3-5-haiku-latest"  # 硬编码           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

目标：简化为单一 Anthropic 客户端，支持自定义 base_url，兼容所有 Anthropic 协议平台。

## Goals / Non-Goals

**Goals:**
- 支持任意兼容 Anthropic 协议的 LLM 平台
- 配置项简洁：base_url + api_key + model
- 代码结构简化，移除 provider 选择逻辑

**Non-Goals:**
- 不支持 OpenAI 协议（用户确认只需 Anthropic 协议）
- 不支持多提供商并行
- 不保留向后兼容（BREAKING CHANGE）

## Decisions

### 1. 使用 Anthropic SDK + base_url 参数

**选择**: 使用 `anthropic` 包的 `AsyncAnthropic` 客户端，通过 `base_url` 参数指向第三方服务。

**理由**:
- Anthropic SDK 原生支持自定义 base_url
- 智谱、DeepSeek 等主流平台都兼容 Anthropic 协议
- 避免引入额外的 SDK 依赖

**替代方案**:
- 使用 httpx 直接调用 → 需要自行处理协议细节，维护成本高
- 使用 litellm 等统一 SDK → 引入新依赖，过度设计

### 2. 配置项命名：`LLM_*` 前缀

**选择**: 使用 `LLM_BASE_URL`、`LLM_API_KEY`、`LLM_MODEL` 统一前缀。

**理由**:
- 语义清晰，表明是通用 LLM 配置
- 不绑定特定提供商名称
- 便于扩展（未来可加 `LLM_TIMEOUT` 等）

### 3. 移除 OpenAI 支持

**选择**: 完全移除 OpenAI 客户端代码和配置。

**理由**:
- 用户确认只需 Anthropic 协议
- 简化代码，减少维护负担
- 如果未来需要，可以重新添加

## Risks / Trade-offs

| 风险 | 缓解措施 |
|------|----------|
| BREAKING CHANGE - 现有用户需迁移配置 | 在 proposal 中明确说明迁移步骤 |
| 第三方平台可能有细微协议差异 | 使用主流平台（智谱）测试验证 |
| 模型名称配置错误导致调用失败 | 启动时验证配置完整性，提供清晰错误信息 |

## Migration Plan

### 步骤

1. 更新 `config/settings.py`，添加新配置项
2. 更新 `src/services/ai_processor.py`，简化客户端初始化
3. 创建/更新 `.env.example`
4. 运行测试确保功能正常

### 用户迁移

```bash
# 旧配置
ANTHROPIC_API_KEY=sk-xxx

# 新配置
LLM_BASE_URL=https://api.anthropic.com
LLM_API_KEY=sk-xxx
LLM_MODEL=claude-3-5-haiku-latest
```

## Open Questions

无。
