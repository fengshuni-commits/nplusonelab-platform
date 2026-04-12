"""
添加零件包库存字段到 products 表
执行时间：2026-04-04
"""
import sqlite3

DB_PATH = 'n1_lab_v3.db'

def add_kit_stock_column():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 检查字段是否已存在
    cursor.execute("PRAGMA table_info(products)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'kit_stock_quantity' in columns:
        print("✅ kit_stock_quantity 字段已存在")
    else:
        # 添加零件包库存字段
        cursor.execute('''
            ALTER TABLE products 
            ADD COLUMN kit_stock_quantity INTEGER DEFAULT 0
        ''')
        print("✅ 已添加 kit_stock_quantity 字段")
        
        # 将现有库存数据同步到零件包库存
        cursor.execute('''
            UPDATE products 
            SET kit_stock_quantity = stock_quantity 
            WHERE stock_quantity IS NOT NULL
        ''')
        print("✅ 已将现有库存数据同步到零件包库存")
    
    conn.commit()
    conn.close()
    print("✅ 数据库迁移完成")

if __name__ == '__main__':
    add_kit_stock_column()
