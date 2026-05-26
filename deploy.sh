#!/bin/bash
# ============================================
# Smart CS Agent — 一键部署脚本
# 用法：bash deploy.sh [start|stop|restart|logs|status|build]
# 兼容：docker compose (推荐) / docker-compose (旧版)
# ============================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# 自动检测 compose 命令（新版是 docker compose，旧版是 docker-compose）
if docker compose version &>/dev/null 2>&1; then
    COMPOSE="docker compose"
elif docker-compose version &>/dev/null 2>&1; then
    COMPOSE="docker-compose"
else
    echo "[✗] 未找到 docker compose，请先安装 Docker"
    exit 1
fi

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
err()  { echo -e "${RED}[✗]${NC} $1"; exit 1; }
info() { echo -e "${CYAN}[→]${NC} $1"; }

check_env() {
    if [ ! -f .env.prod ]; then
        err "缺少 .env.prod 文件，请先配置生产环境变量"
    fi

    source .env.prod 2>/dev/null || true
    if [ "$DEEPSEEK_API_KEY" = "your-deepseek-key-here" ] || [ -z "$DEEPSEEK_API_KEY" ]; then
        warn "DEEPSEEK_API_KEY 未配置，请在 .env.prod 中填写"
    fi
    if [ "$API_KEY" = "change-me-in-production" ] || [ -z "$API_KEY" ]; then
        warn "API_KEY 未更改，请在 .env.prod 中设置生产密钥"
    fi
}

build() {
    info "构建 Docker 镜像..."
    $COMPOSE build --no-cache cs-agent
    log "镜像构建完成"
}

start() {
    check_env
    info "启动所有服务..."
    $COMPOSE up -d
    log "服务已启动"

    info "等待健康检查..."
    sleep 5
    for i in {1..12}; do
        if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
            log "CS Agent 健康检查通过 ✓"
            echo ""
            echo -e "${GREEN}══════════════════════════════════════${NC}"
            echo -e "${GREEN}  Smart CS Agent 部署成功！${NC}"
            echo -e "${GREEN}══════════════════════════════════════${NC}"
            echo ""
            echo "  端口:  http://localhost:8000"
            echo "  文档:  http://localhost:8000/docs"
            echo "  健康:  http://localhost:8000/health"
            echo ""
            echo "  测试命令:"
            echo "    curl -X POST http://localhost:8000/chat \\"
            echo "      -H 'X-API-Key: <你的API_KEY>' \\"
            echo "      -H 'Content-Type: application/json' \\"
            echo "      -d '{\"message\":\"退货需要几天到账？\",\"user_id\":\"test\"}'"
            echo ""
            return
        fi
        sleep 5
    done
    warn "健康检查超时，请查看日志: $COMPOSE logs cs-agent"
}

stop() {
    info "停止所有服务..."
    $COMPOSE down
    log "服务已停止"
}

restart() {
    info "重启所有服务..."
    $COMPOSE down
    $COMPOSE up -d
    log "服务已重启"
}

status() {
    echo ""
    echo -e "${CYAN}═══ 容器状态 ═══${NC}"
    $COMPOSE ps
    echo ""
    echo -e "${CYAN}═══ 资源占用 ═══${NC}"
    docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
        $($COMPOSE ps -q) 2>/dev/null || true
}

logs() {
    $COMPOSE logs -f --tail=100 "${1:-cs-agent}"
}

case "${1:-start}" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    build)   build ;;
    status)  status ;;
    logs)    logs "$2" ;;
    *)
        echo "用法: bash deploy.sh [start|stop|restart|logs|status|build]"
        echo ""
        echo "  start   启动所有服务（默认）"
        echo "  stop    停止所有服务"
        echo "  restart 重启所有服务"
        echo "  logs    查看 cs-agent 日志（加容器名查看特定服务）"
        echo "  status  查看容器状态和资源占用"
        echo "  build   重新构建镜像"
        exit 1
        ;;
esac
