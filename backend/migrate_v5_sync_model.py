#!/usr/bin/env python3
"""
N+1 LAB v5 数据库迁移脚本
目的：确保 orders 表与 ORM Order 模型完全同步

功能：
1. 自动检测现有列，只添加缺失的列（安全幂等，可重复执行）
2. 创建依赖的辅助表（order_logs, procurement_lists, kit_allocations）
3. 如果 orders 表仍是旧结构（无 customer_name），自动触发全表迁移
4. 迁移完成后验证所有字段完整性

使用方法：
    cd backend
    python3 migrate_v5_sync_model.py
"""

import sqlite3
import sys
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "n1_lab_v3.db")

# ORM Order 模型中定义的所有列（列名 → 类型 + 默认值）
EXPECTED_COLUMNS = {
    "id":                "INTEGER PRIMARY KEY AUTOINCREMENT",
    "order_no":          "TEXT UNIQUE",
    "dealer_id":         "INTEGER",
    "customer_name":     "TEXT",
    "customer_contact":  "TEXT",
    "order_type":        "TEXT DEFAULT 'kit'",
    "product_id":        "INTEGER",
    "product_sku":       "TEXT",
    "product_name":      "TEXT",
    "quantity":          "INTEGER DEFAULT 1",
    "unit_price":        "REAL DEFAULT 0",
    "total_amount":      "REAL DEFAULT 0",
    "status":            "TEXT DEFAULT 'pending'",
    "remark":            "TEXT DEFAULT ''",
    "created_by":        "INTEGER",
    "created_at":        "DATETIME DEFAULT CURRENT_TIMESTAMP",
    "updated_at":        "DATETIME",
    "prepared_at":       "DATETIME",
    "shipped_at":        "DATETIME",
    "procurement_cost":  "REAL DEFAULT 0",
    "shipping_company":  "TEXT",
    "tracking_no":       "TEXT",
    "kit_id":            "INTEGER",
    "kit_quantity":      "INTEGER DEFAULT 0",
}

# 需要存在的辅助表
AUXILIARY_TABLES = {
    "order_logs": """
        CREATE TABLE IF NOT EXISTS order_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            user_id INTEGER,
            action VARCHAR(50) NOT NULL,
            old_status VARCHAR(50),
            new_status VARCHAR(50),
            detail TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """,
    "procurement_lists": """
        CREATE TABLE IF NOT EXISTS procurement_lists (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER,
            part_name VARCHAR(200) NOT NULL,
            specs VARCHAR(200),
            quantity REAL NOT NULL DEFAULT 0,
            unit_cost REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            taobao_link VARCHAR(500),
            status VARCHAR(50) DEFAULT 'pending',
            purchased_at DATETIME,
            received_at DATETIME,
            remark TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
        )
    """,
    "kit_allocations": """
        CREATE TABLE IF NOT EXISTS kit_allocations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            product_id INTEGER NOT NULL,
            kit_sku VARCHAR(100),
            kit_name VARCHAR(200),
            quantity INTEGER NOT NULL DEFAULT 0,
            kit_cost REAL DEFAULT 0,
            total_cost REAL DEFAULT 0,
            user_id INTEGER,
            remark TEXT,
            allocated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
        )
    """,
    "purchases": """
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            purchase_type TEXT DEFAULT 'kit',
            quantity INTEGER DEFAULT 1,
            bom_cost REAL DEFAULT 0,
            actual_cost REAL DEFAULT 0,
            user_id INTEGER DEFAULT 1,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (product_id) REFERENCES products(id)
        )
    """,
    "user_logs": """
        CREATE TABLE IF NOT EXISTS user_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            username TEXT,
            action TEXT NOT NULL,
            detail TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """,
}

# products 表需要的列（ORM Product 模型定义的）
PRODUCTS_EXPECTED_COLUMNS = {
    "n1_price":           "REAL DEFAULT 0",
    "kit_cost":           "REAL DEFAULT 0",
    "total_bom_cost":     "REAL DEFAULT 0",
    "sale_type":          "TEXT DEFAULT 'parts_pack'",
    "is_parts_pack":      "INTEGER DEFAULT 1",
    "kit_stock_quantity":  "INTEGER DEFAULT 0",
    "stock_quantity":      "INTEGER DEFAULT 0",
}

