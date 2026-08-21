# 📺 直播源聚合 Cloudflare Worker

一个运行在 Cloudflare Workers 上的**直播源聚合服务**，自动抓取多个远程直播源（M3U / TXT 格式），合并去杂后通过统一接口输出，支持 **JSON API / M3U / TXT** 三种格式，可直接对接 TVBox、影音猫等播放器。

---

## ✨ 功能特性

- **多源聚合** — 同时抓取 3 个远程直播源，自动识别 M3U / TXT 格式并解析
- **KV 缓存** — 接入 Cloudflare KV，缓存 10 分钟，避免每次冷启动重新抓取
- **广告过滤** — 内置垃圾关键词黑名单，自动过滤加群、推广、防失联等无效频道
- **引流注入** — 在频道列表顶部插入自定义推广视频（宣传片 / 短视频等）
- **三格式输出** — JSON（TVBox 兼容）、M3U（播放器兼容）、TXT（传统直播源格式）
- **分页支持** — JSON 接口支持按分组分页查询，单页默认 20 条，最大 500 条
- **CORS 全开** — 响应头允许跨域，可直接被前端 / 播放器调用
- **超时保护** — 单源抓取 15 秒超时，失败不阻塞其他源

---

## 📁 文件结构

```
.
├── worker.js        # Worker 主代码（核心逻辑）
├── wrangler.toml    # Wrangler CLI 部署配置
├── README.md        # 本文档
├── maoge.json       # 茂哥仓库源配置（TVBox 多仓格式）
├── maoge.txt        # 茂哥直播源 URL 列表
└── tv.txt           # 老李直播源（TXT 格式，含 CCTV / 卫视 / 地方台等）
```

---

## 🚀 部署指南

### 方式一：Wrangler CLI（推荐）

#### 1. 安装 Wrangler

```bash
npm install -g wrangler
wrangler login
```

#### 2. 部署（KV 自动创建）

`wrangler.toml` 已配置为 **自动 provisioning 模式**——`[[kv_namespaces]]` 只写了 `binding = "KV"`，没有写死 `id`。部署时 Wrangler 会自动以 Worker 名作为前缀创建 KV 命名空间。

```bash
wrangler deploy
```

部署成功后终端会输出类似：

```
✅  Deployment complete!
🔗  https://live-aggregator.your-subdomain.workers.dev
```

> **手动管理 KV（可选）：**
> ```bash
> wrangler kv:namespace create "live_cache"
> ```
> 将输出的 32 位 ID 填入 `wrangler.toml` 的 `id = "..."` 行。

#### 3. 本地开发

```bash
wrangler dev
```

本地会自动创建 KV 并持久化到磁盘，方便调试。

---

### 方式二：Cloudflare Dashboard + Git 集成

#### 1. 连接仓库

进入 **Workers & Pages** → **Create application** → **Connect to Git**，选择本仓库。

> ⚠️ **关键**：Dashboard 中 Worker 的名字必须与 `wrangler.toml` 中的 `name` 字段**完全一致**（即 `live-aggregator`），否则会报错：
> ```
> The name in your Wrangler configuration file must match the name of your Worker
> ```

#### 2. KV 自动创建

构建系统会自动 provision KV 命名空间，无需手动操作。资源创建后其 ID 仅在 Dashboard 显示，不会回写到仓库。

#### 3. 如需手动绑定 KV

- 进入 Worker → **Settings** → **Variables**
- 滚动到 **KV Namespace Bindings** → **Add binding**
- 变量名填 `KV`，选择对应命名空间 → **Save**

---

## 🔗 接口用法

部署后将你的 Worker URL 记为 `https://your-worker.xxx.workers.dev`

### 首页 — 获取全部分组 + 引流内容

```
GET /
```

返回 JSON，包含 `class`（分组列表）和 `list`（引流视频 + 每组前 5 个频道）。

### 分组列表 — 按分组分页查询

