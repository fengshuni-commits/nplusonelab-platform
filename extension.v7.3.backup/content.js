// N+1 LAB 采购助手 v6.8 - 智能重试增强版 (Smart Retry Enhanced)
// 修复重点：解决第三件及之后商品加购失败问题
// 核心改进：
// 1. 多策略元素查找（选择器 -> XPath -> 文本 -> iframe）
// 2. 智能等待机制（MutationObserver + 轮询）
// 3. 增强重试逻辑（指数退避 + 页面状态重置）
// 4. 详细日志记录（便于调试定位问题）

// A: 管理后台逻辑
if (window.location.host.includes('43.156.225.39') || window.location.host.includes('localhost') || window.location.host.includes('8080')) {
    console.log('🦐 N+1 采购助手 v7.2 已激活 [支持多件采购]');
    const observer = new MutationObserver(() => {
        const bomModal = document.getElementById('bom-modal');
        if (bomModal && bomModal.style.display === 'block' && !document.getElementById('batch-add-btn')) {
            // 创建数量输入框
            const inputDiv = document.createElement('div');
            inputDiv.style = 'margin-top:15px; padding:12px; background:#f5f5f5; border-radius:8px; display:flex; align-items:center; gap:10px;';
            inputDiv.innerHTML = `
                <label style="font-weight:bold; color:#262626;">🛒 采购数量:</label>
                <input type="number" id="n1-purchase-qty" value="1" min="1" max="99" 
                    style="width:80px; padding:8px; border:1px solid #d9d9d9; border-radius:4px; font-size:14px; text-align:center;" />
                <span style="color:#8c8c8c; font-size:13px;">(1-99 件)</span>
            `;
            
            // 创建采购按钮
            const btn = document.createElement('button');
            btn.id = 'batch-add-btn';
            btn.innerHTML = '🚀 开启全自动采购 (v7.2 多件版)';
            btn.style = 'width:100%; margin-top:10px; padding:15px; background:#f5222d; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold; font-size:16px; box-shadow:0 6px 20px rgba(245,34,45,0.5);';
            btn.onclick = () => {
                const qtyInput = document.getElementById('n1-purchase-qty');
                const purchaseQty = parseInt(qtyInput.value) || 1;
                
                const links = Array.from(document.querySelectorAll('#bom-body a')).map(a => a.href);
                if (links.length === 0) return alert('没找到采购链接');
                
                // 生成带数量的链接队列
                const linksWithQty = links.flatMap(link => {
                    return Array(purchaseQty).fill(link);
                });
                
                if (confirm(`准备开启全自动加购\n\n📦 产品数量：${purchaseQty} 件\n🔗 零件总数：${linksWithQty.length} 个\n\nv7.2 新功能：\n1. 支持多件产品采购\n2. 自动重复采购流程\n3. 智能重试机制`)) {
                    chrome.runtime.sendMessage({ 
                        type: 'START_PURCHASE_QUEUE', 
                        links: linksWithQty 
                    });
                }
            };
            
            // 插入到页面
            bomModal.insertBefore(inputDiv, bomModal.querySelector('button'));
            bomModal.insertBefore(btn, bomModal.querySelector('button'));
        }
    });
    observer.observe(document.body, { childList: true, subtree: true });
}

