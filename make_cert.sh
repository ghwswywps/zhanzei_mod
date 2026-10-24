#!/usr/bin/env bash
# 生成自签 HTTPS 证书（含 IP/域名 SAN）
#   用法: ./make_cert.sh 192.168.50.146 [可选域名]
set -e
cd "$(dirname "$0")"

IP="${1:-127.0.0.1}"
DOMAIN="${2:-}"

if ! command -v openssl >/dev/null 2>&1; then
  echo "[错误] 没装 openssl：sudo apt install -y openssl"
  exit 1
fi

SAN="IP:${IP},IP:127.0.0.1,DNS:localhost"
[ -n "$DOMAIN" ] && SAN="${SAN},DNS:${DOMAIN}"

openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout key.pem -out cert.pem -days 825 \
  -subj "/CN=${IP}" \
  -addext "subjectAltName=${SAN}" >/dev/null 2>&1

chmod 600 key.pem
echo "已生成 cert.pem / key.pem（CN=${IP}，SAN=${SAN}，825 天）"
echo "启动： python3 server.py 8123 8443"
