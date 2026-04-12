# 给 manus 的指令 - 淘宝采购插件 v7.1 修复

**时间**: 2026-04-04  
**任务**: 修复淘宝采购插件的两个关键问题  
**基础版本**: v6.8（3 月 30 日，稳定可用版本）

---

## 📦 附件文件

**插件包**: `n1_helper_for_manus_v6.8.tar.gz`  
**位置**: `/root/.openclaw/workspace/projects/n1-lab-automation/n1_helper_for_manus_v6.8.tar.gz`  
**大小**: 7.8KB  
**版本**: v6.8（2026-03-30）

**说明**: 这是今天之前最后一个稳定可用的版本，能正常打开淘宝页面并执行加购，但有两个问题需要修复。

---

## 🎯 需要修复的两个问题

### 问题 1: 淘宝页面打开后不执行自动化 ⭐⭐⭐⭐⭐
**现象**: 点击"开启全自动采购"后，能打开淘宝页面，但插件什么都不执行  
**原因**: `background.js` 没有在 URL 后添加 `n1_auto_add=1` 参数  
**严重性**: 致命（插件无法工作）

### 问题 2: 采购数量 > 1 时卡顿 ⭐⭐⭐⭐
**现象**: 当 BOM 中某个零件的 `purchase_quantity > 1` 时，在设置数量步骤卡住  
**原因**: 清空输入框的操作触发淘宝验证机制  
**严重性**: 高（多件采购无法使用）

---

## 📁 需要修改的文件

### 1. `extension/background.js` (致命问题修复)

**文件位置**: 第 42-55 行的 `processNext()` 函数

**当前代码** (v6.8):
```javascript
function processNext() {
    if (!isProcessing) return;
    
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
```

**修改后** (v7.1):
```javascript
function processNext() {
    if (!isProcessing) return;
    
    if (purchaseQueue.length === 0) {
        isProcessing = false;
        console.log('✅ 任务全部结束');
        return;
    }
    
    const nextLink = purchaseQueue.shift();
    console.log('🚀 准备开启:', nextLink);
    
    // v7.1 修复：添加自动化参数
    const autoAddUrl = nextLink.includes('?') 
        ? `${nextLink}&n1_auto_add=1` 
        : `${nextLink}?n1_auto_add=1`;
    
    console.log('[processNext] 使用 URL:', autoAddUrl);
    
    chrome.tabs.create({ url: autoAddUrl }, (tab) => {
        currentTabId = tab.id;
    });
}
```

**关键改动**:
- ✅ 在 URL 后添加 `?n1_auto_add=1` 或 `&n1_auto_add=1`
- ✅ 这样 content.js 才能检测到参数并执行自动化流程

---

### 2. `extension/content.js` (重要问题修复)

**文件位置**: 第 497-540 行的 `setQuantity` 函数

**当前代码** (v6.8):
```javascript
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
        
        // ❌ 问题：清除原有值会触发淘宝验证
        input.value = '';
        input.dispatchEvent(new Event('input', { bubbles: true }));
        
        // 设置新值
        await new Promise(r => setTimeout(r, 300));
        input.value = targetQty.toString();
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        
        console.log('[setQuantity] 数量已设置:', targetQty);
        await new Promise(r => setTimeout(r, 1200));  // ❌ 等待时间不足
    } else {
        console.log('[setQuantity] 未找到数量输入框');
        sub('未找到数量输入框，使用默认值');
    }
};
```

**修改后** (v7.1):
```javascript
// 设置数量（v7.1 修复版）
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
    
    if (!input) {
        console.log('[setQuantity] 未找到数量输入框');
        sub('未找到数量输入框，使用默认值');
        return;
    }
    
    console.log('[setQuantity] 找到输入框:', input);
    sub('设置采购数量...');
    
    try {
        // ✅ 1. 聚焦输入框
        input.focus();
        await new Promise(r => setTimeout(r, 200));
        
        // ✅ 2. 全选原有内容（代替清空）
        input.select();
        await new Promise(r => setTimeout(r, 100));
        
        // ✅ 3. 直接设置新值
        input.value = targetQty.toString();
        
        // ✅ 4. 触发完整事件链
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('blur', { bubbles: true }));
        
        console.log('[setQuantity] 数量已设置:', targetQty);
        
        // ✅ 5. 等待淘宝验证（增加时间）
        sub('等待页面更新...');
        await new Promise(r => setTimeout(r, 2000));
        
        // ✅ 6. 验证设置结果
        const actualValue = parseInt(input.value) || 1;
        if (actualValue !== targetQty) {
            console.warn('[setQuantity] 验证失败，实际值:', actualValue);
            sub('数量设置失败，继续加购');
        } else {
            console.log('[setQuantity] 验证成功');
            sub('✓ 数量设置完成');
        }
        
    } catch (e) {
        console.error('[setQuantity] 异常:', e);
        sub('数量设置异常，继续加购');
    }
};
```

