// N+1 LAB 采购助手 v7.4 - Background Service Worker
//
// v7.4 全面修复所有 URL 匹配相关问题：
//
// 问题一（已修复 v7.3.1）：URL 兜底匹配用路径 /item.htm 匹配，
//   导致任何商品页都命中，改为用商品 ID 参数精确匹配。
//
// 问题二（本版新增）：purchase_complete 收到后关闭标签页，
//   但 processNext() 打开下一个 tab 前没有清理 currentTabId，
//   如果下一件商品与上一件 ID 相同（重复采购同款），
//   tabIdMatch 会误命中旧 tabId，导致逻辑混乱。
//   修复：processNext() 前先将 currentTabId 置 null。
//
// 问题三（本版新增）：SW 从休眠恢复后，storage 读取是异步的，
//   如果 content_ready 在 storage 读取完成前到达，
//   purchaseQueue 为空，currentIndex 为 0，条件不满足，回复 idle。
//   修复：将 storage 恢复逻辑封装为 Promise，
//   content_ready 处理时等待 storage 恢复完成再判断。
//
// 问题四（本版新增）：tabs.onRemoved 没有监听，
//   如果用户手动关闭了商品标签页，流程会永久卡死。
//   修复：监听 tabs.onRemoved，如果关闭的是 currentTabId，
//   自动推进到下一件。

console.log("🦐 N+1 采购助手 v7.4 Background 已启动");

// ============ 从 URL 中提取商品唯一标识（id 参数） ============
// 同时支持淘宝（?id=xxx）和天猫（?id=xxx&skuId=xxx）格式
function extractItemId(url) {
    if (!url) return null;
    try {
        const u = new URL(url);
        return u.searchParams.get('id') || u.searchParams.get('itemId') || null;
    } catch(e) {
        const m = url.match(/[?&]id=([^&]+)/);
        return m ? m[1] : null;
    }
}

// ============ 判断两个 URL 是否指向同一件商品 ============
function isSameProduct(urlA, urlB) {
    if (!urlA || !urlB) return false;
    const idA = extractItemId(urlA);
    const idB = extractItemId(urlB);
    if (idA && idB) return idA === idB;
    // 如果没有 id 参数，降级为去掉 query string 后的路径比较
    try {
        const a = new URL(urlA);
        const b = new URL(urlB);
        return a.hostname === b.hostname && a.pathname === b.pathname;
    } catch(e) {
        return false;
    }
}

// ============ 全局状态 ============
let purchaseQueue = [];
let currentIndex = 0;
let currentTabId = null;
let pendingTabUrl = null; // 正在等待打开的商品 URL（用于 URL 兜底匹配）
let stateReady = false;   // storage 恢复是否完成

// ============ 启动时从存储恢复全部状态 ============
const stateReadyPromise = new Promise((resolve) => {
    chrome.storage.local.get(['queue', 'currentIndex', 'currentTabId', 'pendingTabUrl'], (result) => {
        if (result.queue && result.queue.length > 0) {
            purchaseQueue = result.queue;
            currentIndex = result.currentIndex || 0;
            currentTabId = result.currentTabId || null;
            pendingTabUrl = result.pendingTabUrl || null;
            console.log(`🔄 从存储恢复：${purchaseQueue.length} 件商品，当前第 ${currentIndex} 件，tabId=${currentTabId}`);
        }
        stateReady = true;
        resolve();
    });
});

// ============ 持久化全部状态 ============
function saveState() {
    chrome.storage.local.set({
        queue: purchaseQueue,
        currentIndex: currentIndex,
        currentTabId: currentTabId,
        pendingTabUrl: pendingTabUrl
    });
}

