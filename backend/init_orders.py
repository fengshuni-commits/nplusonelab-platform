"""
订单管理系统数据库初始化脚本
创建时间：2026-04-04
"""
import sqlite3

DB_PATH = 'n1_lab_v3.db'

def create_orders_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建订单表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT UNIQUE NOT NULL,
            customer_name TEXT NOT NULL,
            customer_contact TEXT,
            order_type TEXT NOT NULL,  -- 'kit' 零件包 或 'complete' 整体产品
            product_id INTEGER,
            product_sku TEXT,
            product_name TEXT,
            quantity INTEGER DEFAULT 1,
            unit_price REAL,
            total_amount REAL,
            status TEXT DEFAULT 'pending',  -- pending/processing/completed/cancelled
            remark TEXT,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    
    # 创建订单明细表（关联 BOM）
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
            status TEXT DEFAULT 'pending',  -- pending/purchased/received
            FOREIGN KEY (order_id) REFERENCES orders(id),
            FOREIGN KEY (bom_item_id) REFERENCES bom_items(id)
        )
    ''')
    
    conn.commit()
    conn.close()
    print("✅ 订单管理数据库表已创建")

if __name__ == '__main__':
    create_orders_table()
