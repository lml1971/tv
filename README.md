<div align="center">

# 📺 茂哥点播 & 直播源接口

**TVBox 多仓 / 单仓接口** · **多源直播每日自动聚合**

<br>

<img src="https://avatars.githubusercontent.com/u/194325777?s=96&v=4" alt="茂哥" width="120" style="border-radius: 12px;">

> **"我原以为看不懂代码，就与码无缘了——没想到只要你敢跟 AI 提要求。它写，你跑；跑不通，就再回去嗑。运行正常的那刻，感觉自己也是伪码农了！"**
> ——思路是我的，代码是 AI 的：**我负责不正经思路，它负责正规代码**。

<br>


<br>

[特性](#-特性) · [30 秒接入](#-30-秒接入) · [文件结构](#-文件结构) · [聚合流程](#-聚合流程) · [配置](#️-配置) · [自动更新](#-自动更新) · [FAQ](#-faq)

</div>

---

## 🌳 关于作者

我是个树木医生，熟悉的是病虫害发生规律，不是 Python 和 YAML。后来想给自己攒一份好用的直播源，就打开对话框，跟 AI 一句一句把代码**嗑**了出来：报错、就丢回去……某个时刻，它跑通了，而且挺好用。

<details>
<summary><b>🪲 树医生式开发原则（点开）</b></summary>

<br>

| 老经验 | 落在代码里 |
|---|---|
| 🔍 望闻问切——不看你标没标，看你实不实 | ffprobe 抓流实测帧高，「1080p 虚标实为 480p」当场现形 |
| 🌲 一片林子不能只栽一个树种 | 多源聚合 + `FORCE_KEEP` 兜底，任一上游暴毙也不全军覆没 |
| 💪 树势旺了，虫自然就少 | 并发测速，快的排前面，卡成 PPT 的往后稍稍 |
| 🗺️ 适地适树，各归其位 | 央视归央视、卫视归卫视、地方台归地方台，谁也别串台 |

> 看不懂代码也别怕，我也不懂——**知道自己想要什么，剩下的拿去跟 AI 嗑**。
> 懂代码更好，看到哪里写得笨，尽管提，我拿去再嗑一轮。

</details>

> ⚠️ 仅供学习研究与技术交流，直播源均来自公开网络，不保证稳定性与合法性，请遵守当地法律法规。

---

## ✨ 特性

| | |
|---|---|
| 🔄 **多源聚合** | 自动拉取合并多个上游源，txt / m3u 按内容自动识别，跨源去重 |
| 🗂️ **延用上游分组** | 聚合后不重新分组：上游叫什么组，产物就叫什么组 |
| 🔢 **组名冲突加序号** | 多源组名相同时自动加序号区分（央视频道 / 央视频道2 / 央视频道3…） |
| 🚫 **双重黑名单** | 组名黑名单整组剔除；频道名黑名单整条剔除 |
| 🧹 **剔除无效源** | 并发探测：连接失败 / 404 / 410 判死剔除，防盗链 403 保守保留 |
| 🔍 **真实分辨率** | ffprobe 抓流实测帧高，虚标重写名称，实测 `< 720p` 自动剔除 |
| 🎯 **测速择优** | 并发测连接 / 首包耗时，快者在前，失败源沉底 |
| 📡 **茂哥TV 置顶** | `mgou_tv.txt` 受版本控制，永远首位，不受任何黑名单 / 探测 / 剔除影响 |
| 📦 **双格式产出** | 同步生成 `tv.txt` 与 `tv.m3u`（组名、条目、顺序完全一致） |
| ⏰ **每日自动更新** | GitHub Actions 每日 UTC 17:00（北京时间 01:00）自动跑 |
| 🛡️ **永不断源** | 两阶段推送 + `FORCE_KEEP`，上游全挂也保留上一版列表 |

---

## 🚀 30 秒接入

任意一个 TVBox 类壳子（TVBox、影视仓、猫影视、FongMi……），把地址填进「接口地址」：

| 接口 | 填什么 | 说明 |
|------|--------|------|
| **多仓接口** | `maoge.json` 的 raw 地址 | 一次装进多个仓库，随便挑 |
| **单仓接口** | `maoge.txt` 的 raw 地址 | 茂哥聚合线路列表 |
| **直播源** | `tv.txt` 的 raw 地址 | 填进「直播」，频道按天自动更新 |

填完等几秒，出画面就成了。出不来换一个仓试试——**叶子发黄未必都是虫，也可能是水浇多了**。🔍

---

## 📁 文件结构

```
.
├── scripts/
│   ├── aggregate.py          # 核心聚合：抓取→黑名单→剔除无效源→实测→测速→tv.txt/tv.m3u
│   ├── normalize_tv.py       # 格式清洗：组内归一、去重、排序、严格校验、双格式产出
│   ├── canonical.py          # 频道命名唯一真相来源（CCTV/CGTN/CETV/CHC 归一）
│   ├── output.py             # 产物写出：tv.txt + tv.m3u 双格式
│   ├── validate_lite.py      # 无效源剔除：并发探测 + 缓存 + 预算
│   ├── probe_resolution.py   # 抓流实测真实分辨率
│   ├── speed_test_lite.py    # 轻量测速：HTTP HEAD + 缓存 + 真并发
│   └── ci_assert.py          # 产物断言（茂哥TV 不变量 + 双格式一致性，供 CI 调用）
├── .github/workflows/
│   └── live-aggregator.yml   # 定时工作流
├── sources.txt               # ★ 上游直播源列表（一行一个 URL，最常改）
├── mgou_tv.txt               # ★ 茂哥TV 固定节目（置顶，按需维护）
├── group_blacklist.txt       # ★ 上游组名黑名单（命中整组剔除）
├── name_blacklist.txt        # ★ 频道名黑名单（命中整条剔除）
├── maoge.json / maoge.txt    # 多仓 / 单仓接口
└── tv.txt / tv.m3u           # ★ 最终产物（自动生成，双格式）
```

> 日常只需要动 4 个文本文件：`sources.txt`、`mgou_tv.txt`、`group_blacklist.txt`、`name_blacklist.txt`，都在仓库根目录，改完推送即生效。

---

## 🔄 聚合流程

```
sources.txt
     │
     ▼
 aggregate.py    1 下载（失败不阻塞）→ 2 自动识别 txt / m3u，按上游分组解析
                 3 组名黑名单整组剔除 → 4 跨源组名冲突加序号
                 5 频道名黑名单剔除 → 6 并发探测剔除无效源
                 7 ffprobe 实测分辨率（虚标重写）→ 8 门槛过滤
                 9 并发测速 + 择优 → 10 茂哥TV 置顶 → 11 输出 tv.txt + tv.m3u
     │
     ▼
 normalize_tv.py 组内清洗 → 归一 → 去重 → 排序 → 严格校验 → 写回双格式
     │
     ▼
 ci_assert.py → git commit & push
```

### 分组规则

| 规则 | 说明 |
|------|------|
| **茂哥TV** | 来自 `mgou_tv.txt`，**永远置顶**，不参与黑名单 / 探测 / 剔除 / 排序 |
| **上游组原样保留** | 不做关键词归类：上游 txt 的 `#genre#` 头、m3u 的 `group-title` 就是产物分组 |
| **组名冲突加序号** | 第一个出现的组用原名，后续同名组依次「组名2」「组名3」…… |
| **黑名单组** | `group_blacklist.txt` 命中的组整组剔除 |

---

## 💻 本地运行

```bash
git clone <your-repo-url> && cd <repo>
python scripts/aggregate.py     # 聚合（需 ffmpeg 启用分辨率探测）
python scripts/normalize_tv.py  # 清洗，生成 tv.txt + tv.m3u
```

| 常用命令 | 作用 |
|---|---|
| `DISABLE_PROBE=1 python aggregate.py` | 关闭抓流探测（快速 / 离线） |
| `DISABLE_SPEED=1 python aggregate.py` | 关闭测速择优 |
| `DISABLE_VALIDATE=1 python aggregate.py` | 关闭无效源剔除 |
| `MIN_HEIGHT=1080 python aggregate.py` | 只保留 ≥1080p |
| `python aggregate.py --no-final` | 只聚合，产出扁平 `tv_raw.txt`（调试） |

> 依赖：`requests`（可选）、`ffmpeg`（ffprobe，未安装则自动跳过探测）。

---

## ⚙️ 配置

**改直播源**：编辑 `sources.txt`，一行一个 URL，`#` 开头为注释。txt / m3u 按内容自动识别，无需标注。

```
https://example.com/live1.txt
https://example.com/live2.m3u8   # 行内注释也支持
# https://disabled.source/
```

**茂哥TV 置顶**：编辑 `mgou_tv.txt`，格式 `节目名,地址`，受 git 版本控制，不会被上游覆盖。

**组名黑名单**：编辑 `group_blacklist.txt`，每行一个上游组名，命中整组剔除（`茂哥TV` 为保留组名，请勿删除）。

**频道名黑名单**：编辑 `name_blacklist.txt`，每行一个频道名，命中整条剔除。

> 以上 4 个配置文件都在仓库根目录，改完推送仓库即自动生效（push 会触发工作流重跑）。

**运行参数（环境变量）**：改 `.github/workflows/live-aggregator.yml` 各 step 的 `env`（每个变量旁有注释）；各脚本顶部也注明了默认值。

| 变量 | 默认 | 说明 |
|------|------|------|
| `MIN_HEIGHT` | 720 | 清晰度门槛帧高（360/480/720/1080/2160） |
| `DISABLE_VALIDATE` | 未设 | 设为 `1` 关闭无效源剔除 |
| `VALIDATE_TIMEOUT` | 3 | 无效源探测单条超时（秒） |
| `VALIDATE_WORKERS` | 32 | 无效源探测并发线程数 |
| `VALIDATE_MAX_ITEMS` | 3000 | 单轮最多探测条数（超出随机采样） |
| `VALIDATE_BUDGET_SEC` | 300 | 无效源探测总耗时上限（秒） |
| `DISABLE_PROBE` | 未设 | 设为 `1` 关闭抓流探测 |
| `DISABLE_SPEED` | 未设 | 设为 `1` 关闭测速择优 |
| `FORCE_KEEP` | true | 所有源失败时保留旧 `tv.txt` |
| `SPEED_TIMEOUT` | 2 | 单条测速超时（秒） |
| `SPEED_WORKERS` | 32 | 测速并发线程数 |
| `SPEED_MAX_ITEMS` | 2000 | 单轮最多测速条数 |
| `SPEED_BUDGET_SEC` | 240 | 测速总耗时上限（秒） |

---

## 🤖 自动更新

`.github/workflows/live-aggregator.yml` 已配好：每日 UTC 17:00 自动跑，支持手动 `Run workflow`（可选 `min_height` / `enable_enhance`），自动安装 ffmpeg，仅内容变化时提交。需仓库开启 `contents: write` 权限。

| 阶段 | 做什么 | 目的 |
|------|--------|------|
| **A · 快速通道** | 抓取 + 黑名单 + 剔除无效源 + 清洗，几分钟内必定产出并推送 | 后面出什么岔子，当天都有可用列表 |
| **B · 增强通道** | 无效源复验 + 抓流实测分辨率 + 测速择优（双预算限流） | 超时也只损失优化，不影响已推送的产物 |

---

## 📝 输出格式

tv.txt（TVBox 类壳子「直播」通用）：

```
茂哥TV,#genre#
幸福家,https://example.com/1.mp4

央视频道,#genre#
CCTV-1 综合,http://example.com/cctv1.m3u8
CCTV-2 财经,http://example.com/cctv2.m3u8
```

tv.m3u（与 tv.txt 同组名、同条目、同顺序）：

```
#EXTM3U
#EXTINF:-1 tvg-name="幸福家" group-title="茂哥TV",幸福家
https://example.com/1.mp4
#EXTINF:-1 tvg-name="CCTV-1 综合" group-title="央视频道",CCTV-1 综合
http://example.com/cctv1.m3u8
```

分组头 `分组名,#genre#`，条目 `节目名,播放地址`，分组间空行；支持 `http/https/rtsp/rtp/udp://`。两个文件均由脚本自动生成，组名来自上游源。

---

## ❓ FAQ

<details>
<summary><b>怎么加直播源？</b></summary>

`sources.txt` 加一行 URL，脚本自动拉取、探测、合并。
</details>

<details>
<summary><b>为什么有些频道被剔除了？</b></summary>

四种情况：频道名命中 `name_blacklist.txt`；所在组命中 `group_blacklist.txt`；探测判死（连接失败 / 404 / 410）；实测帧高 `< MIN_HEIGHT`（默认 720）。茂哥TV 置顶节目不受任何剔除影响。
</details>

<details>
<summary><b>为什么产物里有很多带序号的重复组名？</b></summary>

这是「延用上游分组」的设计：每个上游源的分组原样保留，多源组名相同时按出现顺序加序号（央视频道 / 央视频道2 / 央视频道3……），避免不同源的频道混在一起。想把某些组合并或剔除，改 `group_blacklist.txt`。
</details>

<details>
<summary><b>所有源都挂了会怎样？</b></summary>

`FORCE_KEEP=true`（默认）保留上一次 `tv.txt`，脚本正常退出。
</details>

<details>
<summary><b>同名频道怎么择优？</b></summary>

按测速耗时升序，快的在前。
</details>

<details>
<summary><b>为什么 CCTV-1 只有一条？</b></summary>

`canonical.py` 把 `CCTV1 / CCTV-1 / CCTV-1 综合 / CCTV-1(720p)` 归一后去重，`ci_assert.py` 断言产物中不允许残留别名。
</details>

<details>
<summary><b>想立刻跑一次？</b></summary>

GitHub → Actions → Aggregate Live Sources → Run workflow，或本地 `python scripts/aggregate.py`。
</details>

---

<div align="center">

🌱 **觉得有用，欢迎 Star——就像给一棵病树除掉虫子，新芽会从你这一步开始。**

</div>
