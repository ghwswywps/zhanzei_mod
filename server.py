#!/usr/bin/env python3
"""塔防山贼模拟器 · 线上版服务器（纯标准库，Python 3.7+）

用法：
    python3 server.py 8123              # 只开 HTTP
    python3 server.py 8123 8443         # HTTP + HTTPS（需要 cert.pem / key.pem）
    python3 server.py --tls-only 8443   # 只开 HTTPS

路由：
    /                → 修改器（editor.html）
    /editor.html     → 修改器
    /index.html      → 游戏
    /portraits/*.png → 立绘（缺失自动回落 43.png）
    /__alive         → 健康检查
"""
import http.server
import os
import re
import base64
import time
import json
import socketserver
import ssl
import sys
import threading
import urllib.parse

ROOT = os.path.dirname(os.path.abspath(__file__))
CERT = os.path.join(ROOT, 'cert.pem')
KEY = os.path.join(ROOT, 'key.pem')

MIME = {
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.mjs': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.wasm': 'application/wasm',
    '.webp': 'image/webp',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.svg': 'image/svg+xml',
    '.webm': 'audio/webm',
    '.mp3': 'audio/mpeg',
    '.ogg': 'audio/ogg',
    '.ttf': 'font/ttf',
    '.otf': 'font/otf',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
}
CACHE_OK = {'.webp', '.png', '.jpg', '.jpeg', '.webm', '.mp3', '.ogg',
            '.ttf', '.otf', '.woff', '.woff2', '.wasm'}


class Handler(http.server.SimpleHTTPRequestHandler):
    def setup(self):
        super().setup()
        try:
            self.connection.settimeout(60)
        except Exception:
            pass

    protocol_version = 'HTTP/1.1'          # 长连接：首屏几十个资源才不会被 6 并发卡死

    def __init__(self, *a, **kw):
        super().__init__(*a, directory=ROOT, **kw)

    def log_message(self, fmt, *args):
        pass

    def guess_type(self, path):
        ext = os.path.splitext(path)[1].lower()
        return MIME.get(ext) or super().guess_type(path)

    def send_error(self, code, message=None, explain=None):
        self._no_cache = True
        super().send_error(code, message, explain)

    def end_headers(self):
        # 注意：BaseHTTPRequestHandler 在 parse_request 失败时也会走 end_headers，
        # 那时 self.path 还不存在；早期版本直接取 self.path 会抛 AttributeError，
        # 把错误响应写坏（客户端表现为超时/连接被重置）。
        path = getattr(self, 'path', '') or ''
        ext = os.path.splitext(urllib.parse.urlparse(path).path)[1].lower()
        cc = 'no-store' if (getattr(self, '_no_cache', False) or ext not in CACHE_OK) \
            else 'public, max-age=86400'
        self.send_header('Cache-Control', cc)
        super().end_headers()

    def do_HEAD(self):
        p = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if p == '/__saveinfo':
            # 返回打包内的真实 saveinfo.dat（元数据模板），没有就现造一份合成式的
            tpl = os.path.join(ROOT, 'saveinfo.dat')
            if os.path.exists(tpl):
                with open(tpl, 'rb') as f:
                    body = f.read()
            else:
                body = json.dumps({
                    'c2array': True, 'size': [6, 26, 1],
                    'data': [[['正式版']] + [[0]] * 25] + [[[0]] * 26 for _ in range(5)]
                }, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p == '/__alive':
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            return
        return super().do_HEAD()

# __H5_DEBUG_ENDPOINT__
    def do_POST(self):
        p = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)
        if p != '/__debug':
            self.send_error(404, 'not found')
            return
        try:
            n = int(self.headers.get('Content-Length') or 0)
            raw = self.rfile.read(n) if n else b''
            dbg = os.path.join(ROOT, 'debug')
            os.makedirs(dbg, exist_ok=True)
            ts = time.strftime('%Y%m%d_%H%M%S')
            ctype = (self.headers.get('Content-Type') or '').lower()
            saved = []
            if 'application/json' in ctype:
                data = json.loads(raw.decode('utf-8', 'replace'))
                tag = re.sub(r'[^\w\u4e00-\u9fa5-]+', '_', str(data.get('tag') or 'dump'))[:40]
                img = data.pop('png', None)
                fn = os.path.join(dbg, '%s_%s.json' % (ts, tag))
                with open(fn, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=1)
                saved.append(os.path.basename(fn))
                if isinstance(img, str) and img.startswith('data:image'):
                    b64 = img.split(',', 1)[1]
                    png = os.path.join(dbg, '%s_%s.png' % (ts, tag))
                    with open(png, 'wb') as f:
                        f.write(base64.b64decode(b64))
                    saved.append(os.path.basename(png))
            else:
                fn = os.path.join(dbg, '%s_raw.bin' % ts)
                with open(fn, 'wb') as f:
                    f.write(raw)
                saved.append(os.path.basename(fn))
            out = json.dumps({'ok': True, 'saved': saved}).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(out)))
            self.end_headers()
            self.wfile.write(out)
        except Exception as e:
            msg = ('err: %s' % e).encode()
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(msg)))
            self.end_headers()
            self.wfile.write(msg)

    def do_GET(self):
        p = urllib.parse.unquote(urllib.parse.urlparse(self.path).path)

        if p == '/__saveinfo':
            tpl = os.path.join(ROOT, 'saveinfo.dat')
            if os.path.exists(tpl):
                with open(tpl, 'rb') as f:
                    body = f.read()
            else:
                body = json.dumps({
                    'c2array': True, 'size': [6, 26, 1],
                    'data': [[['正式版']] + [[0]] * 25] + [[[0]] * 26 for _ in range(5)]
                }, ensure_ascii=False).encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if p == '/__alive':
            body = b'ok'
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if p in ('/', '/editor', '/editor.html'):
            return self._file(os.path.join(ROOT, 'editor.html'), 'text/html; charset=utf-8')

        if p.startswith('/portraits/'):
            name = os.path.basename(p)
            for c in (os.path.join(ROOT, 'portraits', name),
                      os.path.join(ROOT, 'portraits', '43.png')):
                if os.path.exists(c):
                    return self._file(c, self.guess_type(c))
            return self.send_error(404, 'portrait not found')

        return super().do_GET()

    def _file(self, path, ctype):
        if not os.path.exists(path):
            return self.send_error(404, 'not found')
        with open(path, 'rb') as fh:
            data = fh.read()
        self.send_response(200)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)


