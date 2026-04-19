# 📊 N+1 LAB 数据看板功能 - 使用说明

**更新时间**: 2026-04-19 22:30  
**功能**: 按时间筛选统计订单金额、采购成本、营利

---

## ✅ 已完成功能

### 1. 后端 API

**接口**: `GET /dashboard/stats`

**参数**:
- `start_date` (可选): 开始日期，格式 `YYYY-MM-DD`
- `end_date` (可选): 结束日期，格式 `YYYY-MM-DD`
- `X-API-Key`: `n1lab2026`

**返回数据**:
```json
{
  "summary": {
    "total_orders": 5,           // 订单总数
    "total_amount": 4560.06,     // 订单总金额
    "total_procurement_cost": 1196.0,  // 总采购成本（订单 + 库存）
    "total_profit": -1196.0,     // 总利润
    "profit_margin": -26.23      // 毛利率 (%)
  },
  "status_breakdown": {          // 订单状态分布
    "pending": {"count": 2, "amount": 2593.08},
    "processing": {"count": 3, "amount": 1966.98}
  },
  "category_breakdown": [        // 按产品类别统计
    {
      "category": "工作桌",
      "order_count": 3,
      "total_amount": 3025.26,
      "total_cost": 0,
      "total_profit": 0
    }
  ],
  "inventory_cost": 1196.0,      // 库存采购成本
  "order_procurement_cost": 0,   // 订单采购成本
  "time_range": {                // 时间范围
    "start_date": null,
    "end_date": null
  }
}
```

---

### 2. 前端界面

**位置**: 管理后台 → 数据看板（首页）

**功能**:
1. **时间筛选器**
   - 开始日期选择器
   - 结束日期选择器
   - 查询按钮
   - 重置按钮

2. **核心指标卡片**（4 个）
   - 📦 订单总数
   - 💰 订单总金额
   - 📉 总采购成本（订单 + 库存）
   - 📈 总利润（含毛利率）

3. **成本明细**
   - 订单采购成本
   - 库存采购成本
   - 订单状态分布

4. **按产品类别统计**
   - 类别名称
   - 订单数
   - 销售金额
   - 采购成本
   - 利润
   - 毛利率

---

## 🎨 界面设计

**渐变卡片**（4 个核心指标）:
- 📦 订单总数：紫色渐变
- 💰 订单总金额：粉红渐变
- 📉 总采购成本：蓝色渐变
- 📈 总利润：绿色渐变

**响应式布局**:
- 核心指标：4 列网格
- 成本明细：2 列网格
- 类别统计：表格展示

---

## 📝 使用示例

### 1. 查询全部数据
- 不选择日期，直接点击"🔍 查询"
- 显示所有历史数据

### 2. 查询本月数据
- 开始日期：`2026-04-01`
- 结束日期：`2026-04-30`
- 点击"🔍 查询"

### 3. 查询特定时间段
- 开始日期：`2026-03-01`
- 结束日期：`2026-03-31`
- 点击"🔍 查询"

### 4. 重置筛选
- 点击"🔄 重置"
- 清除日期选择，显示全部数据

---

## 🔧 技术实现

### 后端 (Python/FastAPI)
```python
@app.get("/dashboard/stats")
def get_dashboard_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    # SQL 查询统计订单、采购成本、利润
    # 支持时间筛选
    # 返回分类统计
```

### 前端 (HTML/JavaScript)
```javascript
async function loadDashboardStats() {
    const startDate = document.getElementById('filter-start-date').value;
    const endDate = document.getElementById('filter-end-date').value;
    
    const response = await fetch(`${API_BASE}/dashboard/stats`, {
        headers: { 'X-API-Key': 'n1lab2026' },
        params: { start_date, end_date }
    });
    
    const data = await response.json();
    // 更新 UI 显示
}
```

---

## 📊 数据说明

### 总采购成本
```
总采购成本 = 订单采购成本 + 库存采购成本
```

- **订单采购成本**: 直接关联订单的采购成本（`orders.procurement_cost`）
- **库存采购成本**: 库存采购记录的成本（`purchase_history.actual_cost * quantity`）

### 总利润
```
总利润 = 订单总金额 - 总采购成本
```

### 毛利率
```
毛利率 = (总利润 / 订单总金额) × 100%
```

---

## 🚀 访问地址

**管理后台**: http://43.156.225.39:8080/

**数据看板**: 登录后默认显示

---

## ⚠️ 注意事项

1. **时间范围**: 选择日期时，包含开始和结束日期当天
2. **数据刷新**: 点击查询按钮后实时加载最新数据
3. **重置功能**: 重置后显示所有历史数据
4. **权限要求**: 需要管理员权限（X-API-Key 认证）

---

## 📝 后续优化建议

1. **图表可视化**: 添加折线图/柱状图展示趋势
2. **导出功能**: 支持导出 Excel/CSV 报表
3. **对比功能**: 同比/环比数据对比
4. **预警功能**: 低毛利/负毛利自动预警
5. **更多维度**: 按经销商/客户/地区统计

---

**开发完成时间**: 2026-04-19 22:30  
**开发者**: 小虾虾 🦐
