// N+1 LAB 采购助手 v7.0 - Background Service Worker
// 负责队列管理和标签页控制

console.log("🦐 N+1 采购助手 v7.0 Background 已启动");

let purchaseQueue = [];
let currentIndex = 0;
let currentTabId = null;

// ============ 监听来自 content.js 的消息 ============
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    console.log("📨 收到消息:", request.action, "from:", sender.tab ? "tab" : "popup");
    
    if (request.action === "init_queue") {
        // 初始化队列（从管理后台）
        purchaseQueue = request.items || [];
        currentIndex = 0;
        console.log(`✅ 队列初始化：${purchaseQueue.length} 件商品`);
        
        if (purchaseQueue.length > 0) {
            processNext();
        }
        sendResponse({ ok: true });
    }
    else if (request.action === "purchase_complete") {
        // 当前商品加购完成
        console.log(`✅ 第 ${currentIndex + 1}/${purchaseQueue.length} 件完成`);
        
        // 关闭当前标签页
        if (sender.tab && sender.tab.id) {
            chrome.tabs.remove(sender.tab.id, () => {
                console.log("✅ 已关闭当前标签页");
                // 关闭后立即打开下一个（不要 setTimeout，防止 Service Worker 休眠）
                openNext();
            });
        } else {
            // 如果没有 sender.tab，直接打开下一个
            openNext();
        }
        
        sendResponse({ ok: true });
    }
    else if (request.action === "get_status") {
        // 获取当前状态
        sendResponse({ 
            queueLength: purchaseQueue.length, 
            currentIndex: currentIndex,
            remaining: purchaseQueue.length - currentIndex
        });
    }
    
    return true; // 保持消息通道开放
});

// ============ 监听页面加载完成 ============
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
    if (changeInfo.status === 'complete' && tab.url && 
        (tab.url.includes('taobao.com') || tab.url.includes('tmall.com'))) {
        console.log(`🛒 淘宝页面加载完成：tabId=${tabId}`);
        // 不再在这里发送指令，由 openProductTab 直接处理
    }
});

// ============ 打开商品页面 ============
function openProductTab(url, quantity) {
    console.log(`🔗 打开商品：${url} (数量：${quantity})`);
    
    chrome.tabs.create({ url: url, active: true }, (tab) => {
        if (chrome.runtime.lastError) {
            console.error("❌ 打开标签页失败:", chrome.runtime.lastError.message);
            return;
        }
        
        currentTabId = tab.id;
        console.log(`✅ 标签页已打开：tabId=${tab.id}`);
        
        // 等待 3 秒确保页面完全加载后直接发送指令
        setTimeout(() => {
            console.log(`📤 发送 start_listening 到 tabId=${tab.id}, quantity=${quantity}`);
            chrome.tabs.sendMessage(tab.id, {
                action: "start_listening",
                quantity: quantity
            }, (response) => {
                if (chrome.runtime.lastError) {
                    console.log("⚠️ 消息发送失败:", chrome.runtime.lastError.message);
                } else {
                    console.log("✅ 已通知 content.js 开始监听点击");
                }
            });
        }, 3000);
    });
}

// ============ 处理下一个商品 ============
function processNext() {
    if (currentIndex >= purchaseQueue.length) {
        console.log("✅ 所有商品处理完成！");
        return;
    }
    
    const item = purchaseQueue[currentIndex];
    console.log(`📦 处理第 ${currentIndex + 1}/${purchaseQueue.length} 件：${item.link}`);
    
    openProductTab(item.link, item.quantity);
}

// ============ 打开下一个商品（递增索引后调用） ============
function openNext() {
    currentIndex++;
    processNext();
}

// ============ 扩展安装/更新时 ============
chrome.runtime.onInstalled.addListener(() => {
    console.log("🎉 扩展已安装/更新");
});
