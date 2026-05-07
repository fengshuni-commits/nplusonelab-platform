// N+1 LAB 采购助手 v7.4 - Content Script
//
// v7.2.4 核心修复：
//   将"购物车数量轮询"改为"MutationObserver 监测加购成功弹窗"
//   根本原因：淘宝商品详情页根本没有购物车角标 DOM 元素，
//   getCartCount() 始终返回 -1，轮询条件永远不成立。
//   新方案：用 MutationObserver 监听 document.body 的子树变化，
//   一旦出现包含"加入购物车"/"已加入"文字的弹窗节点，立即触发跳转。
//   这个方案完全不依赖购物车角标，也不受 stopPropagation 影响。

console.log("🦐 N+1 采购助手 v7.6 已加载");

// ============ 订单同步 / 发票下载 MVP ============
const API_BASES = [
    'https://platform.nplusonelab.com/api',
    'https://platform.nplusonelab.com',
    'http://43.156.225.39:8080',
    'http://localhost:8080',
    'http://43.156.225.39:8000',
    'http://localhost:8000'
];
const API_KEY = 'n1lab2026';

function isTaobaoOrderPage() {
    const h = location.hostname;
    return h.includes('buyertrade.taobao.com') || h.includes('trade.taobao.com') || h.includes('myseller.taobao.com');
}

function isInvoicePage() {
    return location.hostname.includes('invoice.taobao.com');
}

function normalizeText(value) {
    return (value || '').replace(/\s+/g, ' ').trim();
}

function parseMoney(value) {
    if (value === undefined || value === null) return 0;
    const cleaned = String(value).replace(/[^\d.\-]/g, '');
    const num = parseFloat(cleaned);
    return Number.isFinite(num) ? num : 0;
}

function isLikelyInvoiceCandidate(text) {
    const t = normalizeText(text);
    if (!t) return false;
    return ['开票', '申请发票', '电子发票', '发票已开', '开票中', '发票'].some(k => t.includes(k));
}

function findTextByPatterns(text, patterns) {
    for (const p of patterns) {
        const m = text.match(p);
        if (m && m[1]) return normalizeText(m[1]);
    }
    return '';
}

function collectTextCandidates(el, selector) {
    return Array.from(el.querySelectorAll(selector))
        .map(n => normalizeText(n.innerText || n.textContent || ''))
        .filter(Boolean);
}

function uniqueTexts(list) {
    return Array.from(new Set(list.map(normalizeText).filter(Boolean)));
}

function pickSellerName(el, text, links) {
    const headerTexts = uniqueTexts(collectTextCandidates(el, 'a, span, div'));
    const exactShop = headerTexts.find(t => /旗舰店|企业店|专卖店|专营店|店铺|商行|五金|工具/.test(t) && t.length <= 30 && !/订单详情|订单号|卖家已发货|查看物流/.test(t));
    if (exactShop) return exactShop;

    const directCandidates = uniqueTexts([
        ...collectTextCandidates(el, '.seller, .shop, [class*="seller"], [class*="shop"], [data-reactid*="shop"]'),
        ...headerTexts.filter(t => t.length <= 60)
    ]).filter(t => !/订单号|官方客服|联系卖家|更多|删除订单|申请开票|查看物流|订单详情|卖家已发货|再买一单|手机订单/.test(t));

    const shopLike = directCandidates.filter(t => /旗舰店|企业店|专卖店|专营店|店铺|商行|五金|工具/.test(t));
    if (shopLike.length) {
        return shopLike.sort((a, b) => a.length - b.length)[0];
    }
    if (directCandidates.length) {
        return directCandidates.sort((a, b) => a.length - b.length)[0];
    }

    const patternValue = findTextByPatterns(text, [
        /(?:店铺|店名|卖家)[:：]\s*([^\n\r]+?)(?:\s{2,}|订单号|商品|金额|状态|$)/,
        /(?:来自|商家)[:：]\s*([^\n\r]+?)(?:\s{2,}|订单号|商品|金额|状态|$)/
    ]);
    if (patternValue) return patternValue;

    return (links.find(a => /旗舰店|企业店|专卖店|专营店|店铺|商行|五金|工具/.test(a.text))?.text || '').slice(0, 100);
}

