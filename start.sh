#!/usr/bin/env bash
# 塔防山贼模拟器 · 线上版启动脚本
set -e
cd "$(dirname "$0")"

PORT="${1:-8123}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "[错误] 未找到 python3，请先安装：sudo apt install -y python3"
  exit 1
fi

echo "启动中… 端口 ${PORT}"
echo "修改器：http://<本机IP>:${PORT}/editor.html"
echo "（云服务器记得在安全组/防火墙放行 ${PORT} 端口）"
echo
exec python3 server.py "${PORT}"
