# MyVideoPic

后续使用 AI 维护项目时，修改代码前请先阅读 [AI_HANDOFF.md](AI_HANDOFF.md)。

## 开发结构

项目保持一个 Django 应用和一个 Vue 应用。以下文件是后续维护的主要入口，不会改变本文所述的本地、离线运行约束。

- `backend/videos/scanner.py` 协调同一时刻唯一的扫描任务。扫描进行时新选择的媒体库会进入后续扫描队列。
- `backend/videos/scanning/` 放置只读扫描辅助函数：`detect.py`、`extract.py` 和 `thumbnail.py`。缩略图仍使用 UUID 命名并写入 `backend/.app_data/`。
- 首次导入大量图片时，图片读取、EXIF 解析和缩略图编码最多使用两个工作线程并行执行；SQLite 编目写入保持单线程，避免数据库锁与高内存占用。
- `backend/videos/services.py` 放置与 Django 请求处理无关、可复用的媒体库识别逻辑。
- `frontend/src/api/` 按 `client.js`、`media.js`、`libraries.js`、`tasks.js` 与 `settings.js` 分层；`api.js` 保留为兼容既有导入的统一入口。
- `frontend/src/styles/variables.css` 为新组件提供语义设计变量，现有 `mv-` 设计系统仍保留在 `style.css`。

纯本地极简媒体中心。把硬盘上散落的视频和图片编目成一个能刷、能搜、能整理的库。

* **完全离线** —— 不请求任何外部接口，不上传任何数据，断网照常使用
* **零侵入** —— 只读访问你的媒体文件夹，绝不在里面写入任何文件
* **纯手动** —— 没有后台定时扫描，什么时候更新完全由你决定
* **真实文件操作** —— 重命名 / 移动 / 删除作用于磁盘上的真实文件

---

## 目录

