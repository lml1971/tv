/* ============================================================
 * Cloudflare Worker - 直播源聚合 / 引流注入（模板文件）
 * ------------------------------------------------------------
 * 使用方式：
 *   1. 复制本文件为 worker.js（或直接部署本文件）。
 *   2. 仅修改下方【用户配置区】中的内容即可，其余为核心引擎，无需改动。
 *   3. 若需使用 KV 缓存，请在 Cloudflare Dashboard 为 Worker 绑定
 *      一个名为 KV 的 KV Namespace（变量名必须为 KV）。
 *   4. 如需通过环境变量覆盖配置（推荐生产环境使用），可在 Dashboard
 *      → Settings → Environment Variables 中设置，见【环境变量】一节。
 * ============================================================ */


/* ===== 用户配置区（按需修改）==========================================
 * 以下是唯一需要改动的部分。示例值均已用占位符/演示值标注，请替换为
 * 你自己的直播源地址、推流节目与分组规则。
 * ====================================================================== */

/**
 * 直播源列表（必填）
 *   url     : 直播源地址（http/https），支持 m3u / txt 两种格式
 *   format? : 可选，强制指定格式。"m3u" | "txt"，不填则按内容自动判断
 */
const SOURCE_URLS = [
    // { url: "https://example.com/live1.m3u", format: "m3u" },
    // { url: "https://example.com/live2.txt", format: "txt" },
    // { url: "https://example.com/auto-detect" }, // 不指定 format 自动判断
];

/**
 * 推流 / 引流节目列表（选填）
 * 这些节目会保持原样、排在所有直播源前面（置顶引流）。
 *   title    : 展示名称
 *   url      : 视频地址（如 .mp4）
 *   pic      : 封面图地址
 *   group    : 所属分组（决定置顶位置）
 *   from     : 播放线路标识
 *   remarks  : 备注文案
 */
const PROMO_LIST = [
    // {
    //     title: "宣传片1",
    //     url:   "https://example.com/promo1.mp4",
    //     pic:   "https://example.com/promo1.jpg",
    //     group: "推流信息",
    //     from:  "1",
    //     remarks: "置顶引流",
    // },
    // {
    //     title: "宣传片2",
    //     url:   "https://example.com/promo2.mp4",
    //     pic:   "https://example.com/promo2.jpg",
    //     group: "推流信息",
    //     from:  "1",
    //     remarks: "置顶引流",
    // },
];

/**
 * 垃圾/过滤关键词（选填）
 * 频道标题或分组名包含这些关键词时，该频道会被丢弃。
 */
const SPAM_KEYWORDS = [
    // "垃圾关键词1",
    // "广告",
];

/**
 * 重新分组规则（选填 / 可按需增减）
 * 按优先级从上到下匹配，标题命中任一关键词即归入对应分组。
 * 未命中的频道统一归入 DEFAULT_GROUP。
 */
const REGROUP_RULES = [
    { group: "📺 央视",   keywords: ["CCTV", "央视", "中央", "CGTN"] },
    { group: "📡 卫视",   keywords: ["卫视", "湖南", "浙江", "江苏", "东方", "北京", "广东", "深圳", "安徽", "山东", "河南", "河北", "湖北", "江西", "辽宁", "吉林", "黑龙江", "天津", "重庆", "四川", "贵州", "云南", "广西", "福建", "陕西", "甘肃", "青海", "宁夏", "新疆", "西藏", "内蒙古", "海南", "山西", "上海"] },
    { group: "🎬 影视",   keywords: ["电影", "电视剧", "影视", "院线", "影院", "纪录片", "动漫", "动画"] },
    { group: "🏆 体育",   keywords: ["体育", "足球", "篮球", "NBA", "CBA", "英超", "欧冠", "中超", "网球", "乒乓球", "羽毛球", "UFC"] },
    { group: "📰 新闻",   keywords: ["新闻", "资讯", "时事", "财经", "凤凰", "环球"] },
    { group: "🎵 音乐",   keywords: ["音乐", "MTV", "演唱会", "K歌"] },
    { group: "👶 少儿",   keywords: ["少儿", "儿童", "亲子", "Cartoon"] },
    { group: "🎮 游戏",   keywords: ["游戏", "电竞", "LOL", "王者", "GAME"] },
    { group: "🌍 国际",   keywords: ["国际", "美国", "英国", "日本", "韩国", "USA", "UK", "Japan", "Korea"] },
    { group: "📻 广播",   keywords: ["广播", "电台", "Radio", "FM", "AM"] },
    { group: "🎭 综艺",   keywords: ["综艺", "娱乐", "选秀", "脱口秀"] },
    { group: "📚 教育",   keywords: ["教育", "学习", "英语", "留学"] },
    { group: "🏥 健康",   keywords: ["健康", "养生", "医疗", "健身"] },
    { group: "🛒 购物",   keywords: ["购物", "电视购物", "QVC"] },
    { group: "🎬 地方台", keywords: ["地方", "市县", "区县", "乡村"] },
    { group: "📺 港澳台", keywords: ["香港", "澳门", "台湾", "TVB", "台视"] },
];

