import sqlite3

conn = sqlite3.connect('/root/.openclaw/workspace/projects/n1-lab-automation/backend/n1_lab_v2.db')
cursor = conn.execute('SELECT id, contact_phone, company_name, status FROM dealers LIMIT 5')
for row in cursor:
    print(row)
conn.close()