- [环境要求](#环境要求)
- [启动](#启动)
- [首次使用](#首次使用)
- [功能说明](#功能说明)
- [键盘快捷键](#键盘快捷键)
- [项目结构](#项目结构)
- [设计约束与实现](#设计约束与实现)
- [Nginx（可选）](#nginx可选)
- [环境变量](#环境变量)
- [API 一览](#api-一览)
- [常见问题](#常见问题)

---

## 环境要求

| 组件 | 版本 | 必需 | 说明 |
|------|------|------|------|
| Python | 3.11+ | 是 | 后端 |
| Node.js | 20+ | 是 | 前端构建 |
| ffmpeg / ffprobe | 任意近期版本 | 否 | 缺少时视频仍可入库，但没有封面、时长、分辨率与编码信息 |
| Nginx | 任意 | 否 | 仅用于大文件零拷贝，见下文 |

ffmpeg 需要能在命令行直接调用（即所在目录已加入 `PATH`）。验证：

```bash
ffmpeg -version
ffprobe -version
```

---

## 启动

需要两个终端，前后端各一个。

### 后端

```bash
cd backend

python -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS / Linux

pip install -r requirements.txt
python manage.py migrate         # 建表，迁移文件已随仓库提供
python manage.py runserver 127.0.0.1:8000
```

`migrate` 会在 `backend/` 下生成 `db.sqlite3` 与 `.app_data/`（缩略图缓存）。
不需要执行 `makemigrations`，也不需要创建超级用户 —— 应用本身没有登录。

### 前端

```bash
cd frontend

npm install
npm run dev
```

打开 <http://127.0.0.1:5173>。

Vite 已把 `/api` 代理到 `127.0.0.1:8000`，因此前端代码里不含任何主机名，
也不需要任何跨域配置。后端端口不同时用环境变量覆盖：

```bash
set MYVIDEOPIC_API=http://127.0.0.1:9000    # Windows
```

### 打包部署

```bash
cd frontend
npm run build          # 产物在 frontend/dist
```

之后让 Nginx 直接托管 `dist`，并把 `/api` 反代到 Django（配置见 `nginx/media.conf`）。

不想装 Nginx 的话，`npm run preview`（<http://127.0.0.1:4173>）同样能跑，
`/api` 已配好代理，只是视频吞吐不如 Nginx。

---

## 首次使用

1. 打开右上角 **设置 → 媒体库管理 → 选择媒体文件夹**
2. 在弹出的 Windows 系统文件夹选择器中选中目标文件夹
3. 应用会只读检查文件夹及其子文件夹，自动识别视频和图片并建立对应媒体库
4. 文件夹同时包含视频和图片时，会自动建立同路径的「视频」和「图片」两个媒体库
5. 选择完成即自动扫描刚加入的媒体库；不会扫描其它库，也不会启动定时扫描

已有媒体库可通过编辑按钮调整名称、分类和路径。分类可留空；填了就会成为列表页顶部的
筛选胶囊，例如「电影」「剧集」。

扫描是增量的：只有体积或修改时间变化的文件会被重新处理，之后再扫会很快。
面板会实时显示阶段、百分比、当前文件、四类计数与预计剩余时间，可随时取消。

---

## 功能说明

### 浏览

视频页与图片页共用一套筛选：分类胶囊、媒体库下拉、排序下拉、仅收藏开关。
筛选、排序与分页均由后端完成。视频和图片主界面每页显示 24 项，底部提供页码、上一页和下一页；
封面按当前页懒加载，上千条媒体也不会一次性打满浏览器连接池。

### 文件操作

鼠标移到卡片上，点右下角 ⋮：

| 操作 | 行为 |
|------|------|
| 重命名 | 只改主名，扩展名由后端保留。封面按数据库 UUID 命名，因此不会丢 |
| 移动到… | 目标是另一个同类型媒体库。同盘瞬间完成；跨盘转为后台分块复制并显示进度与预计剩余时间，源文件在目标写入成功后才删除 |
| 复制文件路径 | 复制绝对路径，便于粘到别的程序里 |
| 永久删除 | 直接从磁盘删除，**不进回收站**，需二次确认 |

文件被播放器等程序占用时（Windows 常见的 WinError 32），会明确提示
「文件正被其他程序占用，请关闭播放器后重试」，而不是抛一段栈。

### 播放

视频走 `/api/stream/video/<uuid>/`，支持 HTTP 206 分段传输，拖进度条即时响应。
URL 里只有 UUID，磁盘路径不会出现在地址栏或网络面板里。

播放进度每 5 秒上报一次，离开页面再补一次，下次打开自动续播（看完的会归零，
不会一进去就跳到片尾）。

播放页会按当前 Edge/Chrome 的 `canPlayType()` 复核封装和音视频编码。MKV 中的
H.264/H.265（HEVC）会在支持该组合的浏览器中直接播放；是否可用仍由当前浏览器、
Windows HEVC 扩展和硬件能力决定。即使能力检测通过，具体文件加载失败时页面也会立即
切换为外部播放提示。

无法内嵌播放时卡片上会有「需外部播放」角标，播放页会显示「用系统默认播放器打开」。
能内嵌播放的视频也保留此按钮和「复制文件路径」操作。点击默认播放器按钮后，后端会通过
Windows 文件关联打开该视频类型的默认应用；把 MPC-BE 设为对应视频类型的默认应用即可。

播放列表右上角显示「当前序号/总数」，例如 `2/18`。播放页左上角的「返回」会直接进入当前视频所属媒体库、沿用当前排序并定位到该视频所在的分页，不依赖浏览器历史。

### 图片

点开进入全屏查看器，`←` / `→` 在当前列表内翻页，`Esc` 退出。查看器取原图而非
缩略图。带 EXIF 方向信息的照片在生成缩略图时已做旋转校正，不会横躺着显示。

### 收藏与历史

卡片右上角星标即收藏，收藏夹页按视频 / 图片分两个标签页。

顶栏时钟图标打开历史抽屉，分「观看记录」（带进度条）与「浏览记录」两个标签页，
可删单条或整类清空。历史只是本地记录，删记录不会碰任何文件。

### 搜索

顶栏放大镜或 `Ctrl+K` 唤起，跨视频与图片模糊匹配名称和原始文件名。
`↑` `↓` 选中、`Enter` 打开，全程不用碰鼠标。

### 维护

**设置 → 存储与维护** 里有两个操作，都只影响缓存与编目，不动原始文件：

* **清空缩略图缓存** —— 删掉 `.app_data/` 里的封面，下次扫描重新生成
* **清理失效记录** —— 移除物理文件已不存在的编目项。
  **移动硬盘未连接时不要执行**，否则会误清离线盘上的记录

---

## 键盘快捷键

| 场景 | 按键 | 作用 |
|------|------|------|
| 全局 | `Ctrl` + `K` | 打开搜索 |
| 播放页 | `空格` | 播放 / 暂停 |
| 播放页 | `←` `→` | 快退 / 快进（步长在设置里改，默认 10 秒）|
| 看图 | `←` `→` | 上一张 / 下一张 |
| 看图 | `空格` | 下一张 |
| 浮层 | `Esc` | 关闭 |

---

## 项目结构

```
MyVideoPic/
├── backend/
│   ├── config/              # Django 配置与根路由
│   ├── videos/
│   │   ├── models.py        # 7 张表，UUID 主键
│   │   ├── serializers.py   # 序列化，分页后批量注入收藏与进度
│   │   ├── views.py         # 全部接口
│   │   ├── urls.py          # /api/ 路由表
│   │   ├── scanner.py       # 手动扫描引擎（后台线程）
│   │   ├── file_ops.py      # 重命名 / 移动 / 删除
│   │   ├── streaming.py     # 206 Range + X-Accel-Redirect
│   │   ├── image_utils.py   # Pillow 缩略图与 EXIF
│   │   ├── pagination.py
│   │   └── migrations/      # 已随仓库提供
│   ├── requirements.txt
│   ├── db.sqlite3           # 首次 migrate 后生成
│   └── .app_data/           # 缩略图缓存，同上
├── frontend/
│   └── src/
│       ├── api/api.js       # 全部请求集中在此
│       ├── components/      # 卡片、网格、菜单、对话框、抽屉、查看器…
│       ├── composables/     # IntersectionObserver 封装
│       ├── stores/          # Pinia：媒体 / 库 / 设置 / 扫描 / 操作 / UI
│       ├── views/           # 视频 / 图片 / 收藏夹 / 播放 / 设置
│       ├── style.css        # 手写设计系统（mv- 前缀）
│       └── utils.js         # URL 构造与格式化
└── nginx/media.conf         # 可选
```

后端依赖只有 3 个（Django、DRF、Pillow），前端运行时依赖只有 4 个
（vue、vue-router、pinia、axios）。样式是手写 CSS，没有构建期 CSS 框架。

---

## 设计约束与实现

四条项目约束，以及代码里对应的落地方式：

**绝对隐私与离线** —— 没有任何 `http://` 外部请求，没有 CDN、字体、分析脚本。
Django 只监听 `127.0.0.1`，`ALLOWED_HOSTS` 不含局域网地址。
不使用 `django-cors-headers`：开发期 Vite 代理、部署期 Nginx 反代，两种情况下
前端都是同源请求。

**零侵入性** —— 扫描只 `os.walk` + `os.stat` + 读文件头，从不在媒体文件夹里写入
任何东西。唯一会改动原文件的是你主动触发的重命名 / 移动 / 删除。

**缓存策略** —— 缩略图统一写入 `backend/.app_data/`，文件名是 `<数据库UUID>_thumb.jpg`。
用 UUID 而不是文件路径哈希，所以重命名或移动文件之后封面依然对得上。

**纯手动控制** —— 代码里没有任何定时器、`APScheduler`、Celery beat。扫描只能由
你点击「开始扫描」或明确选择一个新媒体文件夹时触发，同一时刻只允许一个扫描任务。

另外两处值得一提的取舍：

* **离线磁盘保护** —— 扫描时若某个库的目录读不到（移动硬盘没插、网络盘断开），
  该库整体跳过并在结果里提示，**绝不**按「数据库里有但这次没扫到 = 已删除」
  去清理。否则插拔一次硬盘就会清空整个库的编目和封面。
* **分页与查询** —— 列表接口先分页，再针对当前页的 id 批量查收藏与播放进度，
  避免每行各查一次。

---

## Nginx（可选）

不装 Nginx 也能正常用：Django 自己实现了 206 Range，拖进度条没问题。
上 Nginx 只为把大文件的字节搬运交给内核 `sendfile`，播 4K / 原盘时 Python
进程不会被占满。

`nginx/media.conf` 用的是 `X-Accel-Redirect` 方案：请求先经过 Django 校验 UUID，
命中后返回一个 `internal` 位置的内部重定向，Nginx 再取文件回传。配置会自动映射本机
所有盘符，但磁盘目录不会被直接暴露：`internal` 会拒绝来自浏览器的直接请求，只有 Django
为已入库 UUID 生成的内部重定向才能读取文件。

Windows 上的最短启用步骤：

1. 执行 `npm run build`，得到 `frontend/dist`。如需访问 Django Admin，再执行
   `python manage.py collectstatic`。
2. 打开 `nginx/media.conf`，只把 `myvideopic_root` 的值改成项目的绝对路径，使用正斜杠，
   例如 `C:/Apps/MyVideoPic`。
3. 在 Nginx 安装目录的 `conf/nginx.conf` 的 `http {}` 内加入：
   `include C:/Apps/MyVideoPic/nginx/media.conf;`
4. 以 `MYVIDEOPIC_X_ACCEL=1` 启动 Django，再执行 `nginx -t` 检查配置并启动 Nginx。
5. 打开 `http://127.0.0.1/`。示例配置只监听 `127.0.0.1:80`，不会对局域网开放。

如 80 端口已被占用，只需同时把配置中的 `listen 127.0.0.1:80` 和访问地址改成空闲端口。

Nginx 版本只适用于盘符形式的本地路径（如 `D:\\Movies`）。媒体库在 UNC 网络共享路径时，
保留 `MYVIDEOPIC_X_ACCEL=0`，由 Django 的 Range 流直接提供视频即可。

---

## 环境变量

全部可选，不设即用默认值。

| 变量 | 默认 | 作用 |
|------|------|------|
| `MYVIDEOPIC_DEBUG` | `1` | 设 `0` 进生产模式 |
| `MYVIDEOPIC_SECRET_KEY` | 内置值 | 本地应用不参与对外通信，可不改 |
| `MYVIDEOPIC_APP_DATA` | `backend/.app_data` | 缩略图缓存目录，可指向别的盘 |
| `MYVIDEOPIC_X_ACCEL` | `0` | 设 `1` 启用 Nginx 零拷贝 |
| `MYVIDEOPIC_API` | `http://127.0.0.1:8000` | 前端开发代理目标（Vite 读取）|

---

## API 一览

全部挂在 `/api/` 下，无鉴权（单用户本地应用）。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/videos/` `/photos/` | 列表，支持 `library` `category` `favorited` `q` `ordering` `page` `page_size` |
| GET | `/videos/<id>/` | 视频详情（含磁盘存在性检查）|
| POST | `/videos/<id>/rename/` `/photos/<id>/rename/` | 重命名 |
| POST | `/videos/<id>/move/` `/photos/<id>/move/` | 移动，跨盘返回 `202` + `task_id` |
| DELETE | `/videos/<id>/delete/` `/photos/<id>/delete/` | 永久删除 |
| POST | `/videos/<id>/progress/` | 上报播放进度 |
| POST | `/videos/<id>/open/` | 交给 Windows 默认播放器打开文件 |
| GET | `/thumbnails/video/<id>/` `/thumbnails/photo/<id>/` | 封面 |
| GET | `/stream/video/<id>/` | 视频流（206 Range）|
| GET | `/original/photo/<id>/` | 原图 |
| GET POST PATCH DELETE | `/libraries/` `/libraries/<id>/` | 媒体库增删改查 |
| POST | `/libraries/pick-and-scan/` | 打开 Windows 原生选目录、自动分类并扫描所选目录 |
| POST | `/scan/` | 触发扫描，返回 `task_id` |
| GET | `/scan/status/` | 当前任务 + 上次扫描记录 |
| GET | `/scan-progress/<task_id>/` | 扫描进度 |
| POST | `/scan-cancel/<task_id>/` | 取消扫描 |
| GET | `/move-progress/<task_id>/` | 跨盘移动进度 |
| GET POST | `/favorites/` `/favorites/toggle/` | 收藏 |
| GET POST | `/history/` `/history/record/` | 历史列表 / 记录一条 |
| DELETE | `/history/<id>/` `/history/clear/` | 删单条 / 按类清空 |
| GET | `/search/?q=&scope=` | 搜索 |
| GET | `/stats/` | 统计 |
| GET PUT PATCH | `/settings/` | 应用偏好 |
| POST | `/maintenance/clear-cache/` `/maintenance/cleanup-orphans/` | 维护 |
| GET | `/browse/?path=` | 列目录（选文件夹用）|

---

## 常见问题

**视频没有封面，时长和分辨率也是空的**
没装 ffmpeg，或它不在 `PATH` 里。装好后重新扫描即可补齐。
设置 → 存储与维护 顶部会直接提示是否检测到 ffmpeg。

**视频能列出但点开播不了**
看卡片上有没有「需外部播放」角标。有的话是当前浏览器能力检查未通过（常见于 RMVB、
AVI 老编码、DTS / TrueHD 音轨等），用播放页的「用系统默认播放器打开」或复制路径打开。
HEVC 能否内嵌播放取决于浏览器版本、Windows HEVC 扩展和硬件能力，页面会动态判断。
若希望由 MPC-BE 打开，请先在 Windows 的默认应用中将对应视频类型关联到 MPC-BE。
没有角标却播不了，检查文件是否还在原处。

**拖进度条没反应 / 整个页面卡住**
中间有代理层开了响应缓冲。用 Nginx 时确认 `/api/` 下有 `proxy_buffering off`。

**重命名失败，提示文件被占用**
Windows 会锁住正在播放的文件。关掉播放器（包括本应用的播放页）再试。

**插拔移动硬盘后编目会不会被清空**
不会。扫描时读不到的库会整体跳过，并在结果里列出「以下媒体库无法访问，已跳过」。
但**不要**在硬盘未连接时点「清理失效记录」—— 那个操作会按文件是否存在来判断。

**移动文件很慢**
同盘移动是瞬间的（`os.rename`）。跨盘必须完整复制一遍内容，速度取决于硬盘，
面板会显示进度与预计剩余时间。源文件在目标写入成功后才删除。

**改了名字/删了文件，下次扫描会重复入库吗**
不会。编目按绝对路径匹配，应用内的操作会同步更新数据库记录。
在应用外用资源管理器改动的话，重新扫描一次即可对齐。

**点击「选择媒体文件夹」没有弹出系统窗口**
系统选择器只能在 Windows 本机、交互式运行 Django 的桌面会话中打开。若把后端作为
Windows 服务或在远程非交互会话中运行，请在可交互桌面会话中启动应用后再选择文件夹。

**怎么彻底卸载**
删掉 `backend/db.sqlite3` 和 `backend/.app_data/` 即可，你的媒体文件不受影响。
