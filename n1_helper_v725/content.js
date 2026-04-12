// N+1 LAB 采购助手 v7.2.4 - Content Script
//
// v7.2.4 核心修复：
//   将"购物车数量轮询"改为"MutationObserver 监测加购成功弹窗"
//   根本原因：淘宝商品详情页根本没有购物车角标 DOM 元素，
//   getCartCount() 始终返回 -1，轮询条件永远不成立。
//   新方案：用 MutationObserver 监听 document.body 的子树变化，
//   一旦出现包含"加入购物车"/"已加入"文字的弹窗节点，立即触发跳转。
//   这个方案完全不依赖购物车角标，也不受 stopPropagation 影响。

console.log("🦐 N+1 采购助手 v7.2.4 已加载");

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
function sendContentReady() {
    if (!location.hostname.includes('taobao.com') && !location.hostname.includes('tmall.com')) {
        return;
    }

    console.log("🤝 发送 content_ready 握手...");

    chrome.runtime.sendMessage({ action: "content_ready" }, (response) => {
        if (chrome.runtime.lastError) {
            console.log("⚠️ 握手失败，2秒后重试:", chrome.runtime.lastError.message);
            setTimeout(sendContentReady, 2000);
            return;
        }

        if (response && response.action === "start_listening") {
            console.log(`✅ 握手成功，收到 start_listening，数量：${response.quantity}`);
            startListening(response.quantity);
        } else {
            console.log("ℹ️ 握手成功，当前无待处理任务");
        }
    });
}

// ============ 监听来自 background 的推送（兼容备用） ============
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "start_listening") {
        startListening(request.quantity);
        sendResponse({ ok: true });
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
