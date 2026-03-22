#!/bin/bash
#
# 微信公众号文章订阅系统 - 启动脚本
#
# 用法:
#   ./start.sh init       # 初始化系统
#   ./start.sh fetch      # 手动抓取
#   ./start.sh scheduler  # 启动定时抓取
#   ./start.sh status     # 查看状态
#   ./start.sh interactive # 交互模式
#

set -e

# ==================== 配置 ====================
CONDA_ENV_NAME="wchat_doc"  # 默认 conda 环境名

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/.pids"

# 创建必要目录
mkdir -p "$LOG_DIR" "$PID_DIR"

# 日志文件
LOG_FILE="$LOG_DIR/wchat_$(date +%Y%m%d).log"
ERROR_LOG="$LOG_DIR/error_$(date +%Y%m%d).log"

# ==================== 工具函数 ====================

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_step() {
    echo -e "${CYAN}[STEP]${NC} $1"
}

# ==================== 环境检查 ====================

# 检查 Python 版本
check_python_version() {
    local python_cmd="${1:-python3}"
    if ! command -v "$python_cmd" &> /dev/null; then
        return 1
    fi

    local version=$($python_cmd --version 2>&1 | awk '{print $2}')
    local major=$(echo "$version" | cut -d. -f1)
    local minor=$(echo "$version" | cut -d. -f2)

    if [[ "$major" -lt 3 ]] || ([[ "$major" -eq 3 ]] && [[ "$minor" -lt 10 ]]); then
        print_error "Python 版本需要 >= 3.10，当前: $version"
        return 1
    fi

    print_info "Python 版本: $version"
    return 0
}

# 检查并激活 conda 环境
check_conda_env() {
    print_step "检查 Conda 环境..."

    # 检查 conda 是否可用
    if ! command -v conda &> /dev/null; then
        print_warning "Conda 未安装，尝试使用 venv..."
        return 1
    fi

    # 检查是否已在目标 conda 环境中
    if [[ "$CONDA_DEFAULT_ENV" == "$CONDA_ENV_NAME" ]]; then
        print_success "已在 Conda 环境: $CONDA_ENV_NAME"
        check_python_version python && return 0
        return 1
    fi

    # 如果在其它 conda 环境中
    if [[ -n "$CONDA_DEFAULT_ENV" ]]; then
        print_info "当前 Conda 环境: $CONDA_DEFAULT_ENV"
        print_info "切换到目标环境: $CONDA_ENV_NAME"
    fi

    # 初始化 conda（支持不同 shell）
    local conda_hook=""
    if [[ -f "$HOME/anaconda3/etc/profile.d/conda.sh" ]]; then
        conda_hook="$HOME/anaconda3/etc/profile.d/conda.sh"
    elif [[ -f "$HOME/miniconda3/etc/profile.d/conda.sh" ]]; then
        conda_hook="$HOME/miniconda3/etc/profile.d/conda.sh"
    elif [[ -f "/opt/anaconda3/etc/profile.d/conda.sh" ]]; then
        conda_hook="/opt/anaconda3/etc/profile.d/conda.sh"
    elif [[ -f "/opt/miniconda3/etc/profile.d/conda.sh" ]]; then
        conda_hook="/opt/miniconda3/etc/profile.d/conda.sh"
    fi

    if [[ -n "$conda_hook" ]]; then
        source "$conda_hook"
    else
        # 尝试 eval 方式
        eval "$(conda shell.bash hook 2>/dev/null)" || true
    fi

    # 尝试激活目标环境
    if conda activate "$CONDA_ENV_NAME" 2>/dev/null; then
        print_success "已激活 Conda 环境: $CONDA_ENV_NAME"
        check_python_version python && return 0
        return 1
    else
        print_warning "Conda 环境 '$CONDA_ENV_NAME' 不存在"
        print_info "创建命令: conda create -n $CONDA_ENV_NAME python=3.10 -y"
        print_info "或者运行: ./start.sh setup-env"
        return 1
    fi
}

# 检查并激活 venv 环境
check_venv_env() {
    print_step "检查 venv 环境..."

    if [[ -n "$VIRTUAL_ENV" ]]; then
        print_success "已激活 venv: $VIRTUAL_ENV"
        check_python_version python3 && return 0
        return 1
    fi

    local venv_path="$PROJECT_DIR/.venv"
    if [[ -d "$venv_path" ]] && [[ -f "$venv_path/bin/activate" ]]; then
        print_info "激活 venv 环境..."
        source "$venv_path/bin/activate"
        print_success "已激活 venv: $venv_path"
        check_python_version python3 && return 0
        return 1
    fi

    return 1
}