class Server(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True
    request_queue_size = 128


class TLSServer(Server):
    """HTTPS 专用。

    旧实现是 ctx.wrap_socket(监听socket)：只要有客户端在握手阶段卡住（不发
    ClientHello 或半开连接），accept 循环就永久阻塞，端口还在 listen 但再也没人
    接受连接 —— 现象就是 Recv-Q 越堆越多、浏览器一直转圈。
    这里改成每个连接单独握手，并给底层 socket 设超时。
    """
    tls_ctx = None

    def get_request(self):
        sock, addr = self.socket.accept()
        try:
            sock.settimeout(15)
            return self.tls_ctx.wrap_socket(sock, server_side=True), addr
        except Exception:
            try:
                sock.close()
            except Exception:
                pass
            # OSError 子类会被 socketserver 静默跳过，不会打断 accept 循环
            raise OSError('tls handshake failed')


def serve(port, tls=False):
    bind = os.environ.get('H5_BIND', '0.0.0.0')
    if tls:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(CERT, KEY)
        TLSServer.tls_ctx = ctx
        srv = TLSServer((bind, port), Handler)
    else:
        srv = Server((bind, port), Handler)
    scheme = 'https' if tls else 'http'
    print(' %-5s : %s://<本机IP>:%d/editor.html' % (scheme.upper(), scheme, port))
    srv.serve_forever()


def main():
    args = [a for a in sys.argv[1:]]
    tls_only = False
    if '--tls-only' in args:
        tls_only = True
        args.remove('--tls-only')
    ports = [int(a) for a in args if a.isdigit()]
    http_port = None if tls_only else (ports[0] if ports else 8123)
    https_port = (ports[1] if len(ports) > 1 else
                  (ports[0] if tls_only and ports else None))

    print('=' * 58)
    print(' 塔防山贼模拟器 · 线上版')
    print('=' * 58)
    if https_port:
        if not (os.path.exists(CERT) and os.path.exists(KEY)):
            print(' ! 找不到 cert.pem / key.pem，HTTPS 无法启动')
            print('   先运行：./make_cert.sh 192.168.50.146')
            https_port = None
    if http_port:
        print(' HTTP  : http://<本机IP>:%d/editor.html' % http_port)
    if https_port:
        print(' HTTPS : https://<本机IP>:%d/editor.html' % https_port)
        print('         （自签证书，浏览器首次会提示风险，点「继续访问」）')
    print(' 目录  : %s' % ROOT)
    print(' Ctrl+C 停止')
    print('=' * 58)

    if https_port:
        threading.Thread(target=serve, args=(https_port, True), daemon=True).start()
    if http_port:
        serve(http_port, False)
    else:
        while True:
            threading.Event().wait(3600)


if __name__ == '__main__':
    main()
