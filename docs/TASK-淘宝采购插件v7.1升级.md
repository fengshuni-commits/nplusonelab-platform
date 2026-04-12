# 淘宝采购插件 v7.1 升级任务书

**任务创建时间**: 2026-04-04 11:15  
**优先级**: ⭐⭐⭐⭐ 高优先级  
**预计工时**: 30-60 分钟  
**执行人**: Manus AI  
**验收人**: Shuni

---

## 📋 任务概述

**目标**: 修复 N+1 LAB 淘宝采购插件在采购数量 > 1 时的卡顿问题

**当前版本**: v6.8  
**目标版本**: v7.1

**核心问题**: 
- 当 BOM 中某个零件的 `purchase_quantity > 1` 时，插件在设置数量步骤卡顿
- 原因：清空输入框的方式触发淘宝验证机制，导致后续流程无法继续

**解决方案**: 
- 改进数量设置逻辑，使用 `select()` 全选代替清空
- 添加完整的事件链（focus → input → change → blur）
- 增加验证步骤，确保数量设置成功

---

## 📁 需要修改的文件

### 1. `extension/content.js` (主要修改)

**文件位置**: `/root/.openclaw/workspace/projects/n1-lab-automation/extension/content.js`

**修改位置**: 第 497-540 行（`setQuantity` 函数）

**修改内容**:

#### 修改前（v6.8 代码）:
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
```

#### 修改后（v7.1 代码）:
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

**关键改动点**:
1. ✅ `input.value = ''` → `input.select()` (全选代替清空)
2. ✅ 添加 `input.focus()` 和 `input.blur()` 事件
3. ✅ 等待时间：1200ms → 2000ms
4. ✅ 添加验证逻辑，确认设置成功
5. ✅ 添加 try-catch 错误处理

---

### 2. `extension/manifest.json` (版本号更新)

**文件位置**: `/root/.openclaw/workspace/projects/n1-lab-automation/extension/manifest.json`

**修改前**:
```json
{
  "manifest_version": 3,
  "name": "N+1 LAB 采购助手 v6.8",
  "version": "6.8",
  "description": "智能重试增强版：多策略元素查找 + 智能等待 + 增强重试 + iframe 支持",
  ...
}
```

**修改后**:
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

### 准备工作

1. **备份原文件**
   ```bash
   cd /root/.openclaw/workspace/projects/n1-lab-automation/extension
   cp content.js content.js.v6.8.backup
   ```

2. **修改代码**
   - 按上述要求修改 `content.js` 和 `manifest.json`

3. **重新加载插件**
   - 打开 Chrome 扩展管理页面：`chrome://extensions/`
   - 找到 "N+1 LAB 采购助手"
   - 点击刷新按钮 🔄

### 功能测试

#### 测试场景 1: 数量 = 1（跳过设置）

1. 打开 N+1 管理后台：`http://43.156.225.39:8080/`
2. 进入"产品中心"
3. 点击任意产品的"🔍 BOM 详情"
4. 点击"🚀 开启全自动采购"
5. **预期**: 第一个商品跳过数量设置，直接加购

#### 测试场景 2: 数量 > 1（设置数量）

1. 修改数据库，设置某个零件的采购数量为 5:
   ```sql
   UPDATE bom_items 
   SET purchase_quantity = '5' 
   WHERE product_id = 1 AND id = 1;
   ```

2. 刷新管理后台，打开 BOM 详情
3. 点击"🚀 开启全自动采购"
4. **预期**: 
   - 悬浮窗显示"设置采购数量..."
   - 数量输入框自动设置为 5
   - 悬浮窗显示"✓ 数量设置完成"
   - 成功加入购物车

#### 测试场景 3: 多个商品连续采购

1. 确保 BOM 中有 3-5 个带淘宝链接的零件
2. 开启全自动采购
3. **预期**: 
   - 每个商品都能正确设置数量
   - 所有商品都能成功加购
   - 无卡顿、无报错

---

## ✅ 验收标准

### 必须通过 (Must Have)

- [ ] **场景 1**: 数量=1 时，跳过设置，直接加购 ✅
- [ ] **场景 2**: 数量>1 时，正确设置数量并加购 ✅
- [ ] **场景 3**: 连续采购多个商品，无卡顿 ✅
- [ ] **控制台日志**: 显示"验证成功" ✅
- [ ] **悬浮窗状态**: 显示"✓ 数量设置完成" ✅

### 应该通过 (Should Have)

- [ ] 版本号更新为 7.1 ✅
- [ ] 描述文字更新 ✅
- [ ] 备份文件已创建 ✅

### 可以有 (Nice to Have)

