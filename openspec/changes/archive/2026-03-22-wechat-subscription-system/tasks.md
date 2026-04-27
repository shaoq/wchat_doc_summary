# Tasks: 微信公众号文章订阅系统

## Overview

| Phase | Task | Owner | Status |
|-------|------|-------|--------|
| Phase 1 | 基础设施 | infrastructure-engineer | ✅ Completed |
| Phase 2 | API 层 | api-engineer | ✅ Completed |
| Phase 3 | 服务层 | service-engineer | ✅ Completed |
| Phase 4 | AI 集成 | ai-engineer | ✅ Completed |
| Phase 5 | CLI & 测试 | cli-engineer | ✅ Completed |

---

## Phase 1: 基础设施

### 1.1 项目结构
- [x] 创建 src/api/, src/models/, src/services/, src/storage/ 目录
- [x] 创建 config/, data/, tests/, scripts/ 目录
- [x] 配置 pyproject.toml

### 1.2 配置管理
- [x] config/settings.py - pydantic-settings 配置
- [x] .env.example 环境变量模板

### 1.3 数据模型
- [x] src/models/schema.py - Feed, Article, Auth 模型

### 1.4 数据库操作
- [x] src/storage/database.py - 异步数据库操作
- [x] CRUD 基类实现

---

## Phase 2: API 层

### 2.1 微信读书客户端
- [x] src/api/weread.py - WeReadClient 类
- [x] get_login_qrcode() - 获取登录二维码
- [x] get_login_result() - 获取登录结果
- [x] get_mp_info() - 获取公众号信息
- [x] get_articles() - 获取文章列表

### 2.2 文章抓取
- [x] src/api/article.py - 文章内容抓取
- [x] fetch_article_content() - 抓取 HTML
- [x] parse_article_html() - 解析文章
- [x] extract_images() - 提取图片

---

## Phase 3: 服务层

### 3.1 订阅管理
- [x] src/services/subscription.py - SubscriptionService
- [x] add_subscription() - 添加订阅
- [x] remove_subscription() - 取消订阅
- [x] list_subscriptions() - 列出订阅
- [x] update_sync_time() - 更新同步时间

### 3.2 文章抓取
- [x] src/services/fetcher.py - FetcherService
- [x] fetch_feed() - 抓取指定公众号
- [x] fetch_all() - 抓取所有订阅
- [x] fetch_incremental() - 增量抓取
- [x] get_mp_info_from_article() - 从 URL 获取公众号信息

### 3.3 认证服务
- [x] src/services/auth.py - AuthService
- [x] start_login() - 开始登录流程
- [x] check_login() - 检查登录状态
- [x] get_current_token() - 获取当前 Token
- [x] logout() - 登出

---

## Phase 4: AI 集成

### 4.1 AI 处理服务
- [x] src/services/ai_processor.py - AIProcessor
- [x] summarize() - 生成摘要
- [x] extract_keywords() - 提取关键词
- [x] classify() - 智能分类
- [x] analyze_sentiment() - 情感分析
- [x] batch_summarize() - 批量处理

### 4.2 多提供商支持
- [x] OpenAI 集成 (gpt-4o-mini)
- [x] Anthropic 集成 (claude-3-5-haiku)

---

## Phase 5: CLI & 测试

### 5.1 CLI 命令
- [x] src/cli.py - 完整 CLI 实现
- [x] init, login, logout 命令
- [x] subscribe, unsubscribe 命令
- [x] fetch, list, info, article 命令
- [x] export 命令
- [x] ai 子命令组

### 5.2 启动脚本
- [x] scripts/run.py - Python 启动脚本
- [x] scripts/start.sh - Shell 启动脚本
- [x] 定时调度功能
- [x] 日志记录

### 5.3 测试
- [x] tests/test_api.py - API 层测试 (15 个)
- [x] tests/test_services.py - 服务层测试 (16 个)
- [x] tests/test_storage.py - 存储层测试 (17 个)
- [x] 48 个测试全部通过

---

## Future Tasks

### 待实现
- [ ] Web UI 界面
- [ ] RSS 输出支持
- [ ] 多账号管理
- [ ] 文章全文搜索
- [ ] 消息推送通知
- [ ] 搜狗微信搜索集成（按名称搜索公众号）
