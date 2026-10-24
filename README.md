# 塔防山贼模拟器 · H5 线上化部署包

把《塔防山贼模拟器》跑在浏览器里（手机 / 平板 / 电脑都能玩），并附带可在线改档的修改器。

> ⚠️ **本仓库只包含"部署代码与教程"，不包含游戏本体资源**（图片、音频、脚本、data.json 等）。
> 游戏文件请自备：从你自己的游戏安装目录得到 `package.nw`（NW.js 包，本质是 zip），
> 解开后按下方步骤放到同一目录即可。

## 特性

| 功能 | 说明 |
|---|---|
| 浏览器直接玩 | 把 NW.js 导出改成 html5 导出，纯静态资源 + 一个 Python 服务 |
| 存档在浏览器 | 使用 IndexedDB（同源），**不写服务器磁盘**，多人用互不干扰 |
| 在线修改器 | `editor.html`：改武将在浏览器里完成，同一站点下与游戏共享存档 |
| 触摸适配 | 触摸事件额外翻译成鼠标事件，修复"某些界面点不动""拖拽落点偏移" |
| 手势 | 双指捏合 = 滚轮缩放；长按 2 秒 = 鼠标右键 |
| 作弊面板 | 游戏右下角玻璃按钮 = `Ctrl+0`（需游戏侧 MOD 支持） |
| HTTPS | 自带自签证书脚本，满足 File System Access 等安全上下文要求 |
| 调试端点 | `?debug=1` 页面内调试台 + `POST /__debug` 落盘日志 |

## 文档

| 文档 | 内容 |
|---|---|
| [部署说明.md](部署说明.md) | **Linux 本地部署**全流程：解压（中文名坑）、HTTP/HTTPS、systemd、防火墙、存档位置、FAQ |
| [桌面版修改器使用说明.md](桌面版修改器使用说明.md) | 桌面版存档修改器：设置游戏位置、改档、备份还原、武将工坊、线上档互转、注意事项 |
| [安装MOD教程.md](安装MOD教程.md) | 凡人MOD / 自建武将包的安装、游戏内使用（`Ctrl+0`）、卸载、杀软与 Steam 校验的坑 |

## 目录结构

```
.
├── server.py                     # 单文件 HTTP/HTTPS 服务器（仅标准库，无第三方依赖）
├── start.sh                      # 启动脚本（HTTP）
├── make_cert.sh                  # 生成自签 HTTPS 证书
├── 部署说明.md                    # Linux 本地部署步骤（推荐先看）
├── 桌面版修改器使用说明.md        # 修改器怎么用
├── 安装MOD教程.md                 # MOD 安装 / 使用 / 卸载
└── README.md
```

## 快速开始（Linux 本地，3 步）

```bash
# 1) 准备游戏文件（自备 package.nw），解压到本目录
#    ★ 必须用 python3 解压，否则中文资源名会乱码 → 游戏白屏
python3 -c "import zipfile;zipfile.ZipFile('package.nw').extractall('.')"

# 2) 放好修改器（如果你有 editor.html）
cp /path/to/editor.html .

# 3) 启动
chmod +x start.sh make_cert.sh
python3 server.py 8123            # 仅 HTTP
./make_cert.sh 192.168.1.10       # 生成自签证书（换成你的 IP）
python3 server.py 8123 8443       # HTTP + HTTPS
```

访问：

| 入口 | 地址 |
|---|---|
| 修改器（推荐） | `https://<你的IP>:8443/editor.html` |
| 游戏本体 | `https://<你的IP>:8443/index.html` |
| 纯 HTTP 备用 | `http://<你的IP>:8123/editor.html` |
| 健康检查 | `/__alive` → `ok` |

> 自签证书首次访问会提示风险，点「高级 → 继续前往」。
> **远程/手机务必用 HTTPS**：`http://192.168.x.x` 不是安全上下文，修改器的目录选择等功能会被浏览器拒绝。

## 部署到常驻服务（systemd）

```bash
mkdir -p ~/.config/systemd/user
cat > ~/.config/systemd/user/tfsz-h5.service <<'EOF'
[Unit]
Description=TFSZ H5
After=network.target

[Service]
WorkingDirectory=%h/tfsz-h5
ExecStart=/usr/bin/python3 %h/tfsz-h5/server.py 8123 8443
Restart=always

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now tfsz-h5
loginctl enable-linger $USER      # 不登录也随开机启动
```

常用：

```bash
systemctl --user status tfsz-h5
systemctl --user restart tfsz-h5
journalctl --user -u tfsz-h5 -f
```

## 服务器端点

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/` | 返回 `editor.html`（没有则 `index.html`） |
| GET | `/portraits/<名字>.png` | 修改器立绘（缺失回退 `43.png`） |
| GET | `/__alive` | 健康检查 |
| GET | `/__saveinfo` | 存档元数据模板（游戏"载入存档"列表用） |
| POST | `/__debug` | 调试台日志/截图落盘到 `debug/` 目录 |

## 常见坑（真的会踩）

1. **不要用 `unzip` 解包**：Linux 的 unzip 按 CP437 解码中文名，`images/中文名-sheet0.webp` 会变成乱码 → 游戏资源 404、卡住。
   用 `python3 -c "import zipfile;..."` 或 `unzip -O UTF-8`。
2. **别用 `python -m http.server` 代替 `server.py`**：它是 HTTP/1.0，没有长连接、没有立绘路由，会黑屏/资源加载极慢。
3. **404 会被浏览器缓存**：本项目对错误响应强制 `Cache-Control: no-store`，避免缓存住 404。若你改过服务端，记得强刷（Ctrl+Shift+R）。
4. **存档按"站点"隔离**：`http://IP:8123` 与 `https://IP:8443` 是两个不同源，**存档互不相通**；`localhost` 与 `IP` 也不通。请在同一个地址下玩与改。
5. **存档不随服务器迁移**：存档在玩家浏览器里（IndexedDB），换浏览器/清缓存/无痕模式都会丢。请自行导出备份。

## 存档互通（手机 ↔ 电脑）

修改器提供：

- **导出线上1档** → 下载 `ea1save.dat`（游戏原生存档格式，可直接放进桌面版 `save/` 目录）
- **导入线上1档** → 选择 `.dat` 写回浏览器 1 号档（含元数据，游戏「载入存档 → 档位1」即可用）

> 导入后如游戏已开着，需要重新进「载入存档」；页面会自动刷新游戏 iframe。

## 许可

仅供个人学习与自用，请勿分发游戏本体资源。游戏版权归原作者所有。
