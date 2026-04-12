# N+1 LAB 自动化平台 - 后端 API

## 🚀 快速启动

### 1. 安装依赖

```bash
cd /root/.openclaw/workspace/projects/n1-lab-automation/backend
pip3 install -r requirements.txt --break-system-packages
```

### 2. 启动服务

```bash
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

访问：http://localhost:8000

### 3. API 文档

启动后访问：
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 📋 API 接口

### 经销商管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/dealers/` | 创建经销商申请 |
| GET | `/dealers/` | 获取经销商列表 |
| GET | `/dealers/{id}` | 获取经销商详情 |
| PUT | `/dealers/{id}/status` | 更新经销商状态 |

### 产品管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/products/` | 创建产品（SKU） |
| GET | `/products/` | 获取产品列表 |

### 订单管理

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/orders/` | 创建订单 |
| GET | `/orders/` | 获取订单列表 |

---

## 📊 数据库

**类型**: SQLite（MVP 阶段）
**文件**: `n1_lab.db`

**表结构**:
- `dealers` - 经销商档案
- `products` - 产品信息（21 个 SKU）
- `orders` - 订单
- `order_items` - 订单明细

---

## 🧪 测试示例

### 创建经销商

```bash
curl -X POST "http://localhost:8000/dealers/" \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "测试公司",
    "shop_name": "测试店铺",
    "contact_name": "张三",
    "contact_phone": "13800138000",
    "platform": "淘宝"
  }'
```

### 创建产品

```bash
curl -X POST "http://localhost:8000/products/" \
  -H "Content-Type: application/json" \
  -d '{
    "sku_code": "AP2501-SKU1",
    "product_name": "小推车 - 国产裸板",
    "category": "小推车",
    "config": "国产裸板配置",
    "n1_price": 211.50,
    "retail_price": 599,
    "stock_quantity": 100
  }'
```

### 创建订单

```bash
curl -X POST "http://localhost:8000/orders/" \
  -H "Content-Type: application/json" \
  -d '{
    "dealer_id": 1,
    "items": [
      {"product_id": 1, "quantity": 2}
    ]
  }'
```

---

## 📝 下一步

1. ✅ 后端框架完成
2. ⏳ 添加 21 个 SKU 数据
3. ⏳ 前端管理界面
4. ⏳ 部署到服务器
