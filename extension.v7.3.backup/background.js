// N+1 LAB 采购助手 v6.0 - 终极核能版 (Background Script)

let purchaseQueue = [];
let currentTabId = null;
let isProcessing = false;

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    console.log('[BG v6.0] 收到消息:', message.type);
    
    if (message.type === 'START_PURCHASE_QUEUE') {
        purchaseQueue = message.links;
        isProcessing = true;
        processNext();
    }
    
    if (message.type === 'ITEM_ADDED' || message.type === 'SKIP_ITEM') {
        // 先移除当前标签页
        if (sender.tab && sender.tab.id) {
            chrome.tabs.remove(sender.tab.id, () => {
                if (chrome.runtime.lastError) console.warn('移除标签页提示:', chrome.runtime.lastError.message);
                // 无论是否成功移除，都触发下一个
                processNext();
            });
        } else {
            processNext();
        }
    }
});

// 安全保底：如果用户手动关闭了标签页，也尝试触发下一个
chrome.tabs.onRemoved.addListener((tabId) => {
    if (tabId === currentTabId && isProcessing) {
        console.log('[BG] 监测到目标标签页关闭，触发保底跳转');
        currentTabId = null;
        // 稍微等一下，防止点击过快
        setTimeout(() => {
            if (isProcessing) processNext();
        }, 1000);
    }
});

function processNext() {
    if (!isProcessing) return;
    
    // 如果已经在队列中并且没有结束，继续下一个
    if (purchaseQueue.length === 0) {
        isProcessing = false;
        console.log('✅ 任务全部结束');
        return;
    }
    
    const nextLink = purchaseQueue.shift();
    console.log('🚀 准备开启:', nextLink);
    
    chrome.tabs.create({ url: nextLink }, (tab) => {
        currentTabId = tab.id;
    });
}
