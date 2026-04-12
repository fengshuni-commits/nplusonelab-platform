#!/usr/bin/env python3
"""
更新产品销售类型数据
- 零件包产品：sale_type='parts_pack', is_parts_pack=true
- 整体产品：sale_type='complete', is_parts_pack=false
"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).parent / "n1_lab_v3.db"

# 零件包产品关键词（产品名称或 SKU 包含这些关键词）
PARTS_PACK_KEYWORDS = [
    '零件包',
    '-P',  # SKU 后缀
    'SKU1-P',
    'SKU2-P',
]

# 整体产品关键词
COMPLETE_KEYWORDS = [
    '整体',
    '全套',
]

def update_products():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查并添加缺失的列
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN sale_type TEXT DEFAULT 'complete'")
        print("✅ 添加 sale_type 列")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("⚠️  sale_type 列已存在")
        else:
            raise
    
    try:
        cursor.execute("ALTER TABLE products ADD COLUMN is_parts_pack BOOLEAN DEFAULT FALSE")
        print("✅ 添加 is_parts_pack 列")
    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e).lower():
            print("⚠️  is_parts_pack 列已存在")
        else:
            raise
    
    conn.commit()
    
    # 获取所有产品
    cursor.execute("SELECT id, product_name, sku_code, sale_type, is_parts_pack FROM products")
    products = cursor.fetchall()
    
    updated_count = 0
    parts_pack_count = 0
    complete_count = 0
    
    for product in products:
        product_id, product_name, sku_code, current_sale_type, current_is_parts_pack = product
        
        # 判断是否为零件包
        is_parts_pack = False
        name_str = (product_name or '').lower()
        sku_str = (sku_code or '').lower()
        
        # 检查零件包关键词
        for keyword in PARTS_PACK_KEYWORDS:
            if keyword.lower() in name_str or keyword.lower() in sku_str:
                is_parts_pack = True
                break
        
        # 如果未匹配，检查产品编号规律（AP2401/2402/2403 等通常是零件包）
        if not is_parts_pack and sku_code:
            # 根据历史数据，AP 系列通常是零件包
            if sku_code.startswith('AP'):
                is_parts_pack = True
        
        # 设置销售类型
        sale_type = 'parts_pack' if is_parts_pack else 'complete'
        
        # 更新数据库
        cursor.execute("""
            UPDATE products 
            SET sale_type = ?, is_parts_pack = ?
            WHERE id = ?
        """, (sale_type, is_parts_pack, product_id))
        
        if cursor.rowcount > 0:
            updated_count += 1
            if is_parts_pack:
                parts_pack_count += 1
                print(f"✅ [零件包] ID:{product_id} | {product_name[:30]:30} | {sku_code}")
            else:
                complete_count += 1
                print(f"📦 [整体]   ID:{product_id} | {product_name[:30]:30} | {sku_code}")
    
    conn.commit()
    conn.close()
    
    print(f"\n=== 更新完成 ===")
    print(f"总产品数：{updated_count}")
    print(f"零件包：{parts_pack_count} 个")
    print(f"整体产品：{complete_count} 个")

if __name__ == "__main__":
    update_products()