function pickProductTitle(el, text) {
    const blocked = /订单号|实付款|更多|查看物流|确认收货|删除订单|申请开票|开票|卖了换钱|联系卖家|官方客服|订单详情|再次购买|退款|卖家已发货|手机订单|先用后付|确认收货后再付款/;
    const titleCandidates = uniqueTexts([
        ...collectTextCandidates(el, '.item-title, .title, .desc, .goods-title, [class*="title"], [class*="itemName"], [class*="goodsName"]'),
        ...collectTextCandidates(el, 'a, span, div')
    ]).filter(t => t && t.length >= 6 && t.length <= 220 && !/^\d+$/.test(t) && !blocked.test(t));

    const preferred = titleCandidates.filter(t => {
        if (/旗舰店|企业店|专卖店|专营店|店铺|商行/.test(t)) return false;
        if (!/[\u4e00-\u9fa5A-Za-z]/.test(t)) return false;
        return /[\u4e00-\u9fa5]/.test(t) && t.length >= 12;
    });

    const sorted = (preferred.length ? preferred : titleCandidates).sort((a, b) => {
        const aScore = (/交易快照/.test(a) ? 3 : 0) + (/【|】|\(|\)|（|）/.test(a) ? 1 : 0) + (a.length > 18 ? 1 : 0);
        const bScore = (/交易快照/.test(b) ? 3 : 0) + (/【|】|\(|\)|（|）/.test(b) ? 1 : 0) + (b.length > 18 ? 1 : 0);
        if (bScore !== aScore) return bScore - aScore;
        return b.length - a.length;
    });

    if (sorted[0]) return sorted[0];

    return findTextByPatterns(text, [
        /(?:商品|宝贝)[:：]\s*([^\n\r]+?)(?:\s{2,}|订单号|金额|状态|$)/
    ]).slice(0, 300);
}

function pickOrderStatus(text) {
    const normalized = normalizeText(text);
    const orderedPatterns = [
        ['退款中', ['退款中', '退款申请中', '退货退款中']],
        ['退款成功', ['退款成功', '已退款']],
        ['交易关闭', ['交易关闭', '订单关闭', '已关闭']],
        ['待付款', ['等待买家付款', '待付款']],
        ['待发货', ['等待卖家发货', '卖家待发货', '待发货']],
        ['卖家已发货', ['卖家已发货']],
        ['待收货', ['等待买家确认收货', '待收货', '运输中', '派送中']],
        ['交易成功', ['交易成功', '交易完成', '已签收', '已完成', '确认收货']]
    ];

    for (const [label, variants] of orderedPatterns) {
        if (variants.some(v => normalized.includes(v))) return label;
    }
    return '';
}

function normalizeInvoiceStatus(text, hasDownloadLink) {
    const normalized = normalizeText(text);
    if (hasDownloadLink) return '已下载';
    if (!normalized) return '未知';
    if (/已开票|开票成功|发票已开/.test(normalized)) return '已开票';
    if (/开票中|申请中|待开票/.test(normalized)) return '开票中';
    if (/可开票|申请发票|去开票|电子发票|发票服务/.test(normalized)) return '可开票';
    if (/先用后付|确认收货后再付款|手机订单|查看物流|再买一单/.test(normalized)) return '未知';
    return '未知';
}

