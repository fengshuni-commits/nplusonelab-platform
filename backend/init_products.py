#!/usr/bin/env python3
"""
初始化 21 个 SKU 产品数据 (带 API KEY 版)
"""

import httpx
import json

BASE_URL = "http://localhost:8000"
API_KEY = "n1lab2026"

# 21 个 SKU 数据（来自 v3.1 文档）
PRODUCTS = [
    {"sku_code": "AP2501-SKU1", "product_name": "小推车 - 国产裸板", "category": "小推车", "n1_price": 211.50, "retail_price": 599, "stock_quantity": 50},
    {"sku_code": "AP2501-SKU2", "product_name": "小推车 - UV 漆进口板含组装", "category": "小推车", "n1_price": 211.50, "retail_price": 899, "stock_quantity": 30},
    {"sku_code": "AP2401-SKU1", "product_name": "置物架 - 单个框架", "category": "置物架", "n1_price": 69.60, "retail_price": 500, "stock_quantity": 100},
    {"sku_code": "AP2401-SKU2", "product_name": "置物架 - 海洋板置物单元", "category": "置物架", "n1_price": 15.30, "retail_price": 150, "stock_quantity": 200},
    {"sku_code": "AP2401-SKU3", "product_name": "置物架 - 海洋板抽屉", "category": "置物架", "n1_price": 54.30, "retail_price": 200, "stock_quantity": 80},
    {"sku_code": "AP2401-SKU4", "product_name": "置物架 - 不锈钢展示板", "category": "置物架", "n1_price": 26.04, "retail_price": 200, "stock_quantity": 100},
    {"sku_code": "AP2401-SKU5", "product_name": "置物架 - 不锈钢层板", "category": "置物架", "n1_price": 19.50, "retail_price": 240, "stock_quantity": 100},
    {"sku_code": "AP2401-SKU6", "product_name": "置物架 - 玻璃层板", "category": "置物架", "n1_price": 37.50, "retail_price": 240, "stock_quantity": 80},
    {"sku_code": "AP2401-SKU7", "product_name": "置物架 - 织物挂杆", "category": "置物架", "n1_price": 11.52, "retail_price": 60, "stock_quantity": 150},
    {"sku_code": "AP2402-SKU1", "product_name": "推柜 - 不含侧板", "category": "推柜", "n1_price": 309.23, "retail_price": 1500, "stock_quantity": 30},
    {"sku_code": "AP2402-SKU2", "product_name": "推柜 - 含长虹亚克力侧板", "category": "推柜", "n1_price": 309.23, "retail_price": 1750, "stock_quantity": 20},
    {"sku_code": "AP2403-SKU1", "product_name": "茶几 - 桌架", "category": "茶几", "n1_price": 65.40, "retail_price": 349, "stock_quantity": 50},
    {"sku_code": "AP2403-SKU2", "product_name": "茶几 - 桌架 + 玻璃", "category": "茶几", "n1_price": 65.40, "retail_price": 799, "stock_quantity": 30},
    {"sku_code": "AP2502-SKU1", "product_name": "天地杆书架 - 天地杆", "category": "天地杆书架", "n1_price": 132.60, "retail_price": 240, "stock_quantity": 40},
    {"sku_code": "AP2502-SKU2", "product_name": "天地杆书架 - C 型搁板", "category": "天地杆书架", "n1_price": 50.00, "retail_price": 130, "stock_quantity": 60},
    {"sku_code": "AP2502-SKU3", "product_name": "天地杆书架 - 天地杆 +2C 型搁板", "category": "天地杆书架", "n1_price": 200.00, "retail_price": 500, "stock_quantity": 30},
    {"sku_code": "AP2502-SKU4", "product_name": "天地杆书架 - 一字板", "category": "天地杆书架", "n1_price": 0.60, "retail_price": 200, "stock_quantity": 100},
    {"sku_code": "AP2502-SKU5", "product_name": "天地杆书架 - 工字盒", "category": "天地杆书架", "n1_price": 3.00, "retail_price": 700, "stock_quantity": 50},
    {"sku_code": "AP2503-SKU1", "product_name": "工作桌 - 桌架", "category": "工作桌", "n1_price": 269.91, "retail_price": 950, "stock_quantity": 20},
    {"sku_code": "AP2503-SKU2", "product_name": "工作桌 - 桌架 + 玻璃桌面", "category": "工作桌", "n1_price": 269.91, "retail_price": 1450, "stock_quantity": 15},
    {"sku_code": "A2504-SKU1", "product_name": "餐边柜", "category": "餐边柜", "n1_price": 305.10, "retail_price": 2000, "stock_quantity": 10},
]

def init_products():
    print("📦 开始初始化 21 个 SKU 产品数据...")
    with httpx.Client() as client:
        for product in PRODUCTS:
            try:
                response = client.post(f"{BASE_URL}/products/", json=product, headers={"X-API-Key": API_KEY})
                if response.status_code == 200:
                    print(f"✅ {product['sku_code']}: {product['product_name']}")
                else:
                    print(f"❌ {product['sku_code']}: {response.text}")
            except Exception as e:
                print(f"❌ {product['sku_code']}: {e}")
    print("\n✅ 产品数据初始化完成！")

if __name__ == "__main__":
    init_products()