// B: 淘宝/天猫页面逻辑
if (window.location.search.includes('n1_auto_add=1')) {
    const urlParams = new URLSearchParams(window.location.search);
    const targetQty = parseInt(urlParams.get('n1_qty') || "1");
    const startTime = Date.now();
    const TIMEOUT_MS = 25000; // 25 秒超时（增加 5 秒）
    let isDone = false;
    let retryCount = 0;
    const MAX_RETRIES = 8; // 最大重试次数
    
    console.log(`🦐 N+1 自动化 v6.8 启动 | 目标数量：${targetQty} | 超时：${TIMEOUT_MS}ms`);
    
    // 创建状态悬浮窗
    const statusBox = document.createElement('div');
    statusBox.id = 'n1-status-box';
    statusBox.style = 'position:fixed; top:20px; right:20px; background:rgba(0,0,0,0.95); color:#52c41a; padding:22px; border-radius:16px; z-index:2147483647; font-size:16px; border:2px solid #52c41a; line-height:1.6; min-width:320px; box-shadow:0 15px 50px rgba(0,0,0,0.9);';
    statusBox.innerHTML = `
        <div style="font-weight:bold; border-bottom:1px solid #52c41a44; margin-bottom:12px; padding-bottom:10px;">🦐 小虾虾 v6.8 [智能重试版]</div>
        <div id="n1-status">🚀 正在初始化...</div>
        <div id="n1-sub" style="font-size:12px; color:#aaa; margin-top:5px;">等待页面加载</div>
        <div id="n1-retry" style="font-size:11px; color:#fa8c16; margin-top:5px;">重试：0/${MAX_RETRIES}</div>
        <div style="display:flex; gap:10px; margin-top:15px;">
            <button id="n1-done-btn" style="flex:1; padding:10px; background:#52c41a; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold;">成功，继续</button>
            <button id="n1-skip-btn" style="flex:1; padding:10px; background:#fa8c16; color:white; border:none; border-radius:6px; cursor:pointer; font-weight:bold;">跳过此件</button>
        </div>
    `;
    document.body.appendChild(statusBox);

    const log = (t) => {
        const el = document.getElementById('n1-status');
        if (el) el.innerText = t;
        console.log(`[N1 v6.8] ${t}`);
    };
    
    const sub = (t) => {
        const el = document.getElementById('n1-sub');
        if (el) el.innerText = t;
        console.log(`[N1 v6.8] ${t}`);
    };
    
    const updateRetry = (count) => {
        const el = document.getElementById('n1-retry');
        if (el) el.innerText = `重试：${count}/${MAX_RETRIES}`;
    };
    
    document.getElementById('n1-done-btn').onclick = () => {
        console.log('[N1 v6.8] 用户手动确认成功');
        chrome.runtime.sendMessage({ type: 'ITEM_ADDED' });
    };
    document.getElementById('n1-skip-btn').onclick = () => {
        console.log('[N1 v6.8] 用户手动跳过');
        chrome.runtime.sendMessage({ type: 'SKIP_ITEM' });
    };

    // 模拟点击（增强版）
    const simulateClick = (el) => {
        try {
            console.log('[simulateClick] 开始模拟点击', el);
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            
            // 触发完整的事件序列
            const events = ['mouseenter', 'mouseover', 'mousedown', 'mouseup', 'click'];
            events.forEach(name => {
                const event = new MouseEvent(name, { 
                    bubbles: true, 
                    cancelable: true, 
                    view: window,
                    clientX: 1,
                    clientY: 1
                });
                el.dispatchEvent(event);
            });
            
            // 额外触发 focus 事件（某些按钮需要）
            if (typeof el.focus === 'function') {
                el.focus();
            }
            
            console.log('[simulateClick] 点击事件发送完成');
            return true;
        } catch(e) {
            console.error('[simulateClick] 错误:', e);
            return false;
        }
    };

    // 检查成功状态（增强版）
    const checkSuccess = () => {
        // 1. 检查成功弹窗/提示
        const successSelectors = [
            '.msg-success', '.cart-success', '.tb-success', '.success-toast',
            '[class*="success"]', '.J_SuccessTip', '.J_TipSuccess', '.tip-success',
            '.add-to-cart-success', '.mui-toast-success', '.tb-icon-success',
            '.sui-toast-success', '.ant-message-success', '.toast-success'
        ];
        
        for (const s of successSelectors) {
            const el = document.querySelector(s);
            if (el) {
                console.log('[checkSuccess] 找到成功元素:', s, el);
                return { success: true, reason: 'success_element' };
            }
        }
        
        // 2. 检查文字内容
        const pageText = document.body.innerText;
        if (pageText.includes('成功加入购物车') || 
            pageText.includes('已加入购物车') || 
            pageText.includes('去结算')) {
            console.log('[checkSuccess] 检测到成功文字');
            return { success: true, reason: 'success_text' };
        }
        
        // 3. 检查 URL 变化
        if (window.location.href.includes('cart.taobao.com') || 
            window.location.href.includes('success') ||
            window.location.href.includes('buy.taobao.com')) {
            console.log('[checkSuccess] URL 变化:', window.location.href);
            return { success: true, reason: 'url_change' };
        }
        
        // 4. 检查购物车图标状态
        const cartIcon = document.querySelector('.cart-icon') || 
                        document.querySelector('.J_MiniCart') ||
                        document.querySelector('.mini-cart');
        if (cartIcon) {
            const cartText = cartIcon.innerText || '';
            if (/\d+/.test(cartText)) {
                console.log('[checkSuccess] 购物车数量变化');
                return { success: true, reason: 'cart_count' };
            }
        }
        
        return { success: false };
    };

    // 在 iframe 中查找元素
    const findInIframes = (selectors) => {
        console.log('[findInIframes] 开始在 iframe 中查找...');
        const iframes = document.querySelectorAll('iframe');
        console.log(`[findInIframes] 找到 ${iframes.length} 个 iframe`);
        
        for (const iframe of iframes) {
            try {
                const iframeDoc = iframe.contentDocument || iframe.contentWindow.document;
                if (!iframeDoc) continue;
                
                for (const selector of selectors) {
                    const el = iframeDoc.querySelector(selector);
                    if (el) {
                        console.log('[findInIframes] 在 iframe 中找到:', selector, el);
                        return { element: el, inIframe: true, iframeDoc };
                    }
                }
            } catch(e) {
                // 跨域 iframe 无法访问
                console.log('[findInIframes] iframe 跨域限制:', e.message);
            }
        }
        return null;
    };

    // 使用 XPath 查找元素（更稳定）
    const findByXPath = (xpaths) => {
        for (const xpath of xpaths) {
            try {
                const result = document.evaluate(
                    xpath,
                    document,
                    null,
                    XPathResult.FIRST_ORDERED_NODE_TYPE,
                    null
                );
                if (result.singleNodeValue) {
                    console.log('[XPath] 找到元素:', xpath, result.singleNodeValue);
                    return result.singleNodeValue;
                }
            } catch(e) {
                console.log('[XPath] 查询失败:', xpath, e.message);
            }
        }
        return null;
    };

    // 查找加购按钮（多策略增强版）
    const findAddToCartButton = () => {
        console.log('[findAddToCartButton] 开始查找加购按钮...');
        
        // 策略 1: CSS 选择器（主文档）
        const btnSelectors = [
            // 淘宝经典选择器（高优先级）
            '.J_LinkBasket', '#J_LinkBasket', '.J_AddToCart', '#J_AddToCart',
            '.J_BtnBasket', '#J_BtnBasket',
            
            // 天猫/旗舰店
            '.add-cart-btn', '.tm-cart-btn', '.buy-cart', '.btn-add-cart',
            '.tm-cart-add', '#tm-cart-add',
            
            // 通用选择器
            '[title="加入购物车"]', '[aria-label="加入购物车"]',
            '.add_cart', '.tb-btn-add', '.cart-add',
            
            // 动态类名（模糊匹配）
            '[class*="addCart"]', '[class*="addToCart"]', '[class*="basket"]',
            '[class*="j_link"]', '[class*="j_add"]',
            
            // 按钮类型
            'button[name="action"]', 'input[type="button"][value*="购物车"]'
        ];
        
        for (const s of btnSelectors) {
            const btn = document.querySelector(s);
            if (btn) {
                console.log('[findAddToCartButton] CSS 选择器找到:', s, btn);
                return { element: btn, inIframe: false };
            }
        }
        
        // 策略 2: XPath（更稳定，不受类名变化影响）
        const xpaths = [
            '//button[contains(text(),"加入购物车")]',
            '//a[contains(text(),"加入购物车")]',
            '//span[contains(text(),"加入购物车")]',
            '//div[contains(text(),"加入购物车")]',
            '//button[contains(text(),"加购")]',
            '//a[contains(text(),"加购")]',
            '//button[contains(@class,"cart") and contains(@class,"add")]',
            '//a[contains(@class,"basket")]'
        ];
        
        const xpathBtn = findByXPath(xpaths);
        if (xpathBtn) {
            console.log('[findAddToCartButton] XPath 找到:', xpathBtn);
            return { element: xpathBtn, inIframe: false };
        }
        
        // 策略 3: 文本内容匹配（兜底）
        const allElements = document.querySelectorAll('button, a, span, div, i');
        const textBtn = Array.from(allElements).find(el => {
            const text = (el.innerText || el.textContent || '').trim();
            return (text === '加入购物车' || text === '加购' || text.includes('加入购物车')) &&
                   el.offsetHeight > 0 &&
                   window.getComputedStyle(el).display !== 'none';
        });
        
        if (textBtn) {
            console.log('[findAddToCartButton] 文本匹配找到:', textBtn);
            return { element: textBtn, inIframe: false };
        }
        
        // 策略 4: 在 iframe 中查找
        const iframeResult = findInIframes(btnSelectors);
        if (iframeResult) {
            console.log('[findAddToCartButton] iframe 中找到:', iframeResult);
            return iframeResult;
        }
        
        console.log('[findAddToCartButton] 未找到加购按钮');
        return null;
    };

    // 检查按钮是否可用
    const isButtonEnabled = (btn) => {
        if (!btn) return false;
        
        const disabled = btn.classList.contains('disabled') || 
                        btn.getAttribute('disabled') === 'disabled' ||
                        btn.getAttribute('aria-disabled') === 'true' ||
                        window.getComputedStyle(btn).opacity < 0.6 ||
                        window.getComputedStyle(btn).pointerEvents === 'none' ||
                        (btn.innerText && btn.innerText.includes('库存不足')) ||
                        (btn.innerText && btn.innerText.includes('售罄'));
        
        if (disabled) {
            console.log('[isButtonEnabled] 按钮禁用:', btn);
        }
        
        return !disabled;
    };

    // 等待元素出现（MutationObserver 智能等待）
    const waitForElement = (timeout = 5000) => {
        return new Promise((resolve) => {
            const startTime = Date.now();
            
            // 先立即检查一次
            const result = findAddToCartButton();
            if (result) {
                console.log('[waitForElement] 立即找到元素');
                resolve(result);
                return;
            }
            
            // 创建观察者
            const observer = new MutationObserver((mutations) => {
                // 检查超时
                if (Date.now() - startTime > timeout) {
                    observer.disconnect();
                    resolve(null);
                    return;
                }
                
                // 检查是否有相关变化
                const hasRelevantChange = mutations.some(m => 
                    m.addedNodes.length > 0 || 
                    m.type === 'attributes' ||
                    m.type === 'childList'
                );
                
                if (hasRelevantChange) {
                    const result = findAddToCartButton();
                    if (result) {
                        observer.disconnect();
                        console.log('[waitForElement] 观察到元素出现');
                        resolve(result);
                    }
                }
            });
            
            observer.observe(document.body, {
                childList: true,
                subtree: true,
                attributes: true,
                attributeFilter: ['class', 'style', 'disabled']
            });
            
            // 超时处理
            setTimeout(() => {
                observer.disconnect();
                console.log('[waitForElement] 等待超时');
                resolve(null);
            }, timeout);
        });
    };

    // 主流程
    const findAndClick = async () => {
        if (isDone) {
            console.log('[findAndClick] 已完成，跳过');
            return;
        }
        
        // 检查超时
        const elapsed = Date.now() - startTime;
        if (elapsed > TIMEOUT_MS) {
            log('⏰ 超时 25 秒，请手动处理');
            console.log('[findAndClick] 总超时');
            return;
        }
        
        // 检查重试次数
        if (retryCount > MAX_RETRIES) {
            log('⚠️ 重试次数过多，请手动处理');
            console.log('[findAndClick] 重试次数超限');
            return;
        }
        
        try {
            // 1. 等待元素出现（智能等待）
            sub('扫描页面...');
            const waitResult = await waitForElement(5000);
            
            if (!waitResult) {
                // 2. 未找到，尝试刷新页面（仅第一次重试）
                if (retryCount === 0) {
                    log('🔄 未找到按钮，尝试刷新...');
                    sub('页面刷新中...');
                    console.log('[findAndClick] 刷新页面');
                    retryCount++;
                    updateRetry(retryCount);
                    
                    // 标记需要刷新后重试
                    sessionStorage.setItem('n1_retry_after_refresh', 'true');
                    window.location.reload();
                    return;
                } else {
                    retryCount++;
                    updateRetry(retryCount);
                    sub(`未找到按钮 (重试 ${retryCount}/${MAX_RETRIES})`);
                    console.log('[findAndClick] 未找到按钮，继续重试');
                    
                    // 指数退避：1s -> 2s -> 4s -> 8s
                    const delay = Math.min(1000 * Math.pow(2, retryCount), 8000);
                    setTimeout(findAndClick, delay);
                    return;
                }
            }
            
            const btn = waitResult.element;
            const inIframe = waitResult.inIframe;
            
            // 视觉标记
            btn.style.outline = '5px solid #f5222d';
            btn.style.boxShadow = '0 0 30px #f5222d';
            btn.style.transition = 'all 0.3s';
            
            // 3. 检查按钮状态
            if (!isButtonEnabled(btn)) {
                log('⚠️ 请先选规格');
                sub('按钮禁用，请选择颜色/尺寸');
                console.log('[findAndClick] 按钮禁用');
                
                // 按钮禁用时，2 秒后重试
                retryCount++;
                updateRetry(retryCount);
                setTimeout(findAndClick, 2000);
                return;
            }
            
            // 4. 执行点击
            log('🔥 锁定按钮，执行点击...');
            sub('点击中...');
            console.log('[findAndClick] 开始点击', { inIframe, btn });
            
            if (inIframe) {
                // iframe 内点击需要特殊处理
                simulateClick(btn);
            } else {
                simulateClick(btn);
            }
            
            isDone = true;
            
            // 5. 验证结果（快速轮询）
            let verifyAttempts = 0;
            const maxVerifyAttempts = 10;
            
            const verifyInterval = setInterval(() => {
                verifyAttempts++;
                const result = checkSuccess();
                
                if (result.success) {
                    clearInterval(verifyInterval);
                    log(`🏆 加购成功！(${result.reason})`);
                    sub('正在跳转...');
                    console.log('[verifyInterval] 验证成功:', result.reason);
                    setTimeout(() => {
                        chrome.runtime.sendMessage({ type: 'ITEM_ADDED' });
                    }, 1500);
                } else if (verifyAttempts >= maxVerifyAttempts) {
                    clearInterval(verifyInterval);
                    log('⚠️ 未检测到成功，请手动确认');
                    sub('可点击"成功"或"跳过"按钮');
                    console.log('[verifyInterval] 验证超时');
                } else {
                    sub(`验证中... (${verifyAttempts}/${maxVerifyAttempts})`);
                    // 再次尝试点击（防止点击失效）
                    if (verifyAttempts % 3 === 0) {
                        console.log('[verifyInterval] 重试点击');
                        simulateClick(btn);
                    }
                }
            }, 1200);
            
        } catch(e) {
            console.error('[findAndClick] 异常:', e);
            log('⚠️ 发生错误，请手动处理');
            sub(`错误：${e.message}`);
            
            retryCount++;
            updateRetry(retryCount);
            setTimeout(findAndClick, 2000);
        }
    };

    // 设置数量
    const setQuantity = async () => {
        if (targetQty <= 1) {
            console.log('[setQuantity] 数量为 1，跳过');
            return;
        }
        
        log(`🎯 设置数量：${targetQty}`);
        sub('查找数量输入框...');
        
        const quantitySelectors = [
            '.mui-amount-input', '#J_IptAmount', '.amount-input',
            '.quantity-inner input', '[name="quantity"]', '#quantity',
            '.J_EmpNum', '.tb-text-buy-num'
        ];
        
        let input = null;
        for (const s of quantitySelectors) {
            input = document.querySelector(s);
            if (input) break;
        }
        
        if (input) {
            console.log('[setQuantity] 找到输入框:', input);
            
            // 清除原有值
            input.value = '';
            input.dispatchEvent(new Event('input', { bubbles: true }));
            
            // 设置新值
            await new Promise(r => setTimeout(r, 300));
            input.value = targetQty.toString();
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.dispatchEvent(new Event('change', { bubbles: true }));
            
            console.log('[setQuantity] 数量已设置:', targetQty);
            await new Promise(r => setTimeout(r, 1200));
        } else {
            console.log('[setQuantity] 未找到数量输入框');
            sub('未找到数量输入框，使用默认值');
        }
    };

    // 启动流程
    const run = async () => {
        console.log('[run] 启动自动化流程');
        log('🚀 开始自动化加购');
        
        // 检查是否是刷新后的重试
        const isRefreshRetry = sessionStorage.getItem('n1_retry_after_refresh');
        if (isRefreshRetry) {
            console.log('[run] 刷新后重试');
            sessionStorage.removeItem('n1_retry_after_refresh');
            retryCount = 1;
            updateRetry(retryCount);
        }
        
        // 1. 设置数量
        await setQuantity();
        
        // 2. 查找并点击按钮
        await findAndClick();
    };

    // 延迟启动（确保页面完全加载）
    // v6.8 改进：根据页面加载状态动态调整延迟
    if (document.readyState === 'complete') {
        console.log('[run] 页面已加载，立即启动');
        setTimeout(run, 2000);
    } else {
        console.log('[run] 等待页面加载完成');
        window.addEventListener('load', () => {
            console.log('[run] 页面加载完成');
            setTimeout(run, 3500);
        });
    }
}