function extractTaobaoOrders() {
    const cards = Array.from(document.querySelectorAll('tr, li, .trade-order-main, .item-mod__trade-order___, .js-order-container, .order-item, .trade-order-item, [class*="order"]'));
    const items = [];
    const seen = new Set();

    cards.forEach((el) => {
        const text = normalizeText(el.innerText || el.textContent || '');
        if (!text) return;
        const orderMatches = text.match(/\b\d{16,20}\b/g) || [];
        const orderNo = orderMatches[0];
        if (!orderNo || seen.has(orderNo)) return;
        seen.add(orderNo);

        const links = Array.from(el.querySelectorAll('a[href]')).map(a => ({ href: a.href, text: normalizeText(a.innerText || a.textContent || '') }));
        const fileLink = links.find(a => /invoice|fp\./i.test(a.href) || /下载|发票/.test(a.text));

        const skuNode = el.querySelector('.sku, .spec, .item-sku, [class*="sku"], [class*="spec"]');
        const amountNode = el.querySelector('.amount, .price, .real-total, [class*="amount"], [class*="price"], [class*="pay"]');
        const timeMatch = text.match(/20\d{2}[-/.年]\d{1,2}[-/.月]\d{1,2}(?:\s+\d{1,2}:\d{2}(?::\d{2})?)?/);

        const productTitle = pickProductTitle(el, text);
        const sellerText = pickSellerName(el, text, links);
        const amountText = normalizeText(amountNode?.innerText || '') || ((text.match(/(?:实付款|订单总额|合计|金额)[:：]?\s*[¥￥]?\s*\d+(?:\.\d+)?/) || [''])[0]);
        const skuText = normalizeText(skuNode?.innerText || '') || findTextByPatterns(text, [
            /规格[:：]\s*([^¥]+?)(?:实付款|订单总额|金额|状态|$)/,
            /型号[:：]\s*([^¥]+?)(?:实付款|订单总额|金额|状态|$)/
        ]);
        const orderStatus = pickOrderStatus(text);
        const invoiceCandidate = isLikelyInvoiceCandidate(text);
        const invoiceStatus = normalizeInvoiceStatus(links.find(a => /发票|开票/.test(a.text))?.text || text, Boolean(fileLink));

        items.push({
            taobao_order_no: orderNo,
            order_time: timeMatch ? timeMatch[0] : '',
            seller_name: sellerText.slice(0, 100),
            buyer_name: '',
            product_title: productTitle.slice(0, 300),
            sku_text: skuText.slice(0, 200),
            amount_text: amountText.slice(0, 80),
            amount_value: parseMoney(amountText),
            order_status: orderStatus,
            invoice_status: invoiceStatus,
            invoice_candidate: invoiceCandidate,
            source_page_url: location.href,
            raw_payload: JSON.stringify({
                text: text.slice(0, 3000),
                debug: {
                    sellerText,
                    productTitle,
                    orderStatus,
                    invoiceStatus,
                    linkTexts: links.slice(0, 8)
                }
            })
        });
    });

    if (items.length === 0) {
        const text = normalizeText(document.body?.innerText || '');
        const orderNos = Array.from(new Set(text.match(/\b\d{16,20}\b/g) || [])).slice(0, 30);
        return orderNos.map((orderNo) => ({
            taobao_order_no: orderNo,
            order_time: '',
            seller_name: '',
            buyer_name: '',
            product_title: '',
            sku_text: '',
            amount_text: '',
            amount_value: 0,
            order_status: '',
            invoice_status: isLikelyInvoiceCandidate(text) ? '可开票' : '未知',
            invoice_candidate: isLikelyInvoiceCandidate(text),
            source_page_url: location.href,
            raw_payload: JSON.stringify({ text: text.slice(0, 2000) })
        }));
    }

    return items;
}