// ============ 消息监听 ============
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("📨 收到消息:", request.action, "| from tab:", sender.tab ? sender.tab.id : "non-tab");

    // ── 1. 初始化队列 ──
    if (request.action === "init_queue") {
        purchaseQueue = request.items || [];
        currentIndex = 0;
        currentTabId = null;
        pendingTabUrl = null;
        stateReady = true;
        console.log(`✅ 队列初始化：${purchaseQueue.length} 件商品`);
        saveState();
        if (purchaseQueue.length > 0) {
            processNext();
        }
        sendResponse({ ok: true });
    }

    // ── 2. content.js 加载完成后主动握手 ──
    else if (request.action === "content_ready") {
        // 等待 storage 恢复完成再处理（解决 SW 休眠后 storage 异步读取问题）
        stateReadyPromise.then(() => {
            const tabId = sender.tab ? sender.tab.id : null;
            const tabUrl = sender.tab ? sender.tab.url : null;
            console.log(`🤝 content_ready from tabId=${tabId}, currentTabId=${currentTabId}, pendingTabUrl=${pendingTabUrl}`);

            // 正常匹配：tabId 与 currentTabId 一致
            const tabIdMatch = tabId && tabId === currentTabId;

            // 兜底匹配：openProductTab 回调还没执行（currentTabId 还没更新）
            // 用商品 ID 精确匹配，避免路径匹配把所有商品页都当成目标页
            const urlMatch = !tabIdMatch && tabId && isSameProduct(pendingTabUrl, tabUrl);

            if ((tabIdMatch || urlMatch) && currentIndex >= 1 && currentIndex <= purchaseQueue.length) {
                if (urlMatch) {
                    console.log(`🔧 URL 兜底匹配（商品ID相同），更新 currentTabId: ${currentTabId} → ${tabId}`);
                    currentTabId = tabId;
                    saveState();
                }

                const currentItem = purchaseQueue[currentIndex - 1];
                console.log(`📤 发送 start_listening: quantity=${currentItem.quantity} → tabId=${tabId}`);
                sendResponse({ action: "start_listening", quantity: currentItem.quantity });
            } else {
                console.log(`⏳ 握手条件不满足（tabId=${tabId}, currentTabId=${currentTabId}, index=${currentIndex}/${purchaseQueue.length}），回复 idle`);
                sendResponse({ action: "idle", retryAfter: 2000 });
            }
        });
        return true; // 必须 return true 才能在 Promise 回调中调用 sendResponse
    }

    // ── 3. 当前商品加购完成 ──
    else if (request.action === "purchase_complete") {
        const completedIndex = currentIndex - 1;
        console.log(`✅ 第 ${completedIndex + 1}/${purchaseQueue.length} 件完成`);

        const completedTabId = sender.tab ? sender.tab.id : null;
        pendingTabUrl = null;
        currentTabId = null; // 清空，防止下一件同款商品误命中
        saveState();

        // 关闭当前标签页
        if (completedTabId) {
            chrome.tabs.remove(completedTabId, () => {
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

// ============ 监听标签页被关闭（防止用户手动关闭导致流程卡死） ============
chrome.tabs.onRemoved.addListener((tabId) => {
    if (tabId === currentTabId) {
        console.log(`⚠️ 当前商品标签页被手动关闭（tabId=${tabId}），自动推进到下一件`);
        currentTabId = null;
        pendingTabUrl = null;
        saveState();
        setTimeout(() => {
            processNext();
        }, 1000);
    }
});

// ============ 打开商品页面 ============
function openProductTab(url) {
    console.log(`🔗 打开商品页面：${url}`);
    pendingTabUrl = url; // 先记录 URL，用于 content_ready 的 URL 兜底匹配
    currentTabId = null; // 清空旧 tabId，防止误匹配
    saveState();

    chrome.tabs.create({ url: url, active: true }, (tab) => {
        if (chrome.runtime.lastError) {
            console.error("❌ 打开标签页失败:", chrome.runtime.lastError.message);
            pendingTabUrl = null;
            saveState();
            return;
        }
        currentTabId = tab.id;
        saveState(); // 立即持久化 tabId
        console.log(`✅ 标签页已打开：tabId=${tab.id}`);
    });
}

// ============ 处理下一件商品 ============
function processNext() {
    if (currentIndex >= purchaseQueue.length) {
        console.log("🎉 所有商品处理完成！");
        chrome.storage.local.remove(['queue', 'currentIndex', 'currentTabId', 'pendingTabUrl']);
        currentTabId = null;
        pendingTabUrl = null;
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
    console.log("🎉 扩展已安装/更新 v7.4");
});

self.addEventListener('activate', () => {
    console.log("🚀 Service Worker 激活");
});
