import pandas as pd
import sqlite3
import glob
import os
import re

def calculate_dealer_prices():
    db_path = '/root/.openclaw/workspace/projects/n1-lab-automation/backend/n1_lab_v3.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    bom_dir = '/root/.openclaw/workspace/xiaohongshu/products/BOM-0330/'
    files = glob.glob(os.path.join(bom_dir, '*.xlsx'))
    
    print("=" * 80)
    print("🚀 重新核算经销商零件包售价 (公式: 零件包成本 * 1.5)")
    print("=" * 80)
    
    for file in files:
        base_name = os.path.basename(file)
        prefix_match = re.match(r'([A-Z0-9]+)', base_name)
        if not prefix_match: continue
        prefix = prefix_match.group(1)
        
        try:
            excel = pd.ExcelFile(file)
            
            # 1. 获取内部总成本 (来自第一个 Sheet)
            total_df = pd.read_excel(file, sheet_name=excel.sheet_names[0])
            cost_col = next((c for c in total_df.columns if '成本' in str(c)), None)
            
            # 建立 SKU 与总成本的映射
            total_costs_by_sku = {}
            for _, row in total_df.iterrows():
                sku_label = str(row.iloc[0])
                cost_val = row[cost_col] if cost_col else 0
                total_costs_by_sku[sku_label] = cost_val
                
            # 2. 计算零件包成本 (遍历物料清单 Sheet)
            dealer_part_costs = {}
            for sheet_name in excel.sheet_names[1:]:
                df = pd.read_excel(file, sheet_name=sheet_name)
                
                qty_col = next((c for c in df.columns if '采购数量' in str(c)), None)
                price_col = next((c for c in df.columns if '参考单价' in str(c) or '单价' in str(c)), None)
                remark_col = next((c for c in df.columns if '备注' in str(c)), None)
                
                if qty_col and price_col and remark_col:
                    # 筛选备注包含 "N+1 零件包" 的行
                    parts_df = df[df[remark_col].astype(str).str.contains('零件包', na=False)]
                    parts_sum = (parts_df[qty_col].astype(float) * parts_df[price_col].astype(float)).sum()
                    dealer_part_costs[sheet_name] = parts_sum

            # 3. 更新数据库
            for sku_label, total_cost in total_costs_by_sku.items():
                # 模糊匹配数据库中的产品
                cursor.execute("SELECT sku_code, product_name FROM products WHERE product_name LIKE ? OR sku_code LIKE ?", 
                             (f'%{sku_label}%', f'{prefix}%'))
                sku_results = cursor.fetchall()

                for sku_code, prod_name in sku_results:
                    # 匹配零件包成本
                    p_cost = 0
                    # 尝试精确匹配或包含匹配
                    for s_name, c_val in dealer_part_costs.items():
                        if s_name in sku_label or sku_label in s_name or s_name in prod_name:
                            p_cost = c_val
                            break
                    
                    if p_cost == 0 and dealer_part_costs:
                        p_cost = list(dealer_part_costs.values())[0]

                    # 执行公式: 零件包售价 = 零件包成本 * 1.5
                    dealer_price = p_cost * 1.5
                    
                    print(f"✅ {sku_code:<12} | {prod_name[:20]:<20} | 零件包成本: ¥{p_cost:>8.2f} | 售价(x1.5): ¥{dealer_price:>8.2f}")
                    
                    cursor.execute("""
                        UPDATE products 
                        SET n1_price = ?, dealer_price = ? 
                        WHERE sku_code = ?
                    """, (float(total_cost), float(dealer_price), sku_code))

        except Exception as e:
            print(f"❌ 处理文件 {base_name} 出错: {e}")

    conn.commit()
    conn.close()
    print("=" * 80)
    print("✨ 数据库已更新：'n1_price' 为内部总成本，'dealer_price' 为零件包售价。")

if __name__ == "__main__":
    calculate_dealer_prices()
