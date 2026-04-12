# 给 manus 的指令 - 淘宝采购插件 v7.1 修复

**时间**: 2026-04-04  
**任务**: 修复淘宝采购插件的两个关键问题

---

## 📦 附件文件

**插件包**: `n1_helper_v7.1_for_manus.tar.gz`  
**位置**: `/root/.openclaw/workspace/projects/n1-lab-automation/n1_helper_v7.1_for_manus.tar.gz`

---

## 🎯 任务目标

修复两个问题：

### 问题 1: 淘宝页面无法打开自动化流程 ⭐⭐⭐⭐⭐
**现象**: 点击"开启全自动采购"后，打开了淘宝页面但插件什么都不执行  
**原因**: `background.js` 没有添加 `n1_auto_add=1` 参数  
**修复**: 在打开淘宝链接时自动添加参数

### 问题 2: 采购数量 > 1 时卡顿 ⭐⭐⭐⭐
**现象**: 当 `purchase_quantity > 1` 时，在设置数量步骤卡顿  
**原因**: 清空输入框触发淘宝验证机制  
**修复**: 使用 `select()` 全选代替清空

---

## 📁 需要修改的文件

### 1. `extension/background.js`

**位置**: 约第 45-55 行的 `processNext()` 函数

**修改前**:
```javascript
chrome.tabs.create({ url: nextLink }, (tab) => {
    currentTabId = tab.id;
});
```

**修改后**:
```javascript
// v7.1 修复：添加自动化参数
const autoAddUrl = nextLink.includes('?') 
    ? `${nextLink}&n1_auto_add=1` 
    : `${nextLink}?n1_auto_add=1`;

console.log('[processNext] 使用 URL:', autoAddUrl);

chrome.tabs.create({ url: autoAddUrl }, (tab) => {
    currentTabId = tab.id;
});
```

---

### 2. `extension/content.js`

**位置**: 约第 497-540 行的 `setQuantity` 函数

**关键修改**:
- `input.value = ''` → `input.select()` (全选代替清空)
- 添加 `input.focus()` 和 `input.blur()`
- 等待时间：1200ms → 2000ms
- 添加验证逻辑

**完整修改后代码**:
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
        // 1. 聚焦输入框
        input.focus();
        await new Promise(r => setTimeout(r, 200));
        
        // 2. 全选原有内容
        input.select();
        await new Promise(r => setTimeout(r, 100));
        
        // 3. 直接设置新值
        input.value = targetQty.toString();
        
        // 4. 触发完整事件链
        input.dispatchEvent(new Event('input', { bubbles: true }));
        input.dispatchEvent(new Event('change', { bubbles: true }));
        input.dispatchEvent(new Event('blur', { bubbles: true }));
        
        console.log('[setQuantity] 数量已设置:', targetQty);
        
        // 5. 等待淘宝验证
        sub('等待页面更新...');
        await new Promise(r => setTimeout(r, 2000));
        
        // 6. 验证设置结果
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

---

### 3. `extension/manifest.json`

**修改版本号和描述**:

**修改前**:
```json
{
  "name": "N+1 LAB 采购助手 v6.8",
  "version": "6.8",
  "description": "智能重试增强版：多策略元素查找 + 智能等待 + 增强重试 + iframe 支持",
  ...
}
```

**修改后**:
```json
{
  "name": "N+1 LAB 采购助手 v7.1",
  "version": "7.1",
  "description": "修复数量设置问题：完整事件链 + 验证机制",
  ...
}
```

---

## 🧪 测试步骤

### 准备工作
```bash
# 1. 解压插件
tar -xzf n1_helper_v7.1_for_manus.tar.gz

# 2. 备份原文件
cd extension
cp background.js background.js.backup
cp content.js content.js.backup
```

### 修改代码
按上述要求修改 3 个文件

### 测试验证
1. Chrome 打开 `chrome://extensions/`
2. 开启"开发者模式"
3. 点击"加载已解压的扩展程序"
4. 选择 `extension` 文件夹
5. 确认版本显示为 **v7.1**

### 功能测试

**场景 1: 基础流程**（必须先通过）
- 打开 BOM 详情 → 点击"开启全自动采购"
- ✅ 应该打开淘宝页面并执行自动化

**场景 2: 数量=1**
- ✅ 跳过数量设置，直接加购

**场景 3: 数量>1**
- ✅ 自动设置数量
- ✅ 显示"✓ 数量设置完成"
- ✅ 成功加入购物车

**场景 4: 连续采购**
- ✅ 所有商品都能正确加购
- ✅ 无卡顿、无报错

---

## 📦 交付物

1. ✅ **修改后的代码**
   - `extension/background.js`
   - `extension/content.js`
   - `extension/manifest.json`

2. ✅ **打包文件**
   - `n1_helper_v7.1.tar.gz`

3. ✅ **测试报告**
   - 4 个场景的测试结果
   - 控制台日志截图（如有问题）

---

## 🚀 快速命令

```bash
# 解压
tar -xzf n1_helper_v7.1_for_manus.tar.gz

# 修改文件
cd extension
nano background.js  # 添加参数
nano content.js      # 修复数量设置
nano manifest.json   # 更新版本号

# 打包
cd ..
tar -czf n1_helper_v7.1.tar.gz extension/

# 验证
ls -lh n1_helper_v7.1.tar.gz
```

---

**完成后把 `n1_helper_v7.1.tar.gz` 发给 Shuni 测试！** 🦐
