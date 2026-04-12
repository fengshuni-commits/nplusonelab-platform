"""
更新工作桌 BOM - 将 4 个内六角扳手换成扳手套装
"""
import sqlite3

DB_PATH = 'n1_lab_v3.db'

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 删除 4 个内六角扳手
cursor.execute("DELETE FROM bom_items WHERE product_id = 20 AND part_name LIKE '%内六角扳手%'")
deleted = cursor.rowcount
print(f"✅ 删除了 {deleted} 个内六角扳手")

# 添加扳手套装
cursor.execute("""
    INSERT INTO bom_items (
        product_id, part_name, specs, quantity, purchase_quantity,
        link, estimated_cost, total_cost, remark
    ) VALUES (
        20, '内六角扳手套装', '2mm/2.5mm/3mm/4mm', 1, 1,
        'https://detail.tmall.com/item.htm?id=607014136588&skuId=5952411225101', 4.9, 4.9, 'N+1 零件包'
    )
""")
print("✅ 添加了扳手套装（¥4.9）")

conn.commit()

# 验证结果
cursor.execute("SELECT part_name, quantity, estimated_cost FROM bom_items WHERE product_id = 20 ORDER BY id")
print("\n📋 更新后的 BOM（部分）:")
for row in cursor.fetchall():
    if '扳手' in row[0] or '螺丝' in row[0]:
        print(f"  - {row[0]}: {row[1]}个 - ¥{row[2]}")

conn.close()
print("\n✅ BOM 更新完成！")
