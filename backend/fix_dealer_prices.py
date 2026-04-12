import pandas as pd
import sqlite3
import glob
import os
import re

def calculate_dealer_prices():
    conn = sqlite3.connect('/root/.openclaw/workspace/projects/n1-lab-automation/backend/n1_lab_v3.db')
    cursor = conn.cursor()
    
    bom_dir = '/root/.openclaw/workspace/xiaohongshu/products/BOM-0330/'
    files = glob.glob(os.path.join(bom_dir, '*.xlsx'))
    
    mapping = {
        'AP2501': 'AP2501',
        'AP2503': 'AP2503',
        'AP2402': 'AP2402',
        'AP2403': 'AP2403',
        'AP2502': 'AP2502',
        'AP2401': 'AP2401',
        'A2504': 'A2504'
    }
    
    print("开始重新计算零件包售价...")
    
    for file in files:
        base_name = os.path.basename(file)
        prefix_match = re.match(r'([A-Z0-9]+)', base_name)
        if not prefix_match: continue
        prefix = prefix_match.group(1)
        
        excel = pd.ExcelFile(file)
        
        # 1. 获取内部总成本 (来自第一个 Sheet)
        total_df = pd.read_excel(file, sheet_name=excel.sheet_names[0])
        cost_col = next((c for c in total_df.columns if '成本' in c), None)
        
        # 2. 计算零件包售价 (遍历所有明细 Sheet)
        dealer_prices_by_sku = {}
        total_costs_by_sku = {}
        
        # 假设总表里列出了 SKU 对应的总成本
        for _, row in total_df.iterrows():
            sku_label = str(row[0])
            cost_val = row[cost_col] if cost_col else 0
            total_costs_by_sku[sku_label] = cost_val
            
        # 遍历物料清单 Sheet 计算零件包
        for sheet_name in excel.sheet_names[1:]:
            df = pd.read_excel(file, sheet_name=sheet_name)
            
            # 查找必要的列
            qty_col = next((c for c in df.columns if '采购数量' in str(c)), None)
            price_col = next((c for c in df.columns if '参考单价' in str(c) or '单价' in str(c)), None)
            remark_col = next((c for c in df.columns if '备注' in str(c)), None)
            
            if qty_col and price_col and remark_col:
                # 筛选备注包含 "N+1 零件包" 的行
                parts_df = df[df[remark_col].astype(str).str.contains('零件包', na=False)]
                parts_sum = (parts_df[qty_col].astype(float) * parts_df[price_col].astype(float)).sum()
                dealer_prices_by_sku[sheet_name] = parts_sum

        # 更新数据库
        for sku_label, total_cost in total_costs_by_sku.items():
            # 模糊匹配 SKU
            cursor.execute("SELECT sku_code FROM products WHERE product_name LIKE ?", (f'%{sku_label}%',))
            sku_codes = cursor.fetchall()
            
            # 如果没找到，按前缀匹配
            if not sku_codes:
                cursor.execute("SELECT sku_code FROM products WHERE sku_code LIKE ?", (f'{prefix}%',))
                sku_codes = cursor.fetchall()

            for (sku_code,) in sku_codes:
                # 尝试匹配具体的 dealer_price
                # 有些 Sheet 名字和 SKU 对应
                d_price = 0
                for s_name, p_val in dealer_prices_by_sku.items():
                    if s_name in sku_label or sku_label in s_name:
                        d_price = p_val
                        break
                
                if d_price == 0 and dealer_prices_by_sku:
                    # 如果只有一个零件包数据，就用那个
                    d_price = list(dealer_prices_by_sku.values())[0]

                print(f"更新 {sku_code}: 内部成本={total_cost}, 零件包售价={d_price}")
                cursor.execute("""
                    UPDATE products 
                    SET n1_price = ?, dealer_price = ? 
                    WHERE sku_code = ?
                """, (float(total_cost), float(d_price), sku_code))

    conn.commit()
    conn.close()
    print("完成！")

if __name__ == "__main__":
    calculate_dealer_prices()