# 检查系统 Python
check_system_python() {
    print_step "检查系统 Python..."
    check_python_version python3
    return $?
}

# 统一的环境检查入口
setup_environment() {
    # 优先级: 1. conda  2. venv  3. 系统 Python
    if check_conda_env; then
        return 0
    fi

    if check_venv_env; then
        return 0
    fi

    if check_system_python; then
        print_warning "使用系统 Python，建议创建虚拟环境"
        return 0
    fi

    print_error "未找到可用的 Python 环境"
    print_info "建议运行: ./start.sh setup-env"
    return 1
}

# 创建 conda 环境
create_conda_env() {
    print_step "创建 Conda 环境: $CONDA_ENV_NAME"

    if ! command -v conda &> /dev/null; then
        print_error "Conda 未安装"
        print_info "请先安装 Miniconda: https://docs.conda.io/en/latest/miniconda.html"
        exit 1
    fi

    # 初始化 conda
    local conda_hook=""
    for path in "$HOME/anaconda3/etc/profile.d/conda.sh" \
                "$HOME/miniconda3/etc/profile.d/conda.sh" \
                "/opt/anaconda3/etc/profile.d/conda.sh" \
                "/opt/miniconda3/etc/profile.d/conda.sh"; do
        if [[ -f "$path" ]]; then
            conda_hook="$path"
            break
        fi
    done

    if [[ -n "$conda_hook" ]]; then
        source "$conda_hook"
    fi

    # 创建环境
    print_info "创建环境 (Python 3.10)..."
    conda create -n "$CONDA_ENV_NAME" python=3.10 -y

    # 激活环境
    conda activate "$CONDA_ENV_NAME"

    print_success "Conda 环境创建成功: $CONDA_ENV_NAME"
    print_info "下一步: ./start.sh install"
}

# ==================== 依赖管理 ====================

# 检查关键依赖是否已安装
check_deps_installed() {
    python -c "
import sys
required = ['httpx', 'sqlalchemy', 'click', 'rich', 'pydantic', 'aiosqlite']
missing = []
for pkg in required:
    try:
        __import__(pkg)
    except ImportError:
        missing.append(pkg)
if missing:
    print(f'缺失: {missing}')
    sys.exit(1)
print('依赖完整')
" 2>/dev/null
    return $?
}

# 智能安装依赖
smart_install_deps() {
    print_step "检查依赖..."

    if check_deps_installed; then
        print_success "依赖已安装，跳过"
        return 0
    fi

    print_info "检测到缺失依赖，正在安装..."
    cd "$PROJECT_DIR"
    pip install -e . -q
    print_success "依赖安装完成"
}

# 强制重新安装
force_install_deps() {
    print_step "强制重新安装依赖..."
    cd "$PROJECT_DIR"
    pip install -e . --force-reinstall -q
    print_success "依赖重新安装完成"
}

# ==================== 系统操作 ====================

# 初始化系统
init_system() {
    print_step "初始化系统..."

    # 检查环境
    setup_environment || exit 1

    # 安装依赖
    smart_install_deps

    # 检查 .env
    if [[ ! -f "$PROJECT_DIR/.env" ]]; then
        print_warning ".env 文件不存在，正在创建..."
        cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
        print_info "请编辑 $PROJECT_DIR/.env 配置 API Key"
    fi

    # 初始化数据库
    python scripts/run.py init

    print_success "系统初始化完成！"
    echo ""
    print_info "下一步:"
    echo "  1. 编辑 .env 配置 API Key（可选）"
    echo "  2. 运行 ./start.sh login 登录"
    echo "  3. 运行 ./start.sh subscribe <URL> 订阅"
}

# 启动定时抓取服务
start_scheduler() {
    local INTERVAL=${1:-60}

    # 检查是否已运行
    local PID_FILE="$PID_DIR/scheduler.pid"
    if [[ -f "$PID_FILE" ]]; then
        local PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            print_warning "调度器已在运行 (PID: $PID)"
            return
        fi
    fi

    setup_environment || exit 1
    smart_install_deps

    print_info "启动定时抓取服务 (间隔: ${INTERVAL}分钟)..."

    cd "$PROJECT_DIR"
    nohup python scripts/run.py scheduler --interval "$INTERVAL" >> "$LOG_FILE" 2>> "$ERROR_LOG" &
    local PID=$!
    echo $PID > "$PID_FILE"

    print_success "调度器已启动 (PID: $PID)"
    print_info "日志文件: $LOG_FILE"
}

