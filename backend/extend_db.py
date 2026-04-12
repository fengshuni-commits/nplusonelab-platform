"""扩展数据库字段"""
import sqlite3

DB_PATH = "n1_lab_v3.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# 扩展 Dealer 表
dealer_columns = [
    "business_license TEXT",
    "tax_id TEXT",
    "invoice_title TEXT",
    "invoice_address TEXT",
    "shipping_address TEXT",
    "shipping_contact TEXT",
    "shipping_phone TEXT"
]

for col in dealer_columns:
    try:
        cursor.execute(f"ALTER TABLE dealers ADD COLUMN {col}")
        print(f"✅ 添加字段：{col}")
    except Exception as e:
        print(f"⚠️  {col} 可能已存在：{e}")

# 扩展 Order 表
order_columns = [
    "order_no TEXT",
    "shipping_company TEXT",
    "tracking_no TEXT",
    "shipping_time TIMESTAMP"
]

for col in order_columns:
    try:
        cursor.execute(f"ALTER TABLE orders ADD COLUMN {col}")
        print(f"✅ 添加字段：{col}")
    except Exception as e:
        print(f"⚠️  {col} 可能已存在：{e}")

conn.commit()
conn.close()
print("\n✅ 数据库扩展完成！")
