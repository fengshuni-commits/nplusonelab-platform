import pandas as pd
import sqlite3
import glob
import os
import re

def fix_dealer_data_v3():
    db_path = '/root/.openclaw/workspace/projects/n1-lab-automation/backend/n1_lab_v3.db'
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    bom_dir = '/root/.openclaw/workspace/xiaohongshu/products/BOM-0330/'
    files = glob.glob(os.path.join(bom_dir, '*.xlsx'))
    
    print("=" * 80)
    print("🛠️  Gemini 3 驱动：SKU 级模糊定价修复 (解决括号与空格问题)")
    print("=" * 80)
    
    for file in files:
        base_name = os.path.basename(file)
        prefix_match = re.match(r'([A-Z0-9]+)', base_name)
        if not prefix_match: continue
        prefix = prefix_match.group(1)
        
        try:
            excel = pd.ExcelFile(file)
            sheets = excel.sheet_names
            
            # 1. 内部成本映射 (来自第一个 Sheet)
            total_df = pd.read_excel(file, sheet_name=sheets[0])
            cost_col = next((c for c in total_df.columns if '成本' in str(c)), None)
            
            sku_to_n1_cost = {}
            for _, row in total_df.iterrows():
                # 清除标签中的括号和空格进行匹配
                raw_label = str(row.iloc[0]).strip()
                clean_label = re.sub(r'[\(\)（）\s]', '', raw_label)
                val = row[cost_col] if cost_col else 0
                sku_to_n1_cost[clean_label] = val

            # 2. 零件包成本映射 (来自明细 Sheets)
            sku_to_dealer_cost = {}
            for s_name in sheets[1:]:
                df = pd.read_excel(file, sheet_name=s_name)
                
                qty_col = next((c for c in df.columns if '采购数量' in str(c)), None)
                price_col = next((c for c in df.columns if '参考单价' in str(c) or '单价' in str(c)), None)
                remark_col = next((c for c in df.columns if '备注' in str(c)), None)
                
                if qty_col and price_col and remark_col:
                    # 关键逻辑：匹配时忽略空格
                    parts_df = df[df[remark_col].astype(str).str.replace(' ', '').str.contains('零件包', na=False)]
                    parts_cost = (parts_df[qty_col].astype(float) * parts_df[price_col].astype(float)).sum()
                    
                    clean_s_name = re.sub(r'[\(\)（）\s]', '', s_name.strip())
                    sku_to_dealer_cost[clean_s_name] = parts_cost

            # 3. 更新数据库
            cursor.execute("SELECT sku_code, product_name FROM products WHERE sku_code LIKE ?", (f'{prefix}%',))
            db_skus = cursor.fetchall()
            
            for db_sku_code, db_name in db_skus:
                clean_db_name = re.sub(r'[\(\)（）\s]', '', db_name)
                
                # 寻找匹配的 N1 成本
                n1_cost = 0
                for label, val in sku_to_n1_cost.items():
                    if label in clean_db_name or label in db_sku_code:
                        n1_cost = val
                        break
                
                # 寻找匹配的零件包成本
                d_cost = 0
                for s_name, val in sku_to_dealer_cost.items():
                    if s_name in clean_db_name or s_name in db_sku_code:
                        d_cost = val
                        break
                
                # 回退：单一 SKU 兜底
                if n1_cost == 0 and sku_to_n1_cost: n1_cost = list(sku_to_n1_cost.values())[0]
                if d_cost == 0 and sku_to_dealer_cost: d_cost = list(sku_to_dealer_cost.values())[0]

                dealer_price = d_cost * 1.5
                
                # 调试打印，特别是解决 0 元问题的 SKU
                status = "✅" if dealer_price > 0 else "⚠️"
                print(f"{status} {db_sku_code:<15} | 内部成本: ¥{n1_cost:>8.2f} | 零件包售价: ¥{dealer_price:>8.2f}")
                
                cursor.execute("""
                    UPDATE products 
                    SET n1_price = ?, dealer_price = ? 
                    WHERE sku_code = ?
                """, (float(n1_cost), float(dealer_price), db_sku_code))

        except Exception as e:
            print(f"❌ 文件 {base_name} 出错: {e}")

    conn.commit()
    conn.close()
    print("=" * 80)
    print("✨ 全量 SKU 调价修复完成！")

if __name__ == "__main__":
    fix_dealer_data_v3()