# 停止定时抓取服务
stop_scheduler() {
    local PID_FILE="$PID_DIR/scheduler.pid"

    if [[ ! -f "$PID_FILE" ]]; then
        print_warning "调度器未运行"
        return
    fi

    local PID=$(cat "$PID_FILE")

    if ps -p "$PID" > /dev/null 2>&1; then
        print_info "停止调度器 (PID: $PID)..."
        kill "$PID"
        rm -f "$PID_FILE"
        print_success "调度器已停止"
    else
        print_warning "调度器进程不存在"
        rm -f "$PID_FILE"
    fi
}

# 手动抓取
run_fetch() {
    setup_environment || exit 1
    smart_install_deps

    print_info "开始抓取文章..."
    cd "$PROJECT_DIR"
    python scripts/run.py fetch 2>&1 | tee -a "$LOG_FILE"
}

# 查看状态
show_status() {
    setup_environment || exit 1

    cd "$PROJECT_DIR"
    python scripts/run.py status
}

# 查看日志
show_logs() {
    local LINES=${1:-50}

    if [[ -f "$LOG_FILE" ]]; then
        print_info "最近 $LINES 行日志:"
        tail -n "$LINES" "$LOG_FILE"
    else
        print_warning "日志文件不存在"
    fi
}

# 交互模式
interactive_mode() {
    setup_environment || exit 1
    smart_install_deps

    cd "$PROJECT_DIR"
    python scripts/run.py interactive
}

# CLI 代理
run_cli() {
    setup_environment || exit 1
    smart_install_deps

    cd "$PROJECT_DIR"
    python -m src.cli "$@"
}

# 显示环境信息
show_env_info() {
    echo "环境信息:"
    echo "  项目目录: $PROJECT_DIR"
    echo "  Conda 环境名: $CONDA_ENV_NAME"
    echo "  当前 Conda 环境: ${CONDA_DEFAULT_ENV:-无}"
    echo "  当前 venv: ${VIRTUAL_ENV:-无}"
    echo "  Python: $(which python3 2>/dev/null || echo '未找到')"
    if command -v python &> /dev/null; then
        echo "  Python 版本: $(python --version 2>&1)"
    fi
}

# 帮助信息
show_help() {
    echo "微信公众号文章订阅系统 - 启动脚本"
    echo ""
    echo "用法: $0 <命令> [参数]"
    echo ""
    echo "环境命令:"
    echo "  setup-env           创建 Conda 环境 (wchat_doc)"
    echo "  install             安装/更新依赖"
    echo "  reinstall           强制重新安装依赖"
    echo "  env-info            显示环境信息"
    echo ""
    echo "系统命令:"
    echo "  init                初始化系统"
    echo "  login               登录微信读书"
    echo "  subscribe <url>     订阅公众号"
    echo "  unsubscribe <id>    取消订阅"
    echo "  fetch               手动抓取文章"
    echo "  scheduler [分钟]    启动定时抓取 (默认 60 分钟)"
    echo "  stop                停止定时抓取"
    echo "  status              查看系统状态"
    echo "  logs [行数]         查看日志 (默认 50 行)"
    echo "  interactive         交互模式"
    echo "  help                显示帮助"
    echo ""
    echo "示例:"
    echo "  $0 setup-env        # 创建 conda 环境"
    echo "  $0 init             # 初始化系统"
    echo "  $0 fetch            # 抓取文章"
    echo "  $0 scheduler 30     # 每30分钟抓取一次"
    echo ""
    echo "配置:"
    echo "  Conda 环境名: $CONDA_ENV_NAME"
    echo "  项目目录: $PROJECT_DIR"
}

# ==================== 主入口 ====================

case "${1:-help}" in
    # 环境管理
    setup-env)
        create_conda_env
        ;;
    install)
        setup_environment || exit 1
        smart_install_deps
        ;;
    reinstall)
        setup_environment || exit 1
        force_install_deps
        ;;
    env-info)
        show_env_info
        ;;

    # 系统初始化
    init)
        init_system
        ;;

    # CLI 命令
    login|subscribe|unsubscribe|list|export|info|article|ai|logout)
        run_cli "$@"
        ;;

    # 抓取
    fetch)
        run_fetch
        ;;

    # 调度器
    scheduler)
        start_scheduler "${2:-60}"
        ;;
    stop)
        stop_scheduler
        ;;

    # 状态和日志
    status)
        show_status
        ;;
    logs)
        show_logs "${2:-50}"
        ;;

    # 交互模式
    interactive)
        interactive_mode
        ;;

    # 帮助
    help|--help|-h)
        show_help
        ;;

    *)
        print_error "未知命令: $1"
        echo ""
        show_help
        exit 1
        ;;
esac