- [ ] 添加错误提示（如商品限购）
- [ ] 添加重试机制（设置失败时重试）
- [ ] 优化等待时间（根据网络情况动态调整）

---

## 🐛 可能遇到的问题

### 问题 1: 修改后仍然卡顿

**排查步骤**:
1. 打开淘宝页面，按 F12 查看控制台
2. 查找 `[setQuantity]` 相关日志
3. 确认是否执行了新的代码逻辑
4. 检查是否有 JavaScript 错误

**解决方案**:
- 清除浏览器缓存
- 重新加载插件
- 确认修改的代码已生效

### 问题 2: 找不到数量输入框

**排查步骤**:
1. 手动打开商品页面
2. 按 F12，检查数量输入框的 class 名
3. 确认选择器是否匹配

**解决方案**:
- 添加新的选择器到 `quantitySelectors` 数组
- 例如：`'.new-selector-class'`

### 问题 3: 设置后数量变回 1

**可能原因**:
- 淘宝商品有限购规则
- 库存不足
- 商品 SKU 未选择

**解决方案**:
- 检查商品详情页的限购提示
- 确认库存充足
- 先选择颜色/尺寸等 SKU

---

## 📚 参考资料

### 相关文档

- **项目目录**: `/root/.openclaw/workspace/projects/n1-lab-automation/`
- **插件代码**: `/root/.openclaw/workspace/projects/n1-lab-automation/extension/`
- **修复方案**: `docs/2026-04-04_淘宝采购插件 v7.1 修复方案.md`

### 关键代码位置

| 函数名 | 作用 | 行号 |
|--------|------|------|
| `setQuantity()` | 设置采购数量 | 497-540 |
| `findAndClick()` | 查找并点击加购按钮 | 368-495 |
| `checkSuccess()` | 验证加购是否成功 | 119-165 |
| `run()` | 启动自动化流程 | 542-570 |

### 调试技巧

**查看日志**:
```javascript
console.log('[setQuantity] 调试信息');
```

**暂停调试**:
```javascript
debugger;  // 在这行设置断点
```

**检查元素**:
```javascript
console.log('输入框:', document.querySelector('.mui-amount-input'));
```

---

## 📝 完成后的操作

### 1. 代码审查

- [ ] 检查 `content.js` 修改是否正确
- [ ] 检查 `manifest.json` 版本号是否更新
- [ ] 确认没有语法错误

### 2. 功能测试

- [ ] 测试场景 1 通过
- [ ] 测试场景 2 通过
- [ ] 测试场景 3 通过

### 3. 文档更新

- [ ] 更新 `README.md` 版本号
- [ ] 记录修复内容到 `docs/` 目录
- [ ] 提交 git commit

### 4. 部署

- [ ] 打包新版本插件
- [ ] 通知 Shuni 验收
- [ ] 等待反馈

---

## 🎯 任务交付物

1. ✅ **修改后的代码**
   - `extension/content.js` (v7.1)
   - `extension/manifest.json` (v7.1)

2. ✅ **备份文件**
   - `extension/content.js.v6.8.backup`

3. ✅ **测试报告**
   - 3 个测试场景的截图/录屏
   - 控制台日志截图

4. ✅ **更新日志**
   ```markdown
   ## v7.1 (2026-04-04)
   
   ### 修复
   - 修复采购数量 > 1 时卡顿的问题
   - 改进数量设置逻辑，使用 select() 全选代替清空
   - 添加完整的事件链（focus → input → change → blur）
   - 增加验证步骤，确保数量设置成功
   
   ### 改进
   - 等待时间从 1200ms 增加到 2000ms
   - 添加 try-catch 错误处理
   - 优化悬浮窗提示信息
   ```

---

## 📞 联系方式

**任务创建人**: 小虾虾 🦐  
**技术负责人**: Shuni  
**执行 AI**: Manus

**如有疑问**:
1. 查看 `docs/2026-04-04_淘宝采购插件 v7.1 修复方案.md` 详细方案
2. 检查 `extension/content.js` 当前代码逻辑
3. 运行测试步骤验证修改效果

---

**任务状态**: ⏳ 待执行  
**创建时间**: 2026-04-04 11:15  
**期望完成**: 2026-04-04 12:00 前

---

## 🚀 快速开始

```bash
# 1. 进入项目目录
cd /root/.openclaw/workspace/projects/n1-lab-automation/extension

# 2. 备份当前版本
cp content.js content.js.v6.8.backup

# 3. 编辑 content.js (第 497-540 行)
nano content.js

# 4. 编辑 manifest.json
nano manifest.json

# 5. 重新加载插件并测试
# 打开 chrome://extensions/ → 刷新 N+1 LAB 采购助手
```

---

**Good Luck! 🦐**
