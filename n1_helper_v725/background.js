// N+1 LAB 采购助手 v7.2 - Background Service Worker
//
// 架构重构：
//   - 彻底废弃 tabs.onUpdated 发送 start_listening 的方式（时序不可靠）
//   - 改为 content.js 加载后主动发送 "content_ready" 握手，background 再回复 start_listening
//   - currentTabId 持久化到 storage，防止 Service Worker 休眠后丢失
//   - 只在 background.js 维护队列，content.js 只负责执行单次加购

console.log("🦐 N+1 采购助手 v7.2 Background 已启动");

let purchaseQueue = [];
let currentIndex = 0;
let currentTabId = null;

// ============ 启动时从存储恢复全部状态 ============
chrome.storage.local.get(['queue', 'currentIndex', 'currentTabId'], (result) => {
    if (result.queue && result.queue.length > 0) {
        purchaseQueue = result.queue;
        currentIndex = result.currentIndex || 0;
        currentTabId = result.currentTabId || null;
        console.log(`🔄 从存储恢复：${purchaseQueue.length} 件商品，当前第 ${currentIndex} 件，tabId=${currentTabId}`);
    }
});

// ============ 持久化全部状态 ============
function saveState() {
    chrome.storage.local.set({
        queue: purchaseQueue,
        currentIndex: currentIndex,
        currentTabId: currentTabId
    });
}

// ============ 消息监听 ============
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("📨 收到消息:", request.action, "| from tab:", sender.tab ? sender.tab.id : "non-tab");

    // ── 1. 初始化队列（来自管理后台的 content.js 转发） ──
    if (request.action === "init_queue") {
        purchaseQueue = request.items || [];
        currentIndex = 0;
        currentTabId = null;
        console.log(`✅ 队列初始化：${purchaseQueue.length} 件商品`);
        saveState();
        if (purchaseQueue.length > 0) {
            processNext();
        }
        sendResponse({ ok: true });
    }

    // ── 2. content.js 加载完成后主动握手 ──
    // 这是新架构的核心：不依赖 tabs.onUpdated 的时序，而是等 content.js 自己说"我准备好了"
    else if (request.action === "content_ready") {
        const tabId = sender.tab ? sender.tab.id : null;
        console.log(`🤝 content_ready from tabId=${tabId}, currentTabId=${currentTabId}`);

        if (tabId && tabId === currentTabId && currentIndex > 0 && currentIndex <= purchaseQueue.length) {
            const currentItem = purchaseQueue[currentIndex - 1];
            console.log(`📤 发送 start_listening: quantity=${currentItem.quantity} → tabId=${tabId}`);
            sendResponse({ action: "start_listening", quantity: currentItem.quantity });
        } else {
            sendResponse({ action: "idle" });
        }
    }

    // ── 3. 当前商品加购完成 ──
    else if (request.action === "purchase_complete") {
        const completedIndex = currentIndex - 1;
        console.log(`✅ 第 ${completedIndex + 1}/${purchaseQueue.length} 件完成`);

        // 关闭当前标签页
        if (sender.tab && sender.tab.id) {
            chrome.tabs.remove(sender.tab.id, () => {
                if (chrome.runtime.lastError) {
                    console.log("⚠️ 关闭标签页出错:", chrome.runtime.lastError.message);
                }
            });
        }

        // 延迟后处理下一件
        setTimeout(() => {
            processNext();
        }, 1500);

        sendResponse({ ok: true });
    }

    // ── 4. 查询状态 ──
    else if (request.action === "get_status") {
        sendResponse({
            queueLength: purchaseQueue.length,
            currentIndex: currentIndex,
            remaining: purchaseQueue.length - currentIndex
        });
    }

    return true; // 保持异步通道
});

// ============ 打开商品页面 ============
function openProductTab(url) {
    console.log(`🔗 打开商品页面：${url}`);
    chrome.tabs.create({ url: url, active: true }, (tab) => {
        if (chrome.runtime.lastError) {
            console.error("❌ 打开标签页失败:", chrome.runtime.lastError.message);
            return;
        }
        currentTabId = tab.id;
        saveState(); // 立即持久化 tabId，防止 SW 休眠后丢失
        console.log(`✅ 标签页已打开：tabId=${tab.id}`);
    });
}

// ============ 处理下一件商品 ============
function processNext() {
    if (currentIndex >= purchaseQueue.length) {
        console.log("🎉 所有商品处理完成！");
        chrome.storage.local.remove(['queue', 'currentIndex', 'currentTabId']);
        currentTabId = null;
        return;
    }

    const item = purchaseQueue[currentIndex];
    console.log(`📦 处理第 ${currentIndex + 1}/${purchaseQueue.length} 件：${item.link}`);

    currentIndex++; // 先递增，tabs 加载完后用 currentIndex-1 取商品
    saveState();

    openProductTab(item.link);
}

// ============ 扩展安装/更新 ============
chrome.runtime.onInstalled.addListener(() => {
    console.log("🎉 扩展已安装/更新 v7.2");
});

self.addEventListener('activate', () => {
    console.log("🚀 Service Worker 激活");
});