function extractTaobaoInvoices() {
    const rows = Array.from(document.querySelectorAll('tr, li, .invoice-item, .invoice-list-item, .fp-table-row, [class*="invoice"]'));
    const items = [];
    const seen = new Set();

    rows.forEach((el) => {
        const text = normalizeText(el.innerText || el.textContent || '');
        if (!text || !/发票|开票|下载/.test(text)) return;

        const orderMatch = text.match(/\b\d{16,20}\b/);
        const invoiceMatch = text.match(/(?:发票号|票据号码|发票号码)[:：]?\s*([A-Za-z0-9\-]+)/);
        const key = `${orderMatch ? orderMatch[0] : ''}_${invoiceMatch ? invoiceMatch[1] : text.slice(0, 40)}`;
        if (seen.has(key)) return;
        seen.add(key);

        const links = Array.from(el.querySelectorAll('a[href]'));
        const downloadLink = links.find(a => /download|invoice|fp\./i.test(a.href) || /下载/.test(normalizeText(a.innerText || a.textContent || '')));
        const amountMatch = text.match(/[¥￥]\s?\d+(?:\.\d+)?/);

        items.push({
            taobao_order_no: orderMatch ? orderMatch[0] : '',
            invoice_no: invoiceMatch ? invoiceMatch[1] : '',
            invoice_title: normalizeText((el.querySelector('.title, .invoice-title, [class*="title"]')?.innerText) || '').slice(0, 200),
            invoice_amount_text: amountMatch ? amountMatch[0] : '',
            invoice_amount_value: parseMoney(amountMatch ? amountMatch[0] : ''),
            invoice_status: downloadLink ? 'downloaded' : (/已开票|开票成功/.test(text) ? 'issued' : 'pending'),
            file_url: downloadLink ? downloadLink.href : '',
            download_status: downloadLink ? 'downloaded' : 'pending',
            downloaded_file: '',
            source_page_url: location.href,
            raw_payload: JSON.stringify({ text: text.slice(0, 2000) })
        });
    });

    return items;
}

async function postJsonToBackend(path, payload) {
    let lastError = null;
    for (const base of API_BASES) {
        try {
            const resp = await fetch(`${base}${path}`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-Key': API_KEY
                },
                body: JSON.stringify(payload)
            });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
            return await resp.json();
        } catch (err) {
            lastError = err;
        }
    }
    throw lastError || new Error('backend unavailable');
}

async function syncTaobaoOrdersNow() {
    const items = extractTaobaoOrders();
    try {
        const result = await postJsonToBackend('/admin/taobao-orders/sync', { items });
        window.postMessage({ action: 'N1_CAPTURE_TAOBAO_ORDERS_RESULT', payload: { synced: result.synced || items.length, items } }, '*');
        showStatus(`📋 已同步淘宝订单：${result.synced || items.length} 条`, '#722ed1');
    } catch (e) {
        window.postMessage({ action: 'N1_CAPTURE_TAOBAO_ORDERS_RESULT', payload: { error: e.message, items } }, '*');
        showStatus(`⚠️ 同步订单失败：${e.message}`, '#fa8c16');
    }
}

async function syncTaobaoInvoicesNow() {
    const items = extractTaobaoInvoices();
    try {
        const result = await postJsonToBackend('/admin/taobao-invoices/sync', { items });
        window.postMessage({ action: 'N1_CAPTURE_INVOICE_PAGE_RESULT', payload: { synced: result.synced || items.length, items } }, '*');
        showStatus(`🧾 已同步发票：${result.synced || items.length} 条`, '#13c2c2');
    } catch (e) {
        window.postMessage({ action: 'N1_CAPTURE_INVOICE_PAGE_RESULT', payload: { error: e.message, items } }, '*');
        showStatus(`⚠️ 同步发票失败：${e.message}`, '#fa8c16');
    }
}

window.addEventListener('message', async (event) => {
    if (!event.data) return;
    console.log('📨 window message received:', event.data.action, 'host=', location.hostname);
    if (event.data.action === 'N1_CAPTURE_TAOBAO_ORDERS') await syncTaobaoOrdersNow();
    if (event.data.action === 'N1_CAPTURE_INVOICE_PAGE') await syncTaobaoInvoicesNow();
});