/** 未匹配到任何分组时的默认分组名 */
const DEFAULT_GROUP = "📺 其他频道";

/* ===== 环境变量（可选覆盖）=============================================
 * 在生产环境，可通过 Cloudflare Dashboard 设置以下环境变量来覆盖
 * 上述硬编码配置（环境变量优先级更高），便于在不改代码的情况下切换
 * 直播源 / 开关功能：
 *   - SOURCE_URLS : JSON 字符串，如 [{"url":"https://...m3u"}]
 *   - ENABLE_PROMO: "true" | "false"  是否注入推流节目，默认 true
 *   - FALLBACK_LOGO_BASE : 自定义台标兜底域名
 * 示例（wrangler / Dashboard）：
 *   wrangler secret put SOURCE_URLS   # 输入 JSON 字符串
 * ====================================================================== */


/* ===== 核心引擎（以下为通用逻辑，通常无需修改）========================= */

// ---------- 缓存与常量 ----------
const CACHE_TTL_MS       = 10 * 60 * 1000;
const DEFAULT_PAGE_SIZE  = 20;
const MAX_RETURN_LIMIT   = 500;
const FALLBACK_LOGO_BASE = (typeof SOURCE_URLS !== "undefined" && self?.FALLBACK_LOGO_BASE) || "https://epg.112114.xyz/logo";
const FETCH_TIMEOUT_MS   = 15 * 1000;

// KV 缓存配置（KV Namespace 绑定变量名须为 KV）
const KV_CACHE_KEY    = "all_channels_v1";
const KV_TTL_SECONDS  = 600; // 10 分钟

// ---------- 工具函数 ----------

function normalizeSource(src) {
    const url = typeof src === "string" ? src : (src && src.url) || "";
    return { url, format: src && src.format, _skip: !isValidHttpUrl(url) };
}

function isValidHttpUrl(str) {
    if (!str || typeof str !== "string") return false;
    try {
        const u = new URL(str);
        return u.protocol === "http:" || u.protocol === "https:";
    } catch {
        return false;
    }
}

function isSpam(text) {
    return text && SPAM_KEYWORDS.some(kw => text.includes(kw));
}

// 从 #EXTINF 行提取属性值（兼容有/无引号）
function extractAttr(line, key) {
    const re = new RegExp(
        key + '=(?:"([^"]+)"|\'([^\']+)\'|([^,\\s][^,]*?)(?=,\\s*\\w+=|$))'
    );
    const m = line.match(re);
    return m ? (m[1] || m[2] || m[3] || "").trim() : "";
}

async function fetchWithTimeout(url, timeoutMs) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    try {
        return await fetch(url, {
            headers: {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "*/*",
            },
            signal: controller.signal,
        });
    } finally {
        clearTimeout(timer);
    }
}

// ---------- 重新分组核心逻辑 ----------

function matchGroup(title) {
    if (!title) return DEFAULT_GROUP;
    for (const rule of REGROUP_RULES) {
        for (const kw of rule.keywords) {
            if (title.includes(kw)) {
                return rule.group;
            }
        }
    }
    return DEFAULT_GROUP;
}

function regroupChannels(channels) {
    return channels.map(ch => ({
        ...ch,
        orig_group: ch.group,
        group: matchGroup(ch.title),
    }));
}

// ---------- 解析器 ----------

function parseM3U(text) {
    const list = [];
    let current = null;

    for (const line of text.split('\n')) {
        const trimmed = line.trim();
        if (!trimmed) continue;

        if (trimmed.startsWith('#EXTINF')) {
            const group = extractAttr(trimmed, 'group-title') || "默认频道";
            let logo = extractAttr(trimmed, 'tvg-logo');
            const commaIdx = trimmed.lastIndexOf(',');
            const title = commaIdx > -1 ? trimmed.substring(commaIdx + 1).trim() : "未知频道";
            if (!logo) logo = `${FALLBACK_LOGO_BASE}/${encodeURIComponent(title)}.png`;
            current = { group, logo, title };
        } else if (trimmed.startsWith('#')) {
            continue;
        } else if (current) {
            const urls = trimmed.split(',').map(s => s.trim()).filter(Boolean);
            if (urls.length > 0) {
                const channel = { ...current, url: urls[0], urls };
                if (!isSpam(channel.group) && !isSpam(channel.title)) {
                    list.push(channel);
                }
            }
            current = null;
        }
    }
    return list;
}

