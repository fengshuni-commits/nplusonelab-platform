"""
批量更新零件包售价
公式：零件包售价 = 零件包成本 × 1.5
执行时间：2026-04-04
"""
import sqlite3

DB_PATH = 'n1_lab_v3.db'

def update_dealer_prices():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 查询所有产品
    cursor.execute('''
        SELECT id, sku_code, product_name, kit_cost, dealer_price
        FROM products
        ORDER BY id
    ''')
    
    products = cursor.fetchall()
    
    print("=" * 100)
    print("批量更新零件包售价（公式：成本 × 1.5）\n")
    print(f"{'SKU':<20} {'产品名称':<25} {'成本':<10} {'原售价':<10} {'新售价':<10} {'变化':<10}")
    print("-" * 100)
    
    updated_count = 0
    
    for pid, sku, name, kit_cost, old_dealer_price in products:
        # 计算新价格
        if kit_cost and kit_cost > 0:
            new_dealer_price = round(kit_cost * 1.5, 2)
        else:
            new_dealer_price = 0
        
        # 更新数据库
        cursor.execute('''
            UPDATE products
            SET dealer_price = ?
            WHERE id = ?
        ''', (new_dealer_price, pid))
        
        # 显示变化
        old_display = f"¥{old_dealer_price:.2f}" if old_dealer_price else "NULL"
        new_display = f"¥{new_dealer_price:.2f}"
        change = new_dealer_price - (old_dealer_price or 0)
        change_display = f"{'+' if change >= 0 else ''}¥{change:.2f}"
        
        cost_display = f"¥{kit_cost:.2f}" if kit_cost else "NULL"
        print(f"{sku:<20} {name[:25]:<25} {cost_display:<10} {old_display:<10} {new_display:<10} {change_display:<10}")
        
        updated_count += 1
    
    print("-" * 100)
    print(f"✅ 共更新 {updated_count} 个产品的零件包售价")
    
    conn.commit()
    conn.close()
    
    # 统计信息
    print("\n📊 价格统计：")
    print("=" * 100)

if __name__ == '__main__':
    update_dealer_prices()