chrome.runtime?.onMessage?.addListener((request, sender, sendResponse) => {
    if (!request || !request.action) return;
    if (request.action === 'PING') {
        sendResponse({ ok: true, page: location.href });
        return;
    }
    if (request.action === 'N1_CAPTURE_TAOBAO_ORDERS_INTERNAL') {
        syncTaobaoOrdersNow()
            .then(() => sendResponse({ ok: true }))
            .catch((e) => sendResponse({ ok: false, error: e?.message || String(e) }));
        return true;
    }
    if (request.action === 'N1_CAPTURE_INVOICE_PAGE_INTERNAL') {
        syncTaobaoInvoicesNow()
            .then(() => sendResponse({ ok: true }))
            .catch((e) => sendResponse({ ok: false, error: e?.message || String(e) }));
        return true;
    }
});

// ============ 全局状态 ============
let isListening = false;
let _clickHandler = null;
let _observer = null; // MutationObserver 实例

// ============ 状态悬浮窗 ============
function showStatus(msg, color = "#FF4D4F") {
    let bar = document.getElementById('n1-status-bar');
    if (!bar) {
        bar = document.createElement('div');
        bar.id = 'n1-status-bar';
        bar.style.cssText = [
            'position:fixed', 'top:0', 'left:0', 'width:100%',
            `background:${color}`, 'color:white', 'padding:12px 20px',
            'z-index:2147483647', 'text-align:center', 'font-size:16px',
            'font-weight:bold', 'box-shadow:0 2px 10px rgba(0,0,0,0.25)',
            'box-sizing:border-box', 'font-family:sans-serif'
        ].join(';');
        document.body.appendChild(bar);
    }
    bar.innerText = msg;
    bar.style.background = color;
}

// ============ 监听来自管理后台的 postMessage ============
window.addEventListener("message", (event) => {
    if (event.data && event.data.action === "N1_START_PURCHASE") {
        const items = event.data.items || [];
        console.log(`🚀 收到采购指令，共 ${items.length} 件商品`);

        if (items.length === 0) {
            showStatus("⚠️ BOM 数据为空", "#F59E0B");
            return;
        }

        showStatus(`🚀 正在开启采购... 共 ${items.length} 件`, "#1890ff");

        chrome.runtime.sendMessage({ action: "init_queue", items: items }, (response) => {
            if (chrome.runtime.lastError) {
                showStatus("⚠️ 插件未响应，请检查扩展是否已启用", "#F59E0B");
                console.error("init_queue 发送失败:", chrome.runtime.lastError.message);
            } else {
                console.log("✅ 已通知 background.js 开始处理");
            }
        });
    }

    if (event.data && event.data.action === "N1_STOP_PURCHASE") {
        showStatus("🛑 已停止本次采购", "#cf1322");
        chrome.runtime.sendMessage({ action: "stop_purchase" }, (response) => {
            if (chrome.runtime.lastError) {
                console.error("stop_purchase 发送失败:", chrome.runtime.lastError.message);
            } else {
                console.log("✅ 已通知 background.js 停止采购");
            }
        });
    }
});