function parseTXT(text) {
    const list = [];
    let currentGroup = "默认频道";

    for (const raw of text.split('\n')) {
        const line = raw.trim();
        if (!line || line.startsWith('#')) continue;

        if (/,#genre#\s*$/i.test(line)) {
            currentGroup = line.split(',')[0].trim() || "默认频道";
            continue;
        }

        const commaIdx = line.indexOf(',');
        if (commaIdx < 0) continue;
        const title = line.substring(0, commaIdx).trim();
        let urlPart = line.substring(commaIdx + 1).trim();
        if (!title || !urlPart) continue;

        const hashIdx = urlPart.indexOf('#');
        if (hashIdx !== -1 && urlPart.substring(hashIdx + 1).trim()) {
            urlPart = urlPart.substring(0, hashIdx).trim();
        }
        if (!urlPart || isSpam(currentGroup) || isSpam(title)) continue;

        list.push({
            group: currentGroup,
            title,
            logo: `${FALLBACK_LOGO_BASE}/${encodeURIComponent(title)}.png`,
            url: urlPart,
            urls: [urlPart],
        });
    }
    return list;
}

function parseSource(text, formatHint) {
    const isM3U = formatHint === "m3u"
        ? true
        : formatHint === "txt"
            ? false
            : text.includes('#EXTM3U') || text.includes('#EXTINF');
    return isM3U ? parseM3U(text) : parseTXT(text);
}

// ---------- 抓取与合并（已接入 KV 缓存）----------

async function fetchOneSource(srcConfig) {
    const { url, format, _skip } = normalizeSource(srcConfig);
    if (_skip) {
        console.error(`[fetchOneSource] 跳过无效 URL: ${url || "(empty)"}`);
        return { source: url || "(invalid)", channels: [], error: "Invalid URL" };
    }
    try {
        const resp = await fetchWithTimeout(url, FETCH_TIMEOUT_MS);
        if (!resp.ok) {
            console.error(`[fetchOneSource] HTTP ${resp.status} for ${url}`);
            return { source: url, channels: [], error: `HTTP ${resp.status}` };
        }
        const text = await resp.text();
        if (!text || !text.trim()) {
            console.error(`[fetchOneSource] Empty body from ${url}`);
            return { source: url, channels: [], error: "Empty body" };
        }
        const channels = parseSource(text, format);
        console.log(`[fetchOneSource] ${url} -> ${channels.length} channels`);
        return { source: url, channels, error: null };
    } catch (err) {
        console.error(`[fetchOneSource] ${url} -> ${err.message}`);
        return { source: url, channels: [], error: err.message };
    }
}

// 解析来源列表：优先环境变量 SOURCE_URLS（JSON），否则用硬编码配置
function resolveSourceUrls(env) {
    if (env && env.SOURCE_URLS) {
        try {
            const parsed = JSON.parse(env.SOURCE_URLS);
            if (Array.isArray(parsed) && parsed.length > 0) return parsed;
        } catch (e) {
            console.error(`[resolveSourceUrls] 环境变量 SOURCE_URLS 解析失败: ${e.message}`);
        }
    }
    return SOURCE_URLS;
}

// 是否启用推流节目注入（环境变量 ENABLE_PROMO=false 可关闭）
function resolveEnablePromo(env) {
    if (env && typeof env.ENABLE_PROMO === "string") {
        return env.ENABLE_PROMO !== "false";
    }
    return true;
}

