# 任务清单

## 1. 创建新浪数据源客户端

- **文件**: `src/api/finance.py`
- **位置**: 在 `TencentFinanceClient` 类后面添加 `SinaFinanceClient` 类
- **操作**:
  - 添加 API 端点
  - 实现数据获取方法
  - 添加缓存机制

- **状态**: `[x]` (completed)

## 2. 更新 FinanceClient 类

- **文件**: `src/api/finance.py`
- **位置**: `FinanceClient.__init__` 方法
- **操作**:
  - 初始化新浪客户端
  - 调整数据源优先级顺序
- **状态**: `[x]` (completed)

## 3. 调整数据源优先级

- **文件**: `src/api/finance.py`
- **位置**: `FinanceClient` 的数据获取方法
- **操作**:
  - `get_index_data()`: 使用新浪作为主数据源
  - `get_volume_data()`: 使用新浪作为主数据源
  - `get_statistics()`: 使用新浪作为主数据源
  - `get_sector_data()`: 保留东方财富（暂时)
  - `get_limit_up_stocks()`: 保留东方财富(暂时)
- **状态**: `[x]` (completed)

## 4. 添加测试文件
- **文件**: `tests/test_finance_sina.py`
- **位置**: 新建
- **操作**:
  - 创建 `SinaFinanceClient` 测试类
  - 创建 mock fixture
  - 创建测试用例
- **状态**: `[x]` (completed)

## 5. 运行测试
- **命令**: `pytest tests/test_finance_sina.py`
- **操作**: 运行测试并验证功能
- **状态**: `[x]` (completed) - 13 tests passed

## 6. 更新文档
- **文件**: `src/api/finance.py`
- **位置**: 文件头部
- **操作**: 更新数据源说明
- **状态**: `[x]` (completed)