// ============ 填写数量 ============
function fillQuantity(qty) {
    if (qty === 1 || qty === '1') {
        console.log("ℹ️ 数量为1，无需填写");
        return true;
    }

    const selectors = [
        // 淘宝新版（CSS Modules，className 含 countValue）
        'input[class*="countValue"]',
        // 天猫/淘宝通用
        'input.next-input-medium',
        'input.next-input-large',
        // 语义化属性
        'input[aria-label="数量"]',
        'input[name="quantity"]',
        // 容器内
        '.amount-input input',
        '.quantity-input input',
        '[class*="quantity"] input',
        '[class*="count"] input',
        '[class*="num"] input',
        // 淘宝经典
        '#J_EmptyInput',
        'input.tb-text',
        // 通用
        'input[type="number"]',
        'input[min="1"]'
    ];

    console.log(`🔍 查找数量输入框，目标数量：${qty}`);

    let input = null;

    for (const sel of selectors) {
        const el = document.querySelector(sel);
        if (el && el.offsetParent !== null) {
            input = el;
            console.log(`✅ 找到输入框：${sel}，当前值：${el.value}`);
            break;
        }
    }

    if (!input) {
        console.log("⚠️ 精确选择器未命中，尝试智能匹配...");
        const allInputs = document.querySelectorAll('input');
        let bestScore = 0;
        let bestEl = null;

        for (const el of allInputs) {
            if (el.offsetParent === null) continue;
            let score = 0;
            const cls = (typeof el.className === 'string') ? el.className.toLowerCase() : '';
            const id = (el.id || '').toLowerCase();
            const name = (el.name || '').toLowerCase();
            const val = el.value || '';

            if (cls.includes('count') || cls.includes('quantity') || cls.includes('num') ||
                cls.includes('amount') || cls.includes('qty')) score += 3;
            if (id.includes('count') || id.includes('quantity') || id.includes('num')) score += 3;
            if (name.includes('count') || name.includes('quantity') || name.includes('num')) score += 3;
            if (/^\d+$/.test(val)) score += 2;
            if (el.type === 'number') score += 2;
            if (el.type === 'text') score += 1;
            if (el.getAttribute('min') === '1') score += 2;
            const maxLen = parseInt(el.getAttribute('maxlength') || '999');
            if (maxLen <= 4) score += 1;

            if (score > bestScore) {
                bestScore = score;
                bestEl = el;
            }
        }

        if (bestEl && bestScore >= 2) {
            input = bestEl;
            console.log(`✅ 智能匹配到输入框（score=${bestScore}）：${input.className || input.id}`);
        }
    }

    if (!input) {
        console.error("❌ 未找到数量输入框");
        return false;
    }

    try {
        input.focus();
        input.select && input.select();

        const ok = document.execCommand('selectAll', false, null) &&
                   document.execCommand('insertText', false, String(qty));

        if (!ok) {
            console.log("⚠️ execCommand 不可用，降级为键盘模拟");
            simulateTyping(input, String(qty));
        }

        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.blur();

        console.log(`✅ 数量已填写，当前值：${input.value}`);
        return true;
    } catch (e) {
        console.error("❌ 填写数量出错:", e);
        return false;
    }
}

function simulateTyping(input, text) {
    input.value = '';
    for (const char of text) {
        const keyCode = char.charCodeAt(0);
        input.dispatchEvent(new KeyboardEvent('keydown', { key: char, keyCode, bubbles: true }));
        input.dispatchEvent(new KeyboardEvent('keypress', { key: char, keyCode, bubbles: true }));
        input.value += char;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new KeyboardEvent('keyup', { key: char, keyCode, bubbles: true }));
    }
}

// ============ 判断是否为加购成功弹窗 ============
function isSuccessPopup(el) {
    if (!el || el.nodeType !== 1) return false;
    const text = (el.innerText || el.textContent || '').trim();
    const cls = (typeof el.className === 'string') ? el.className : '';

    const hasSuccessText =
        text.includes('加入购物车') ||
        text.includes('已加入') ||
        text.includes('加购成功') ||
        text.includes('成功加入') ||
        text.includes('added to cart') ||
        text.includes('Added to Cart');

    const isPopupLike =
        cls.includes('dialog') || cls.includes('modal') ||
        cls.includes('popup')  || cls.includes('toast') ||
        cls.includes('success')|| cls.includes('notify') ||
        cls.includes('message')|| cls.includes('tips') ||
        cls.includes('overlay')|| cls.includes('layer') ||
        cls.includes('floating')|| cls.includes('panel') ||
        cls.includes('cartSuccess') || cls.includes('cart-success') ||
        cls.includes('addSuccess') || cls.includes('add-success');

    return hasSuccessText && isPopupLike;
}

