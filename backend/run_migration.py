#!/usr/bin/env python3
"""
N+1 LAB 订单管理功能升级 - 数据库迁移脚本
执行 migrate_orders_v4.sql 中的迁移
"""

import sqlite3
from datetime import datetime

DB_PATH = "n1_lab_v3.db"
SQL_FILE = "migrate_orders_v4.sql"

def run_migration():
    print(f"🔧 开始数据库迁移...")
    print(f"数据库：{DB_PATH}")
    print(f"迁移脚本：{SQL_FILE}")
    print("=" * 60)
    
    # 读取 SQL 文件
    with open(SQL_FILE, 'r', encoding='utf-8') as f:
        sql_script = f.read()
    
    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 执行迁移（过滤掉注释和 SELECT 语句）
        statements = sql_script.split(';')
        
        executed = 0
        for stmt in statements:
            stmt = stmt.strip()
            # 跳过空语句、注释和 SELECT
            if not stmt or stmt.startswith('--') or stmt.upper().startswith('SELECT'):
                continue
            
            # 执行 DDL 语句
            if stmt.upper().startswith(('ALTER', 'CREATE', 'INSERT', 'UPDATE', 'DELETE')):
                try:
                    cursor.execute(stmt)
                    executed += 1
                    print(f"✅ 执行：{stmt[:60]}...")
                except Exception as e:
                    # 忽略已存在的错误（如字段已存在）
                    if 'duplicate' not in str(e).lower() and 'already exists' not in str(e).lower():
                        print(f"⚠️ 跳过：{stmt[:60]}... - {e}")
        
        conn.commit()
        print("=" * 60)
        print(f"✅ 迁移完成！共执行 {executed} 条语句")
        
        # 验证迁移结果
        print("\n📊 验证迁移结果：")
        
        # 检查新表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"表：{', '.join(tables)}")
        
        # 检查 orders 表结构
        cursor.execute("PRAGMA table_info(orders)")
        columns = [row[1] for row in cursor.fetchall()]
        print(f"orders 表字段：{len(columns)} 个")
        
        # 检查新字段
        new_fields = ['kit_id', 'kit_quantity', 'procurement_cost', 'shipping_company', 'tracking_no']
        for field in new_fields:
            if field in columns:
                print(f"  ✅ {field}")
            else:
                print(f"  ❌ {field} (缺失)")
        
        # 检查新表
        for table in ['procurement_lists', 'kit_allocations', 'order_logs']:
            if table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"  ✅ {table} ({count} 条记录)")
            else:
                print(f"  ❌ {table} (缺失)")
        
    except Exception as e:
        print(f"❌ 迁移失败：{e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    run_migration()
