// N+1 LAB 采购助手 v7.0 - 人机协作版
// 工作流程：管理后台点击 → 自动打开淘宝 → Shuni 点击 1 次加购 → 插件自动填数量 → 自动下一个

console.log("🦐 N+1 采购助手 v7.0 已加载");

// ============ 全局状态 ============
let purchaseQueue = [];
let currentIndex = 0;
let isListening = false;

// ============ 状态悬浮窗 ============
function showStatus(msg, color = "#FF4D4F") {
    let bar = document.getElementById('n1-status-bar');
    if (!bar) {
        bar = document.createElement('div');
        bar.id = 'n1-status-bar';
        bar.style.cssText = `position:fixed; top:0; left:0; width:100%; background:${color}; color:white; padding:15px; z-index:999999; text-align:center; font-size:18px; font-weight:bold; box-shadow:0 2px 10px rgba(0,0,0,0.2);`;
        document.body.appendChild(bar);
    }
    bar.innerText = msg;
    bar.style.background = color;
}

// ============ 监听管理后台的 postMessage ============
window.addEventListener("message", (event) => {
    if (event.data && event.data.action === "N1_START_PURCHASE") {
        const items = event.data.items || [];
        console.log(`🚀 收到协作采购指令，共 ${items.length} 件商品`);
        
        if (items.length === 0) {
            showStatus("⚠️ BOM 数据为空", "#F59E0B");
            return;
        }
        
        showStatus(`🚀 正在开启采购... 共 ${items.length} 件`, "#FF4D4F");
        
        // 转发给 background.js
        chrome.runtime.sendMessage({ 
            action: "init_queue", 
            items: items 
        }, (response) => {
            if (chrome.runtime.lastError) {
                showStatus("⚠️ 插件未响应，请检查扩展是否启用", "#F59E0B");
                console.error("消息发送失败:", chrome.runtime.lastError);
            } else {
                console.log("✅ 已通知 background.js 开始处理");
            }
        });
    }
});

// ============ 自动填写数量 ============
function fillQuantity(qty) {
    const selectors = [
        // 天猫/淘宝通用
        'input.next-input-medium',
        'input.next-input-large',
        // 数量输入框常见选择器
        'input[aria-label="数量"]',
        'input[name="quantity"]',
        '.amount-input input',
        '.quantity-input input',
        // 淘宝经典
        '#J_EmptyInput',
        'input.tb-text',
        // 通用 input[type=number]
        'input[type="number"]',
        // 宽泛匹配
        'input[value="1"]',
        'input[min="1"]'
    ];
    
    console.log("🔍 开始查找数量输入框...");
    
    for (const sel of selectors) {
        const input = document.querySelector(sel);
        if (input) {
            console.log(`✅ 找到输入框：${sel}`);
            input.value = qty;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            input.focus();
            input.blur();
            console.log(`✅ 已填入数量：${qty}`);
            return true;
        }
    }
    
    // 备用方案：查找所有 input，尝试匹配
    console.log("⚠️ 标准选择器未找到，尝试模糊匹配...");
    const allInputs = document.querySelectorAll('input');
    for (const input of allInputs) {
        const val = input.value || input.getAttribute('value') || '';
        if (val === '1' || input.type === 'number' || input.className.includes('quantity')) {
            console.log(`✅ 模糊匹配到输入框：${input.className || input.id}`);
            input.value = qty;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        }
    }
    
    console.error("❌ 未找到数量输入框");
    return false;
}

// ============ 点击确认按钮 ============
function clickConfirm() {
    const buttons = Array.from(document.querySelectorAll('button, .btn, span')).filter(el => {
        const text = (el.innerText || el.textContent || "").trim();
        return text === "确定" || text === "确认" || text.includes("加入购物车");
    });
    
    if (buttons.length > 0) {
        buttons[0].click();
        console.log("✅ 已点击确认按钮");
        return true;
    }
    return false;
}

// ============ 处理加购流程 ============
function handlePurchase(qty) {
    showStatus("✅ 收到！正在自动填写数量...", "#10B981");
    
    setTimeout(() => {
        const filled = fillQuantity(qty);
        if (!filled) {
            showStatus("⚠️ 未找到数量输入框，请手动填写", "#F59E0B");
            return;
        }
        
        setTimeout(() => {
            const clicked = clickConfirm();
            if (!clicked) {
                showStatus("⚠️ 未找到确认按钮，请手动点击", "#F59E0B");
                return;
            }
            
            showStatus("🎉 加购成功！准备下一个...", "#10B981");
            
            setTimeout(() => {
                // 通知 background.js 关闭当前页并打开下一个
                chrome.runtime.sendMessage({ 
                    action: "purchase_complete",
                    index: currentIndex,
                    total: purchaseQueue.length
                });
            }, 1500);
        }, 800);
    }, 500);
}