// ============ 核心流程：先填数量，再等用户点击，再通知下一件 ============
function startListening(targetQty) {
    if (isListening) {
        console.log("⚠️ 已在监听中，忽略重复调用");
        return;
    }
    isListening = true;

    console.log(`🎯 startListening 开始，目标数量：${targetQty}`);

    const tryFill = (attempt = 1) => {
        const filled = fillQuantity(targetQty);

        if (!filled && attempt <= 5) {
            console.log(`⏳ 第 ${attempt} 次尝试填写数量未成功，500ms后重试...`);
            setTimeout(() => tryFill(attempt + 1), 500);
            return;
        }

        if (filled) {
            showStatus(`✅ 数量已设为 ${targetQty}，请点击【加入购物车】按钮`, "#10B981");
        } else {
            showStatus(`⚠️ 未找到数量框（可能默认为1），请点击【加入购物车】按钮`, "#F59E0B");
        }

        startClickListening(targetQty);
    };

    setTimeout(() => tryFill(1), 500);
}

// ============ 监听用户点击加购按钮（事件 + MutationObserver 双保险） ============
// 淘宝加购按钮使用了 stopPropagation，且商品详情页没有购物车角标
// 改用双机制：事件监听（向上遍历父元素）+ MutationObserver 监测加购成功弹窗出现
function startClickListening(targetQty) {
    if (_clickHandler) {
        document.removeEventListener('click', _clickHandler, true);
        _clickHandler = null;
    }
    if (_observer) {
        _observer.disconnect();
        _observer = null;
    }

    let triggered = false;

    function onPurchaseDetected(source) {
        if (triggered) return;
        triggered = true;
        console.log(`🎯 检测到加购操作（来源：${source}）`);

        isListening = false;
        if (_clickHandler) {
            document.removeEventListener('click', _clickHandler, true);
            _clickHandler = null;
        }
        if (_observer) {
            _observer.disconnect();
            _observer = null;
        }

        showStatus("⏳ 加购中，稍候跳转下一件...", "#1890ff");

        setTimeout(() => {
            showStatus("🎉 加购完成！即将跳转下一件...", "#10B981");
            setTimeout(() => {
                chrome.runtime.sendMessage({ action: "purchase_complete" }, (resp) => {
                    if (chrome.runtime.lastError) {
                        console.error("purchase_complete 发送失败:", chrome.runtime.lastError.message);
                    }
                });
            }, 500);
        }, 1500);
    }

    // 机制一：事件监听（向上遍历最多6层父元素）
    _clickHandler = function onShunisClick(e) {
        let el = e.target;
        for (let i = 0; i < 6; i++) {
            if (!el) break;
            const text = (el.innerText || el.textContent || '').trim();
            const cls = (typeof el.className === 'string') ? el.className : '';
            const tag = el.tagName;
            const isBasket = text.includes('加入购物车') ||
                             text.includes('Add to cart') ||
                             text.includes('立即购买');
            const isBtn = tag === 'BUTTON' || tag === 'A' || tag === 'SPAN' ||
                          cls.includes('btn') || cls.includes('button') ||
                          cls.includes('J_LinkBasket') || cls.includes('addCart') ||
                          cls.includes('buy-btn') || cls.includes('purchase');
            if (isBasket && isBtn) {
                onPurchaseDetected('事件监听');
                return;
            }
            el = el.parentElement;
        }
    };
    document.addEventListener('click', _clickHandler, true);

    // 机制二：MutationObserver 监测加购成功弹窗出现
    // 淘宝商品详情页没有购物车角标，改用 MutationObserver 监听 DOM 变化
    // 一旦出现包含"加入购物车"/"已加入"文字的弹窗节点，立即触发跳转
    _observer = new MutationObserver((mutations) => {
        for (const mutation of mutations) {
            for (const node of mutation.addedNodes) {
                if (node.nodeType !== 1) continue;

                // 检查节点本身
                if (isSuccessPopup(node)) {
                    console.log(`🎉 MutationObserver 检测到加购成功弹窗：${node.className}`);
                    onPurchaseDetected('MutationObserver');
                    return;
                }

                // 检查子元素（弹窗可能是嵌套结构）
                try {
                    const children = node.querySelectorAll(
                        '[class*="dialog"],[class*="modal"],[class*="popup"],[class*="toast"],' +
                        '[class*="success"],[class*="notify"],[class*="tips"],[class*="layer"],' +
                        '[class*="floating"],[class*="cartSuccess"],[class*="addSuccess"]'
                    );
                    for (const child of children) {
                        if (isSuccessPopup(child)) {
                            console.log(`🎉 MutationObserver 子元素检测到加购成功弹窗：${child.className}`);
                            onPurchaseDetected('MutationObserver子元素');
                            return;
                        }
                    }
                } catch(e) {}
            }
        }
    });

    _observer.observe(document.body, {
        childList: true,
        subtree: true
    });

    console.log("👂 监听用户点击中（事件+MutationObserver 双保险）...");
}