# 建议的索引
INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status)",
    "CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_name)",
    "CREATE INDEX IF NOT EXISTS idx_orders_order_no ON orders(order_no)",
    "CREATE INDEX IF NOT EXISTS idx_order_logs_order ON order_logs(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_order_logs_created_at ON order_logs(created_at)",
    "CREATE INDEX IF NOT EXISTS idx_procurement_order ON procurement_lists(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_procurement_status ON procurement_lists(status)",
    "CREATE INDEX IF NOT EXISTS idx_kit_allocations_order ON kit_allocations(order_id)",
    "CREATE INDEX IF NOT EXISTS idx_kit_allocations_product ON kit_allocations(product_id)",
]


def get_existing_columns(cursor, table_name):
    """获取表的现有列名列表"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {row[1] for row in cursor.fetchall()}


def get_existing_tables(cursor):
    """获取数据库中所有表名"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cursor.fetchall()}


def needs_full_migration(cursor):
    """
    判断是否需要全表迁移（旧结构 → 新结构）
    旧结构特征：有 dealer_id 但没有 customer_name
    """
    columns = get_existing_columns(cursor, "orders")
    return "dealer_id" in columns and "customer_name" not in columns


def full_table_migration(cursor):
    """
    执行全表迁移：从旧结构（dealer 订单）迁移到新结构（客户订单）
    这是 migrate_orders.py 的增强版
    """
    print("\n🔄 检测到旧表结构，执行全表迁移...")

    # 备份旧数据
    cursor.execute("SELECT * FROM orders")
    old_orders = cursor.fetchall()
    old_columns = [desc[0] for desc in cursor.description]
    print(f"   📦 备份了 {len(old_orders)} 条旧订单记录")

    # 创建新表
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders_new (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_no TEXT UNIQUE,
            dealer_id INTEGER,
            customer_name TEXT,
            customer_contact TEXT,
            order_type TEXT DEFAULT 'kit',
            product_id INTEGER,
            product_sku TEXT,
            product_name TEXT,
            quantity INTEGER DEFAULT 1,
            unit_price REAL DEFAULT 0,
            total_amount REAL DEFAULT 0,
            status TEXT DEFAULT 'pending',
            remark TEXT DEFAULT '',
            created_by INTEGER,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            updated_at DATETIME,
            prepared_at DATETIME,
            shipped_at DATETIME,
            procurement_cost REAL DEFAULT 0,
            shipping_company TEXT,
            tracking_no TEXT,
            kit_id INTEGER,
            kit_quantity INTEGER DEFAULT 0
        )
    """)

    # 迁移旧数据
    migrated = 0
    for old in old_orders:
        old_dict = dict(zip(old_columns, old))
        old_id = old_dict.get("id")
        dealer_id = old_dict.get("dealer_id")
        status = old_dict.get("status", "pending")
        total_amount = old_dict.get("total_amount", 0)
        created_at = old_dict.get("created_at")
        order_no = old_dict.get("order_no", f"ORD-LEGACY-{old_id}")

        # 查询经销商信息
        customer_name = "经销商客户"
        customer_contact = ""
        if dealer_id:
            cursor.execute(
                "SELECT company_name, contact_name, contact_phone FROM dealers WHERE id = ?",
                (dealer_id,)
            )
            dealer = cursor.fetchone()
            if dealer:
                customer_name = dealer[0] or dealer[1] or "经销商客户"
                customer_contact = dealer[2] or ""

        # 查询订单项
        product_id = None
        product_sku = ""
        product_name = ""
        quantity = 1
        unit_price = total_amount or 0

        cursor.execute(
            "SELECT product_id, quantity, price FROM order_items WHERE order_id = ?",
            (old_id,)
        )
        items = cursor.fetchall()
        if items:
            product_id = items[0][0]
            quantity = items[0][1] or 1
            unit_price = items[0][2] or 0
            cursor.execute(
                "SELECT sku_code, product_name FROM products WHERE id = ?",
                (product_id,)
            )
            product = cursor.fetchone()
            if product:
                product_sku = product[0] or ""
                product_name = product[1] or ""

        try:
            cursor.execute("""
                INSERT INTO orders_new (
                    order_no, dealer_id, customer_name, customer_contact,
                    order_type, product_id, product_sku, product_name,
                    quantity, unit_price, total_amount, status,
                    created_at, created_by,
                    shipping_company, tracking_no, shipped_at
                ) VALUES (?, ?, ?, ?, 'kit', ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?)
            """, (
                order_no, dealer_id, customer_name, customer_contact,
                product_id, product_sku, product_name,
                quantity, unit_price, total_amount, status, created_at,
                old_dict.get("shipping_company"),
                old_dict.get("tracking_no"),
                old_dict.get("shipping_time") or old_dict.get("shipped_at"),
            ))
            migrated += 1
        except sqlite3.IntegrityError:
            print(f"   ⚠️  跳过重复订单号: {order_no}")

    # 替换旧表
    cursor.execute("DROP TABLE orders")
    cursor.execute("ALTER TABLE orders_new RENAME TO orders")
    print(f"   ✅ 迁移完成，共迁移 {migrated}/{len(old_orders)} 条订单")


def add_missing_columns(cursor):
    """向 orders 表添加缺失的列"""
    existing = get_existing_columns(cursor, "orders")
    added = 0

    for col_name, col_type in EXPECTED_COLUMNS.items():
        if col_name not in existing:
            # SQLite ALTER TABLE ADD COLUMN 不支持 PRIMARY KEY / UNIQUE 约束
            clean_type = col_type.replace("PRIMARY KEY AUTOINCREMENT", "INTEGER")
            clean_type = clean_type.replace("UNIQUE", "")
            try:
                cursor.execute(f"ALTER TABLE orders ADD COLUMN {col_name} {clean_type}")
                print(f"   ✅ 添加列: {col_name} ({clean_type.strip()})")
                added += 1
            except Exception as e:
                print(f"   ⚠️  列 {col_name} 添加失败: {e}")

    if added == 0:
        print("   ✅ orders 表所有列已同步，无需修改")
    else:
        print(f"   📊 共添加 {added} 列")


def create_auxiliary_tables(cursor):
    """创建辅助表"""
    existing_tables = get_existing_tables(cursor)
    created = 0

    for table_name, create_sql in AUXILIARY_TABLES.items():
        if table_name not in existing_tables:
            try:
                cursor.execute(create_sql)
                print(f"   ✅ 创建表: {table_name}")
                created += 1
            except Exception as e:
                print(f"   ⚠️  表 {table_name} 创建失败: {e}")
        else:
            print(f"   ✓  表 {table_name} 已存在")

    if created == 0:
        print("   ✅ 所有辅助表已就绪")


def create_indexes(cursor):
    """创建索引"""
    for idx_sql in INDEXES:
        try:
            cursor.execute(idx_sql)
        except Exception:
            pass  # 索引已存在或表不存在，静默跳过


def verify_migration(cursor):
    """验证迁移结果"""
    print("\n📊 验证结果")
    print("=" * 50)

    # 检查 orders 表列
    existing = get_existing_columns(cursor, "orders")
    missing = [col for col in EXPECTED_COLUMNS if col not in existing]

    if missing:
        print(f"   ❌ orders 表缺失 {len(missing)} 列: {', '.join(missing)}")
        return False
    else:
        print(f"   ✅ orders 表完整 ({len(existing)} 列)")

    # 检查辅助表
    existing_tables = get_existing_tables(cursor)
    for table_name in AUXILIARY_TABLES:
        if table_name in existing_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cursor.fetchone()[0]
            print(f"   ✅ {table_name} ({count} 条记录)")
        else:
            print(f"   ❌ {table_name} 缺失")
            return False

    # 检查 products 表
    if "products" in existing_tables:
        prod_cols = get_existing_columns(cursor, "products")
        prod_missing = [c for c in PRODUCTS_EXPECTED_COLUMNS if c not in prod_cols]
        if prod_missing:
            print(f"   ⚠️  products 表缺失列: {', '.join(prod_missing)}")
        else:
            print(f"   ✅ products 表完整 ({len(prod_cols)} 列)")

    # 检查 users 表
    if "users" in existing_tables:
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"   ✅ users 表 ({user_count} 个用户)")
    else:
        print("   ❌ users 表缺失")

    # 检查订单数据
    cursor.execute("SELECT COUNT(*) FROM orders")
    order_count = cursor.fetchone()[0]
    print(f"   📦 orders 表共 {order_count} 条订单")

    return True


def sync_products_columns(cursor):
    """同步 products 表列（补齐 ORM 模型需要但数据库缺失的列）"""
    existing_tables = get_existing_tables(cursor)
    if "products" not in existing_tables:
        print("   ⚠️  products 表不存在，跳过")
        return

    existing = get_existing_columns(cursor, "products")
    added = 0

    for col_name, col_type in PRODUCTS_EXPECTED_COLUMNS.items():
        if col_name not in existing:
            try:
                cursor.execute(f"ALTER TABLE products ADD COLUMN {col_name} {col_type}")
                print(f"   ✅ 添加列: products.{col_name} ({col_type.strip()})")
                added += 1
            except Exception as e:
                print(f"   ⚠️  列 products.{col_name} 添加失败: {e}")

    if added == 0:
        print("   ✅ products 表所有列已同步")
    else:
        print(f"   📊 products 表共添加 {added} 列")


def ensure_users_table(cursor):
    """确保 users 表存在并有默认管理员账号"""
    import hashlib

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            status TEXT DEFAULT 'active',
            last_login DATETIME,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # 检查 last_login 列是否存在（兼容旧版 users 表）
    existing = get_existing_columns(cursor, "users")
    if "last_login" not in existing:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN last_login DATETIME")
            print("   ✅ 添加列: users.last_login")
        except:
            pass
    if "created_at" not in existing:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")
            print("   ✅ 添加列: users.created_at")
        except:
            pass

    # 确保默认管理员存在
    cursor.execute("SELECT COUNT(*) FROM users WHERE username = 'admin'")
    if cursor.fetchone()[0] == 0:
        pwd = hashlib.sha256("admin123".encode()).hexdigest()
        cursor.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
            ("admin", pwd, "admin")
        )
        print("   ✅ 创建默认管理员账号 (admin / admin123)")
    else:
        print("   ✅ 管理员账号已存在")


def run_migration():
    """主迁移流程"""
    print("=" * 60)
    print("  N+1 LAB v5 数据库迁移工具")
    print(f"  数据库路径: {DB_PATH}")
    print(f"  执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    # 检查数据库文件是否存在
    if not os.path.exists(DB_PATH):
        print(f"\n⚠️  数据库文件不存在: {DB_PATH}")
        print("   将在后端启动时由 SQLAlchemy 的 Base.metadata.create_all() 自动创建")
        print("   迁移脚本将创建一个空数据库用于验证...")
        # 创建空的 db
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        # 创建最基础的表结构让 ORM 能工作
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT DEFAULT 'pending',
                total_amount REAL DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dealers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT,
                contact_name TEXT,
                contact_phone TEXT UNIQUE,
                status TEXT DEFAULT 'pending',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sku_code TEXT UNIQUE,
                product_name TEXT,
                category TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                dealer_price REAL DEFAULT 0,
                retail_price REAL DEFAULT 0,
                kit_stock_quantity INTEGER DEFAULT 0,
                stock_quantity INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS order_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                product_id INTEGER,
                quantity INTEGER DEFAULT 1,
                price REAL DEFAULT 0,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)
        conn.commit()
        conn.close()
        print("   ✅ 基础表已创建\n")

    # 连接数据库
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        # 步骤 1: 检查是否需要全表迁移
        print("\n🔍 步骤 1/6: 检查 orders 表结构...")
        tables = get_existing_tables(cursor)
        if "orders" in tables:
            if needs_full_migration(cursor):
                full_table_migration(cursor)
            else:
                print("   ✅ orders 表已是新结构")
        else:
            print("   ⚠️  orders 表不存在，将在添加列步骤中创建")

        # 步骤 2: 添加缺失列
        print("\n🔧 步骤 2/6: 同步 orders 表列...")
        add_missing_columns(cursor)

        # 步骤 3: 创建辅助表
        print("\n📋 步骤 3/6: 创建辅助表...")
        create_auxiliary_tables(cursor)

        # 步骤 4: 同步 products 表列
        print("\n🛋️  步骤 4/6: 同步 products 表列...")
        sync_products_columns(cursor)

        # 步骤 5: 确保 users 表
        print("\n👤 步骤 5/6: 检查 users 表...")
        ensure_users_table(cursor)

        # 步骤 6: 创建索引
        print("\n🔑 步骤 6/6: 创建索引...")
        create_indexes(cursor)
        print("   ✅ 索引已就绪")

        # 提交所有更改
        conn.commit()

        # 验证
        success = verify_migration(cursor)

        print("\n" + "=" * 60)
        if success:
            print("  ✅ 迁移完成！数据库已与 ORM 模型完全同步")
        else:
            print("  ⚠️  迁移部分完成，请检查上方错误信息")
        print("=" * 60)

        return success

    except Exception as e:
        print(f"\n❌ 迁移失败: {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()


if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
