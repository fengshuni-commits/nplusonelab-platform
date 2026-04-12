"""
用户管理系统数据库初始化脚本
创建时间：2026-04-04
"""
import sqlite3
from datetime import datetime

DB_PATH = 'n1_lab_v3.db'

def create_users_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 创建用户表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'user',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_login TIMESTAMP,
            purchase_count INTEGER DEFAULT 0
        )
    ''')
    
    # 创建操作日志表
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            detail TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # 插入默认管理员账户（密码：admin123）
    import hashlib
    admin_password = hashlib.sha256('admin123'.encode()).hexdigest()
    
    try:
        cursor.execute('''
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
        ''', ('admin', admin_password, 'admin'))
        print("✅ 已创建默认管理员账户：admin / admin123")
    except sqlite3.IntegrityError:
        print("⚠️ 管理员账户已存在")
    
    conn.commit()
    conn.close()
    print("✅ 用户管理数据库表已创建")

if __name__ == '__main__':
    create_users_table()