// ============ 页面加载后主动握手 ============
let _handshakeRetries = 0;
const MAX_HANDSHAKE_RETRIES = 8; // 最多重试 8 次，共约 16 秒

// 判断当前页面是否为淡宝/天猫商品页
// 支持：taobao.com, tmall.com, detail.tmall.com, item.taobao.com 等所有子域名
function isTaobaoOrTmall() {
    const h = location.hostname;
    return h.endsWith('taobao.com') || h.endsWith('tmall.com');
}

function sendContentReady() {
    if (!isTaobaoOrTmall()) {
        return;
    }

    console.log(`🤝 发送 content_ready 握手（第 ${_handshakeRetries + 1} 次）...`);

    chrome.runtime.sendMessage({ action: "content_ready" }, (response) => {
        if (chrome.runtime.lastError) {
            console.log("⚠️ 握手失败，2秒后重试:", chrome.runtime.lastError.message);
            if (_handshakeRetries < MAX_HANDSHAKE_RETRIES) {
                _handshakeRetries++;
                setTimeout(sendContentReady, 2000);
            }
            return;
        }

        if (response && response.action === "start_listening") {
            console.log(`✅ 握手成功，收到 start_listening，数量：${response.quantity}`);
            _handshakeRetries = 0;
            startListening(response.quantity);
        } else {
            // background 回复 idle 可能是因为 openProductTab 回调还没执行
            // 根据 retryAfter 提示重试
            const retryAfter = (response && response.retryAfter) ? response.retryAfter : 3000;
            if (_handshakeRetries < MAX_HANDSHAKE_RETRIES) {
                console.log(`ℹ️ 收到 idle，${retryAfter}ms 后重试握手（第 ${_handshakeRetries + 1} 次）`);
                _handshakeRetries++;
                setTimeout(sendContentReady, retryAfter);
            } else {
                console.log("ℹ️ 握手重试达到上限，当前页面无待处理任务");
            }
        }
    });
}

// ============ 监听来自 background 的推送（兼容备用） ============
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === 'PING') {
        sendResponse({ ok: true, host: location.hostname });
        return true;
    }
    if (request.action === "start_listening") {
        startListening(request.quantity);
        sendResponse({ ok: true });
    }
    if (request.action === 'N1_CAPTURE_TAOBAO_ORDERS_INTERNAL') {
        syncTaobaoOrdersNow().then(() => sendResponse({ ok: true })).catch(err => sendResponse({ ok: false, error: err.message }));
        return true;
    }
    if (request.action === 'N1_CAPTURE_INVOICE_PAGE_INTERNAL') {
        syncTaobaoInvoicesNow().then(() => sendResponse({ ok: true })).catch(err => sendResponse({ ok: false, error: err.message }));
        return true;
    }
    return true;
});

// ============ 页面就绪时握手 ============
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        console.log("📄 DOM 已加载，插件已就绪");
        setTimeout(sendContentReady, 1500);
    });
} else {
    console.log("📄 DOM 已加载，插件已就绪");
    setTimeout(sendContentReady, 1500);
}