async function loadAllChannels(env, ctx) {
    const sources = resolveSourceUrls(env);
    const enablePromo = resolveEnablePromo(env);

    if (enablePromo && PROMO_LIST.length > 0) {
        console.log(`[loadAllChannels] 推流节目注入已启用 (${PROMO_LIST.length} 条)`);
    } else {
        console.log(`[loadAllChannels] 推流节目注入已禁用`);
    }

    // 1. 尝试从 KV 读取
    if (env && env.KV) {
        try {
            const cached = await env.KV.get(KV_CACHE_KEY, { type: "json" });
            if (cached && cached.expireAt > Date.now()) {
                console.log(`[loadAllChannels] KV cache HIT, ${cached.channels.length} channels`);
                return cached.channels;
            }
            if (cached) {
                console.log(`[loadAllChannels] KV cache EXPIRED, re-fetching`);
            } else {
                console.log(`[loadAllChannels] KV cache MISS`);
            }
        } catch (e) {
            console.error(`[loadAllChannels] KV read error: ${e.message}`);
        }
    } else {
        console.log(`[loadAllChannels] No KV binding found, fetching directly`);
    }

    // 2. KV 未命中或已过期，抓取所有源
    const results = await Promise.all(sources.map(u => fetchOneSource(u)));
    const successCount = results.filter(r => r.error === null).length;
    const totalChannels = results.reduce((sum, r) => sum + r.channels.length, 0);
    console.log(`[loadAllChannels] ${successCount}/${results.length} sources OK, ${totalChannels} channels`);

    // 3. 合并所有源（不去重，保留全部条目）
    const merged = [];
    for (const result of results) {
        for (const ch of result.channels) {
            merged.push({ ...ch });
        }
    }

    // 4. 重新分组：按标题关键词自动归类
    const regrouped = regroupChannels(merged);
    console.log(`[loadAllChannels] ${merged.length} merged, ${regrouped.length} after regroup`);

    // 5. 异步写回 KV（不阻塞响应）
    const writeKV = async () => {
        if (!env || !env.KV) return;
        try {
            const cacheData = {
                channels: regrouped,
                expireAt: Date.now() + CACHE_TTL_MS,
            };
            await env.KV.put(KV_CACHE_KEY, JSON.stringify(cacheData), {
                expirationTtl: KV_TTL_SECONDS,
            });
            console.log(`[loadAllChannels] KV cache written, ${regrouped.length} channels`);
        } catch (e) {
            console.error(`[loadAllChannels] KV write error: ${e.message}`);
        }
    };

    if (ctx && typeof ctx.waitUntil === "function") {
        ctx.waitUntil(writeKV());
    } else {
        await writeKV();
    }

    return regrouped;
}

// ---------- Vod 构造 ----------

function buildPromoVods() {
    return PROMO_LIST.map((p, idx) => ({
        vod_id:        `live_promo_${idx}`,
        vod_name:      p.title,
        vod_pic:       p.pic || "",
        vod_remarks:   p.remarks || "引流",
        vod_play_from: p.from  || "推广线路",
        vod_play_url:  `${p.title}$${p.url}`,
        type_name:     p.group || "推流信息",
    }));
}

function channelToVod(ch, idx) {
    const playUrl = ch.urls && ch.urls.length > 1
        ? `${ch.title}$${ch.urls.join('#')}`
        : `${ch.title}$${ch.url}`;
    return {
        vod_id:        `ch_${idx}`,
        vod_name:      ch.title,
        vod_pic:       ch.logo,
        vod_remarks:   "直播",
        vod_play_from: ch.group,
        vod_play_url:  playUrl,
        type_name:     ch.group,
    };
}

// ---------- 响应构造 ----------

function buildHomeResponse(channels) {
    const groupMap = new Map();
    channels.forEach((ch, i) => {
        if (!groupMap.has(ch.group)) groupMap.set(ch.group, []);
        groupMap.get(ch.group).push({ ch, i });
    });

    const promoGroups = Array.from(new Set(PROMO_LIST.map(p => p.group || "推流信息")));
    const otherGroups = Array.from(groupMap.keys())
        .filter(g => !promoGroups.includes(g))
        .sort();
    const allGroups = [...promoGroups, ...otherGroups];

    const class_list = allGroups.map(g => ({ type_id: g, type_name: g }));

    const promoVods = buildPromoVods();
    const groupVods = [];
    for (const g of otherGroups) {
        const items = (groupMap.get(g) || []).slice(0, 5);
        for (const { ch, i } of items) groupVods.push(channelToVod(ch, i));
    }

    return { class: class_list, list: [...promoVods, ...groupVods] };
}

function buildCategoryResponse(channels, typeId, page, pageSize) {
    if (!typeId) {
        return { page: 1, pagecount: 1, limit: pageSize, total: 0, list: [], notice: "typeId (参数 t) 不能为空" };
    }

    const promoGroups = new Set(PROMO_LIST.map(p => p.group || "推流信息"));
    const list = [];

    if (promoGroups.has(typeId)) {
        list.push(...buildPromoVods().filter(v => v.type_name === typeId));
    }
    channels.forEach((ch, i) => {
        if (ch.group === typeId) list.push(channelToVod(ch, i));
    });

    const total = Math.min(list.length, MAX_RETURN_LIMIT);
    const totalPage = Math.max(1, Math.ceil(total / pageSize));
    const safePage = Math.min(page, totalPage);
    const start = (safePage - 1) * pageSize;

    return {
        page: safePage,
        pagecount: totalPage,
        limit: pageSize,
        total,
        list: list.slice(start, start + pageSize),
    };
}

