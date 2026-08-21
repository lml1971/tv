# Cloudflare Worker 直播源聚合 — KV 部署指南

## 📦 文件说明

| 文件 | 用途 |
|---|---|
| `worker.js` | Worker 主代码（已接入 KV 缓存） |
| `wrangler.toml` | Wrangler CLI 部署配置（已启用自动 provisioning） |
| `README.md` | 本说明文档 |

---

## 🚀 部署步骤

### 方式一：Wrangler CLI（推荐）

#### 1. 安装 Wrangler

```bash
npm install -g wrangler
wrangler login
```

#### 2. 直接部署（KV 会自动创建）

本仓库的 `wrangler.toml` 已配置为 **自动 provisioning 模式** ——
`[[kv_namespaces]]` 只写了 `binding = "KV"`，**没有填 `id`**。
这样部署时 Wrangler 会自动以 Worker 名作为前缀创建 KV 命名空间，
本地 `wrangler dev` 也会自动建本地 KV 并持久化。

```bash
wrangler deploy
```

部署成功后终端会输出你的 Worker URL，例如：
```
https://live-aggregator.your-subdomain.workers.dev
```

> 如果需要手动管理 KV，也可以先建再绑：
> ```bash
> wrangler kv:namespace create "live_cache"
> ```
> 然后把输出的 `id` 填到 `wrangler.toml` 的 `id = "..."` 行。

---

### 方式二：Cloudflare Dashboard / Git 集成

#### 1. 连接仓库
- 进入 **Workers & Pages** → **Create application** → **Connect to Git**
- 选择本仓库，确认 **Worker name** 与 `wrangler.toml` 中的 `name`（即 `live-aggregator`）**完全一致**

> ⚠️ 这是 Dashboard 部署最常见的失败原因：
> Worker name 不匹配会直接报
> `The name in your Wrangler configuration file must match the name of your Worker`。

#### 2. KV 会自动创建
- 由于配置里没有写死 `id`，Cloudflare 构建系统会自动 provision KV；
- 资源创建后，其 ID 只会在 Dashboard 显示，**不会回写到仓库**。

#### 3. 如需手动绑定 KV
- 进入 Worker → **Settings** → **Variables**
- 滚动到 **KV Namespace Bindings** → **Add binding**
- 变量名填 `KV`，选择对应的命名空间 → **Save**

---

## 🔗 接口用法

部署后你的 Worker URL 记为 `https://your-worker.xxx.workers.dev`

| 接口 | 说明 |
|---|---|
| `GET /` | 首页，返回分类 + 推广 + 每组前5频道 |
| `GET /?ac=list&t=分组名&pg=1&limit=20` | 按分组分页列表 |
| `GET /?ac=detail&ids=ch_0,ch_1` | 频道详情 |
| `GET /m3u` 或 `/live.m3u` | 输出 M3U 播放列表 |
| `GET /txt` 或 `/live.txt` | 输出 TXT 格式列表 |

---

## 🔧 常见问题 / 构建失败排查

**Q: 构建报错 `The name in your Wrangler configuration file must match...`**
A: Dashboard 里 Worker 的名字和 `wrangler.toml` 的 `name` 字段不一致。
把任意一边改成 `live-aggregator` 重新部署即可。

**Q: 构建报错 `kv_namespaces[0].id: should be a 32-character hex string`**
A: 这是原版 `wrangler.toml` 里占位符 `id = "替换为你的-namespace-id"` 导致的。
本仓库新版已删掉占位符、改用自动 provisioning，重新拉取部署即可。
如果想手动指定，把 `id` 换成真实的 32 位十六进制 namespace ID。

**Q: 绑定后报 `env.KV is undefined`？**
A: 检查 `wrangler.toml` 中 `binding` 名称是否为 `KV`，需与代码中 `env.KV` 一致。
改完后重新 `wrangler deploy`。

**Q: KV 缓存多久刷新一次？**
A: 代码中 `KV_TTL_SECONDS = 600`（10 分钟）。如需调整，修改 `worker.js` 顶部常量后重新部署。

**Q: 没有 KV 绑定能跑吗？**
A: 能。代码做了兼容——没有 KV 时会直接抓取源站，只是每次冷启动会慢一些（最多 15 秒超时）。

**Q: 如何手动清除 KV 缓存？**
A: Dashboard → KV → 找到 `all_channels_v1` 这个 key → 删除即可。下次请求会自动重新抓取。