// ============ 监听 Shuni 的点击 ============
function startListening(targetQty) {
    if (isListening) return;
    isListening = true;
    
    showStatus(`🤖 助手待命，请 Shuni 点击【加入购物车】按钮 (目标数量：${targetQty})`, "#FF4D4F");
    
    console.log("👂 开始监听点击事件...");
    
    // 使用捕获阶段监听所有点击
    document.addEventListener('click', (e) => {
        const target = e.target;
        const text = (target.innerText || target.textContent || "").trim();
        const tagName = target.tagName;
        const className = target.className || "";
        const id = target.id || "";
        
        console.log(`🖱️ 检测到点击：tagName=${tagName}, text="${text}", class="${className}", id="${id}"`);
        
        // 检测加购按钮（多种文本匹配）
        const isBasketBtn = text.includes("加入购物车") || 
                           text.includes("加入购物车") ||
                           text.includes("Add to cart") || 
                           text.includes("Add to Cart") ||
                           text.includes("收藏") ||
                           text.includes("立即购买");
        
        // 检测确定按钮（弹窗中的）
        const isConfirmBtn = text === "确定" || 
                            text === "确认" || 
                            text === "OK" ||
                            text.includes("确认购买");
        
        // 检测按钮样式（天猫/淘宝常见按钮类名）
        const isButtonStyle = className.includes("btn") || 
                             className.includes("button") ||
                             className.includes("J_LinkBasket") ||
                             target.classList.contains("tb-button");
        
        console.log(`🔍 匹配结果：isBasketBtn=${isBasketBtn}, isConfirmBtn=${isConfirmBtn}, isButtonStyle=${isButtonStyle}`);
        
        // 放宽条件：只要是按钮且文本匹配
        if ((isBasketBtn || isConfirmBtn) && (tagName === "BUTTON" || tagName === "SPAN" || tagName === "A" || isButtonStyle)) {
            console.log("🎯 检测到 Shuni 点击，接管后续操作...");
            
            // 停止监听，防止重复触发
            isListening = false;
            
            handlePurchase(targetQty);
        }
    }, true); // 捕获阶段监听
}

// ============ 初始化采购流程 ============
function startPurchase(items) {
    purchaseQueue = items;
    currentIndex = 0;
    console.log(`🚀 开始采购，共 ${items.length} 件商品`);
    processNext();
}

// ============ 处理下一个商品 ============
function processNext() {
    if (currentIndex >= purchaseQueue.length) {
        showStatus("✅ 全部完成！共加购 " + purchaseQueue.length + " 件商品", "#10B981");
        setTimeout(() => {
            const bar = document.getElementById('n1-status-bar');
            if (bar) bar.remove();
        }, 5000);
        return;
    }
    
    const item = purchaseQueue[currentIndex];
    currentIndex++;
    
    showStatus(`🤖 第 ${currentIndex}/${purchaseQueue.length} 件 - 正在打开商品页面...`, "#FF4D4F");
    
    // 打开新标签页
    chrome.runtime.sendMessage({
        action: "open_tab",
        url: item.link,
        quantity: item.quantity
    });
}

// ============ 监听来自 background 的消息 ============
chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
    if (request.action === "start_purchase") {
        // 从管理后台启动
        const items = request.items || purchaseQueue;
        if (items.length === 0) {
            showStatus("⚠️ 未找到 BOM 数据，请检查页面", "#F59E0B");
            return;
        }
        startPurchase(items);
    } else if (request.action === "start_listening") {
        // 在当前页面开始监听
        startListening(request.quantity);
    }
    sendResponse({ ok: true });
});

// ============ 页面加载完成时 ============
window.addEventListener('load', () => {
    // 检查是否是淘宝/天猫页面
    if (location.hostname.includes('taobao.com') || location.hostname.includes('tmall.com')) {
        console.log("🛒 检测到淘宝/天猫页面，准备接收指令");
        // 等待 background.js 发送指令
    }
});

// 页面 DOM 加载完成后立即注入脚本
if (document.readyState === 'interactive' || document.readyState === 'complete') {
    console.log("📄 DOM 已加载，插件已就绪");
}