function buildDetailResponse(channels, ids) {
    const idSet = new Set(ids);
    const list = [];

    for (const v of buildPromoVods()) {
        if (idSet.has(v.vod_id)) list.push(v);
    }
    channels.forEach((ch, i) => {
        const vodId = `ch_${i}`;
        if (idSet.has(vodId)) list.push(channelToVod(ch, i));
    });

    return { list };
}

function buildM3U(channels) {
    const lines = ['#EXTM3U'];
    for (const p of PROMO_LIST) {
        lines.push(`#EXTINF:-1 tvg-logo="${p.pic || ''}" group-title="${p.group || '推流信息'}",${p.title}`);
        lines.push(p.url);
    }
    for (const ch of channels) {
        lines.push(`#EXTINF:-1 tvg-logo="${ch.logo}" group-title="${ch.group}",${ch.title}`);
        lines.push(ch.urls && ch.urls.length > 1 ? ch.urls.join(',') : ch.url);
    }
    return lines.join('\n');
}

function buildTXT(channels) {
    const groupMap = new Map();
    for (const p of PROMO_LIST) {
        const g = p.group || "推流信息";
        if (!groupMap.has(g)) groupMap.set(g, []);
        groupMap.get(g).push({ title: p.title, url: p.url });
    }
    for (const ch of channels) {
        if (!groupMap.has(ch.group)) groupMap.set(ch.group, []);
        const u = ch.urls && ch.urls.length > 0 ? ch.urls[0] : ch.url;
        groupMap.get(ch.group).push({ title: ch.title, url: u });
    }
    const promoGroups = new Set(PROMO_LIST.map(p => p.group || "推流信息"));
    const groupOrder = [
        ...Array.from(promoGroups),
        ...Array.from(groupMap.keys()).filter(g => !promoGroups.has(g)).sort(),
    ];

    const out = [];
    for (const group of groupOrder) {
        const items = groupMap.get(group) || [];
        if (items.length === 0) continue;
        out.push(`${group},#genre#`);
        for (const it of items) out.push(`${it.title},${it.url}`);
        out.push('');
    }
    return out.join('\n');
}

// ---------- 主入口 ----------

const corsHeaders = {
    "Access-Control-Allow-Origin":  "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "*",
};

function jsonResponse(obj, status = 200) {
    return new Response(JSON.stringify(obj), {
        status,
        headers: { ...corsHeaders, "Content-Type": "application/json; charset=utf-8" },
    });
}

export default {
    async fetch(request, env, ctx) {
        const url = new URL(request.url);
        const path = url.pathname;
        const params = url.searchParams;

        if (request.method === "OPTIONS") {
            return new Response(null, { headers: corsHeaders });
        }

        try {
            const channels = await loadAllChannels(env, ctx);

            if (path === '/m3u' || path === '/live.m3u') {
                return new Response(buildM3U(channels), {
                    headers: { ...corsHeaders, "Content-Type": "audio/x-mpegurl; charset=utf-8" },
                });
            }

            if (path === '/txt' || path === '/live.txt') {
                return new Response(buildTXT(channels), {
                    headers: { ...corsHeaders, "Content-Type": "text/plain; charset=utf-8" },
                });
            }

            const ac = params.get('ac');

            if (ac === 'detail') {
                const ids = (params.get('ids') || '').split(',').filter(Boolean);
                return jsonResponse(buildDetailResponse(channels, ids));
            }

            if (ac === 'list' || params.has('t')) {
                const typeId = params.get('t') || '';
                const page = parseInt(params.get('pg') || '1', 10) || 1;
                const size = parseInt(params.get('limit') || String(DEFAULT_PAGE_SIZE), 10) || DEFAULT_PAGE_SIZE;
                return jsonResponse(buildCategoryResponse(channels, typeId, page, size));
            }

            return jsonResponse(buildHomeResponse(channels));

        } catch (err) {
            console.error(`[fetch] Unhandled error: ${err.message}`);
            return jsonResponse({ error: true, message: err.message || String(err) }, 500);
        }
    },
};