**关键改动**:
1. ✅ `input.value = ''` → `input.select()` (全选代替清空，避免触发验证)
2. ✅ 添加 `input.focus()` 和 `input.blur()` (完整的事件链)
3. ✅ 等待时间：1200ms → 2000ms (给淘宝足够验证时间)
4. ✅ 添加验证逻辑 (确认设置成功)
5. ✅ 添加 try-catch 错误处理

---

### 3. `extension/manifest.json` (版本号更新)

**当前代码** (v6.8):
```json
{
  "manifest_version": 3,
  "name": "N+1 LAB 采购助手 v6.8",
  "version": "6.8",
  "description": "稳定版本",
  ...
}
```

**修改后** (v7.1):
```json
{
  "manifest_version": 3,
  "name": "N+1 LAB 采购助手 v7.1",
  "version": "7.1",
  "description": "修复数量设置问题：完整事件链 + 验证机制",
  ...
}
```

---

## 🧪 测试步骤

### 1. 解压插件
```bash
tar -xzf n1_helper_for_manus_v6.8.tar.gz
cd extension
```

### 2. 备份原文件
```bash
cp background.js background.js.v6.8.backup
cp content.js content.js.v6.8.backup
```

### 3. 修改代码
按上述要求修改 3 个文件

### 4. 加载插件
1. Chrome 打开 `chrome://extensions/`
2. 开启"开发者模式"
3. 点击"加载已解压的扩展程序"
4. 选择 `extension` 文件夹
5. 确认版本显示为 **v7.1**

### 5. 功能测试

#### 场景 1: 基础流程（必须先通过）⭐⭐⭐⭐⭐
- 打开 N+1 管理后台：`http://43.156.225.39:8080/`
- 进入"产品中心"
- 点击任意产品的"🔍 BOM 详情"
- 点击"🚀 开启全自动采购"
- **预期**: 
  - ✅ 自动打开淘宝商品页面
  - ✅ 控制台显示 `[processNext] 使用 URL: xxx? n1_auto_add=1`
  - ✅ 悬浮窗显示"🦐 小虾虾 v7.1"
  - ✅ 自动执行加购流程

#### 场景 2: 数量=1
- BOM 中零件的 `purchase_quantity = 1`
- **预期**: 
  - ✅ 打开淘宝页面
  - ✅ 跳过数量设置
  - ✅ 直接加购成功

#### 场景 3: 数量>1
- 修改 BOM，设置 `purchase_quantity = 5`
- **预期**: 
  - ✅ 打开淘宝页面
  - ✅ 悬浮窗显示"设置采购数量..."
  - ✅ 数量自动设置为 5
  - ✅ 显示"✓ 数量设置完成"
  - ✅ 成功加入购物车

#### 场景 4: 连续采购
- BOM 中有 3-5 个带淘宝链接的零件
- **预期**: 
  - ✅ 每个商品都能正确打开
  - ✅ 每个商品都能正确设置数量
  - ✅ 所有商品都能成功加购
  - ✅ 无卡顿、无报错

---

## 📦 交付物

1. ✅ **修改后的代码**
   - `extension/background.js` (v7.1)
   - `extension/content.js` (v7.1)
   - `extension/manifest.json` (v7.1)

2. ✅ **打包文件**
   - `n1_helper_v7.1.tar.gz`

3. ✅ **测试报告**
   - 4 个场景的测试结果（截图或文字说明）
   - 如有问题，提供控制台日志

---

## 🚀 快速命令

```bash
# 解压
tar -xzf n1_helper_for_manus_v6.8.tar.gz
cd extension

# 备份
cp background.js background.js.v6.8.backup
cp content.js content.js.v6.8.backup

# 修改文件
nano background.js    # 添加 n1_auto_add=1 参数
nano content.js       # 修复数量设置逻辑
nano manifest.json    # 更新版本号为 7.1

# 打包
cd ..
tar -czf n1_helper_v7.1.tar.gz extension/

# 验证
ls -lh n1_helper_v7.1.tar.gz
```

---

## ⚠️ 注意事项

1. **必须先修复 background.js** - 否则插件无法工作
2. **测试时打开 F12 控制台** - 查看日志确认参数是否正确添加
3. **如果数量设置还是失败** - 检查控制台 `[setQuantity]` 日志

---

**完成后把 `n1_helper_v7.1.tar.gz` 发给 Shuni 测试！** 🦐
