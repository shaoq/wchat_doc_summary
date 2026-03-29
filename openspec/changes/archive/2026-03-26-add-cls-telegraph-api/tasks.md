# 财联社电报 API 实施任务

## 1. Setup

- [x] 1.1 创建 src/api/cls_telegraph.py 模块文件
- [x] 1.2 定义数据模型和缓存配置（5分钟 TTL）
- [x] 1.3 定义自定义异常类 CLstTelegraphError
- [x] 1.4 实现 CLstTelegraphClient 类
  - 使用 curl 命令请求数据
  - 实现缓存机制
  - 添加错误处理
- [x] 1.5 添加日志记录

## 2. 核心实现

- [x] 2.1 实现 get_telegraph 方法
  - 调用 curl 命令获取数据
  - 解析返回数据
  - 缓存结果
- [x] 2.2 实现 _fetch_telegraph_data 方法
  - 检查缓存
  - 如果缓存有效且未过期，直接返回缓存数据
  - 如果缓存过期则调用 _fetch_with_curl
  - 解析并返回结果
  - 更新缓存
- [x] 2.3 实现 get_latest_telegraph 方法
  - 调用 get_telegraph 获取最新 50 条
  - 解析并返回结果

## 3. 集成到 FinanceClient

- [x] 3.1 添加 CLstTelegraphClient 到 FinanceClient
  - 在 __init__ 中导入新客户端
- [x] 3.2 在 get_all_market_data 中添加电报快讯获取
  - 添加 cls_telegraph 字段到返回数据中
- [x] 3.3 实现缓存清除方法
- [x] 3.4 添加单元测试
  - 测试 CLstTelegraphClient 初始化
  - 测试 get_telegraph 方法
  - 测试 _fetch_telegraph_data 方法
  - 测试缓存机制

## 4. CLI 集成

- [x] 4.1 添加 cls-telegraph 命令到 CLI
- [x] 4.2 实现命令处理函数
- [x] 4.3 添加 --json 输出支持
- [x] 4.4 测试命令执行

## 5. 文档和更新

- [x] 5.1 更新 README.md 添加新功能说明
- [x] 5.2 更新 CHANGE log
