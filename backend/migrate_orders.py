"""
订单表结构迁移脚本
将旧 orders 表（dealer 订单）迁移到新结构（客户订单）
创建时间：2026-04-05
"""
import sqlite3
from datetime import datetime

DB_PATH = 'n1_lab_v3.db'

def migrate_orders_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查是否已经是新结构
    cursor.execute("PRAGMA table_info(orders)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'customer_name' in columns:
        print("✅ 订单表已经是新结构，无需迁移")
        conn.close()
        return
    
    print("🔄 开始迁移订单表结构...")
    
    # 备份旧数据
    cursor.execute("SELECT * FROM orders")
    old_orders = cursor.fetchall()
    print(f"📦 备份了 {len(old_orders)} 条旧订单记录")
    
    # 创建新表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            customer_contact TEXT,
            order_type TEXT NOT NULL,
            product_id INTEGER,
            product_sku TEXT,
            product_name TEXT,
            quantity INTEGER DEFAULT 1,
            unit_price REAL,
            total_amount REAL,
            status TEXT DEFAULT 'pending',
            remark TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # 迁移旧数据（转换为新格式）
    for old in old_orders:
        # 旧结构：id, dealer_id, status, total_amount, created_at, order_no, shipping_company, tracking_no, shipping_time
        old_id, dealer_id, status, total_amount, created_at, order_no = old[0], old[1], old[2], old[3], old[4], old[5]
        
        # 获取经销商信息
        cursor.execute("SELECT company_name, contact_name, contact_phone FROM dealers WHERE id = ?", (dealer_id,))
        dealer = cursor.fetchone()
        
        if dealer:
            customer_name = dealer[0] or dealer[1] or "经销商客户"
            customer_contact = dealer[2] or ""
        else:
            customer_name = "经销商客户"
            customer_contact = ""
        
        # 获取订单项
        cursor.execute("SELECT product_id, quantity, price FROM order_items WHERE order_id = ?", (old_id,))
        items = cursor.fetchall()
        
        if items:
            product_id = items[0][0]
            quantity = items[0][1]
            unit_price = items[0][2]
            
            # 获取产品信息
            cursor.execute("SELECT sku_code, product_name FROM products WHERE id = ?", (product_id,))
            product = cursor.fetchone()
            
            product_sku = product[0] if product else ""
            product_name = product[1] if product else ""
            order_type = "kit"  # 默认零件包
        else:
            product_id = None
            product_sku = ""
            product_name = ""
            quantity = 1
            unit_price = total_amount
            order_type = "kit"
        
        # 插入新表
        try:
            cursor.execute('''
                INSERT INTO orders_new (
                    order_no, customer_name, customer_contact, order_type,
                    product_id, product_sku, product_name, quantity,
                    unit_price, total_amount, status, created_at, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
            ''', (
                order_no, customer_name, customer_contact, order_type,
                product_id, product_sku, product_name, quantity,
                unit_price, total_amount, status, created_at
            ))
        except sqlite3.IntegrityError:
            # 订单号重复，跳过
            print(f"⚠️  跳过重复订单号：{order_no}")
    
    # 删除旧表
    cursor.execute("DROP TABLE orders")
    
    # 重命名新表
    cursor.execute("ALTER TABLE orders_new RENAME TO orders")
    
    # 创建 order_items 表（如果不存在）
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            bom_item_id INTEGER,
            part_name TEXT,
            specification TEXT,
            quantity REAL,
            unit_price REAL,
            total_price REAL,
            taobao_link TEXT,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (bom_item_id) REFERENCES bom_items(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 订单表结构迁移完成！")

if __name__ == '__main__':
    migrate_orders_table()
