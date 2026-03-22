# Proposal: 启动脚本优化

## Summary

优化微信公众号订阅系统的启动脚本，支持 Conda 环境管理和智能依赖安装。

## Motivation

用户需要：
1. 使用 Conda 管理虚拟环境（默认环境名 `wchat_doc`）
2. 自动检测缺失依赖并安装
3. 避免每次启动都重新安装依赖

## Proposed Solution

### 环境检测流程

```
优先级: Conda > venv > 系统 Python

1. 检测 Conda 环境 wchat_doc
2. 检测 .venv 目录
3. 使用系统 Python
```

### 智能依赖管理

```python
smart_install_deps():
1. 检查关键包是否已安装 (httpx, sqlalchemy, click, rich, pydantic, aiosqlite)
2. 已安装 → 跳过
3. 未安装 → pip install -e .
```

### 新增命令

| 命令 | 功能 |
|------|------|
| `./start.sh setup-env` | 创建 Conda 环境 wchat_doc |
| `./start.sh install` | 智能安装依赖 |
| `./start.sh reinstall` | 强制重新安装依赖 |
| `./start.sh env-info` | 显示环境信息 |

## Scope

### In Scope
- Conda 环境检测和激活
- venv 环境检测和激活
- 智能依赖安装
- 环境信息显示

### Out of Scope
- 自动创建 venv 环境
- 依赖版本锁定

## Implementation

修改文件：`scripts/start.sh`

## Success Criteria

- [x] `./start.sh env-info` 显示正确环境信息
- [x] `./start.sh setup-env` 创建 Conda 环境
- [x] `./start.sh install` 智能安装依赖
- [x] 已安装依赖时跳过重复安装

## Dependencies

- Conda (可选)
- Python 3.10+
