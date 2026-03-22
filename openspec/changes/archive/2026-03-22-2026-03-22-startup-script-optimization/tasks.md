# Tasks: 启动脚本优化

## Status: Completed

## Task List

| # | Task | Status |
|---|------|--------|
| 1 | 优化环境检测流程 (Conda > venv > 系统 Python) | Done |
| 2 | 实现 `smart_install_deps()` 智能依赖安装 | Done |
| 3 | 添加 `setup-env` 命令 | Done |
| 4 | 添加 `install` 命令 | Done |
| 5 | 添加 `reinstall` 命令 | Done |
| 6 | 添加 `env-info` 命令 | Done |
| 7 | 创建 OpenSpec change 记录 | Done |

## Verification

```bash
# 1. 检查环境信息
./scripts/start.sh env-info

# 2. 创建 Conda 环境
./scripts/start.sh setup-env

# 3. 初始化系统
./scripts/start.sh init

# 4. 测试命令
./scripts/start.sh status
./scripts/start.sh help
```

## Files Changed

- `scripts/start.sh` - 优化启动脚本
- `openspec/changes/2026-03-22-startup-script-optimization/` - 变更记录