```
GET /?ac=list&t=央视频道&pg=1&limit=20
```

| 参数 | 说明 | 默认值 |
|---|---|---|
| `t` | 分组名称（如 `央视频道`、`卫视频道`） | 必填 |
| `pg` | 页码 | `1` |
| `limit` | 每页条数（最大 500） | `20` |

### 频道详情

```
GET /?ac=detail&ids=ch_0,ch_1,ch_2
```

### M3U 播放列表

```
GET /m3u
GET /live.m3u
```

直接返回标准 M3U 格式，可粘贴到 VLC / PotPlayer / TVBox 等播放器使用。

### TXT 直播源

```
GET /txt
GET /live.txt
```

返回 `频道名,URL` 格式的传统直播源文本。

---

## ⚙️ 配置说明

### 数据源（`worker.js` → `SOURCE_URLS`）

```js
const SOURCE_URLS = [
    { url: "https://0701.tv1288.xyz/m3u", format: "m3u" },
    { url: "https://m3u.lml1971.ccwu.cc/xymm" },           // 自动识别格式
    { url: "https://5266.kstore.space/xiangxichuanshuo.txt", format: "txt" },
];
```

- `format` 字段可选 `m3u` / `txt`，不填则根据内容自动判断
- 支持无限扩展，直接往数组里加即可

### 引流视频（`worker.js` → `PROMO_LIST`）

每个引流项包含：

| 字段 | 说明 |
|---|---|
| `title` | 显示标题 |
| `url` | 视频直链（MP4 等） |
| `pic` | 封面图 URL |
| `group` | 所属分组名 |
| `from` | 播放来源标识 |
| `remarks` | 备注文字 |

### 垃圾过滤（`worker.js` → `SPAM_KEYWORDS`）

包含以下关键词的频道或分组会被自动剔除：

```
注意事项、加群、TG频道、轮播视频、关注Q群、交流群、
防失联、防丢关注、网址、官网、广告位、微信公众号、
最新资源、获取资源、备用地址、防丢地址、更新时间、关于本源
```

### KV 缓存参数

| 常量 | 值 | 说明 |
|---|---|---|
| `KV_CACHE_KEY` | `"all_channels_v1"` | KV 中存储的 key |
| `KV_TTL_SECONDS` | `600`（10 分钟） | KV 过期时间 |
| `CACHE_TTL_MS` | `10 * 60 * 1000` | 内存层过期判断 |
| `FETCH_TIMEOUT_MS` | `15 * 1000` | 单源抓取超时 |

---

## 🔧 常见问题排查

| 问题 | 原因 & 解决方案 |
|---|---|
| `The name in your Wrangler configuration file must match...` | Dashboard 中 Worker 名称与 `wrangler.toml` 的 `name` 不一致，统一改为 `live-aggregator` |
| `kv_namespaces[0].id: should be a 32-character hex string` | 旧版配置写了占位符 `id = "替换为你的-namespace-id"`，删除该行即可（自动 provisioning） |
| `env.KV is undefined` | `wrangler.toml` 中 `binding` 名称不是 `KV`，需与代码中 `env.KV` 一致 |
| 频道列表为空 | 检查 `SOURCE_URLS` 中的地址是否可访问，查看 Worker 日志确认抓取结果 |
| 缓存不刷新 | Dashboard → KV → 删除 `all_channels_v1` 这个 key，下次请求自动重建 |
| 没有 KV 绑定能跑吗？ | 能。代码做了兼容，每次直接抓取源站，只是冷启动会慢一些（最多 15 秒超时） |

---

## 📝 更新日志

| 版本 | 变更 |
|---|---|
| v1.0 | 初始版本，支持 M3U/TXT 双格式解析、KV 缓存、引流注入、广告过滤 |

---

## 📄 License

仅供学习交流使用，请勿用于商业用途。直播源版权归各电视台及内容提供方所有。
