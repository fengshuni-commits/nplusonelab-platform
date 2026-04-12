"""
更新工作桌 SKU1 BOM - 将 4 个内六角扳手换成扳手套装
"""
import sqlite3

DB_PATH = 'n1_lab_v3.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 删除 4 个内六角扳手
cursor.execute("DELETE FROM bom_items WHERE product_id = 19 AND part_name LIKE '%内六角扳手%'")
deleted = cursor.rowcount
print(f"✅ SKU1: 删除了 {deleted} 个内六角扳手")

# 添加扳手套装
cursor.execute("""
    INSERT INTO bom_items (
        product_id, part_name, specs, quantity, purchase_quantity,
        link, estimated_cost, total_cost, remark
    ) VALUES (
        19, '内六角扳手套装', '2mm/2.5mm/3mm/4mm', 1, 1,
        'https://detail.tmall.com/item.htm?id=607014136588&skuId=5952411225101', 4.9, 4.9, 'N+1 零件包'
    )
""")
print("✅ SKU1: 添加了扳手套装（¥4.9）")

conn.commit()

# 验证结果
cursor.execute("SELECT part_name, quantity, estimated_cost FROM bom_items WHERE product_id = 19 ORDER BY id")
print("\n📋 SKU1 更新后的 BOM（扳手相关）:")
for row in cursor.fetchall():
    if '扳手' in row[0] or '螺丝' in row[0]:
        print(f"  - {row[0]}: {row[1]}个 - ¥{row[2]}")

# 计算并更新产品成本
cursor.execute("SELECT SUM(total_cost) FROM bom_items WHERE product_id = 19")
total_cost = cursor.fetchone()[0] or 0
print(f"\n💰 SKU1 BOM 总成本：¥{total_cost:.2f}")

cursor.execute("UPDATE products SET total_bom_cost = ? WHERE id = 19", (total_cost,))
conn.commit()
print("✅ SKU1 产品成本已同步")

conn.close()
print("\n✅ SKU1 BOM 更新完成！")
