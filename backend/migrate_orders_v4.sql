-- N+1 LAB 订单管理功能升级 - 数据库迁移脚本
-- 创建时间：2026-04-12
-- 版本：v4.0

-- ==================== 1. 订单表升级 ====================

-- 新增字段
ALTER TABLE orders ADD COLUMN kit_id INTEGER;  -- 调用的零件包产品 ID
ALTER TABLE orders ADD COLUMN kit_quantity INTEGER DEFAULT 0;  -- 零件包调用数量
ALTER TABLE orders ADD COLUMN procurement_cost FLOAT DEFAULT 0;  -- 采购成本（实际支出）
ALTER TABLE orders ADD COLUMN shipping_cost FLOAT DEFAULT 0;  -- 运费
ALTER TABLE orders ADD COLUMN shipping_company VARCHAR(100);  -- 快递公司
ALTER TABLE orders ADD COLUMN tracking_no VARCHAR(100);  -- 快递单号
ALTER TABLE orders ADD COLUMN shipped_at DATETIME;  -- 发货时间
ALTER TABLE orders ADD COLUMN prepared_at DATETIME;  -- 备货完成时间
ALTER TABLE orders ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;  -- 最后更新时间

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders(created_at);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_name);

-- ==================== 2. 创建采购清单表 ====================

CREATE TABLE IF NOT EXISTS procurement_lists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER,  -- 关联的产品 ID（可选）
    part_name VARCHAR(200) NOT NULL,  -- 零件名称
    specs VARCHAR(200),  -- 规格型号
    quantity FLOAT NOT NULL DEFAULT 0,  -- 采购数量
    unit_cost FLOAT DEFAULT 0,  -- 单价
    total_cost FLOAT DEFAULT 0,  -- 总价
    taobao_link VARCHAR(500),  -- 淘宝链接
    status VARCHAR(50) DEFAULT 'pending',  -- pending | purchased | received
    purchased_at DATETIME,  -- 采购完成时间
    received_at DATETIME,  -- 到货时间
    remark TEXT,  -- 备注
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_procurement_order ON procurement_lists(order_id);
CREATE INDEX IF NOT EXISTS idx_procurement_status ON procurement_lists(status);

-- ==================== 3. 创建零件包调用记录表 ====================

CREATE TABLE IF NOT EXISTS kit_allocations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,  -- 零件包产品 ID
    kit_sku VARCHAR(100),  -- 零件包 SKU
    kit_name VARCHAR(200),  -- 零件包名称
    quantity INTEGER NOT NULL DEFAULT 0,  -- 调用数量
    kit_cost FLOAT DEFAULT 0,  -- 零件包成本（调用时的单位成本）
    total_cost FLOAT DEFAULT 0,  -- 总成本
    user_id INTEGER,  -- 操作人 ID
    remark TEXT,  -- 备注
    allocated_at DATETIME DEFAULT CURRENT_TIMESTAMP,  -- 调用时间
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_kit_allocations_order ON kit_allocations(order_id);
CREATE INDEX IF NOT EXISTS idx_kit_allocations_product ON kit_allocations(product_id);

-- ==================== 4. 创建订单操作日志表 ====================

CREATE TABLE IF NOT EXISTS order_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id INTEGER NOT NULL,
    user_id INTEGER,  -- 操作人 ID
    action VARCHAR(50) NOT NULL,  -- 操作类型：create | allocate_kit | procure | ship | update_status
    old_status VARCHAR(50),  -- 原状态
    new_status VARCHAR(50),  -- 新状态
    detail TEXT,  -- 操作详情（JSON 格式）
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_order_logs_order ON order_logs(order_id);
CREATE INDEX IF NOT EXISTS idx_order_logs_created_at ON order_logs(created_at);

-- ==================== 5. 更新订单状态枚举 ====================

-- 注释：SQLite 不强制枚举，这里用注释说明
-- 订单状态：pending (待处理) | prepared (已备货) | shipped (已发货) | completed (已完成) | cancelled (已取消)

-- 更新现有订单状态（如果需要）
-- UPDATE orders SET status = 'pending' WHERE status = 'unpaid';
-- UPDATE orders SET status = 'shipped' WHERE status = 'delivered';

-- ==================== 6. 创建视图：订单完整信息 ====================

CREATE VIEW IF NOT EXISTS v_orders_complete AS
SELECT 
    o.id,
    o.order_no,
    o.customer_name,
    o.customer_contact,
    o.order_type,
    o.product_id,
    o.product_sku,
    o.product_name,
    o.quantity,
    o.unit_price,
    o.total_amount,
    o.status,
    o.kit_id,
    o.kit_quantity,
    o.procurement_cost,
    o.shipping_cost,
    o.shipping_company,
    o.tracking_no,
    o.shipped_at,
    o.prepared_at,
    o.created_at,
    o.updated_at,
    p.dealer_price,
    p.retail_price,
    p.kit_stock_quantity,
    p.stock_quantity,
    (o.total_amount - COALESCE(o.procurement_cost, 0) - COALESCE(o.shipping_cost, 0)) as gross_profit
FROM orders o
LEFT JOIN products p ON o.product_id = p.id;

-- ==================== 7. 创建视图：采购统计 ====================

CREATE VIEW IF NOT EXISTS v_procurement_stats AS
SELECT 
    order_id,
    COUNT(*) as total_parts,
    SUM(CASE WHEN status = 'purchased' THEN 1 ELSE 0 END) as purchased_count,
    SUM(CASE WHEN status = 'received' THEN 1 ELSE 0 END) as received_count,
    SUM(total_cost) as total_cost,
    MAX(purchased_at) as last_purchase_at
FROM procurement_lists
GROUP BY order_id;

-- ==================== 8. 数据迁移（如果需要） ====================

-- 示例：将旧订单状态映射到新状态
-- UPDATE orders SET status = 'pending' WHERE status IN ('unpaid', 'pending');
-- UPDATE orders SET status = 'prepared' WHERE status = 'paid';
-- UPDATE orders SET status = 'shipped' WHERE status IN ('shipped', 'delivered');

-- ==================== 9. 插入测试数据（可选） ====================

-- 测试零件包调用记录
-- INSERT INTO kit_allocations (order_id, product_id, kit_sku, kit_name, quantity, kit_cost, total_cost, user_id, remark)
-- VALUES (1, 1, 'AP2401-SKU1', '铝型材基础包', 2, 150.0, 300.0, 1, '测试数据');

-- 测试采购清单
-- INSERT INTO procurement_lists (order_id, product_id, part_name, specs, quantity, unit_cost, total_cost, taobao_link, status)
-- VALUES (1, 1, '铝型材', '40x40x2mm', 10, 25.5, 255.0, 'https://...', 'pending');

-- ==================== 迁移完成 ====================

SELECT '数据库迁移完成！' as message;
SELECT '新增表：procurement_lists, kit_allocations, order_logs' as message;
SELECT '新增字段：orders 表 9 个新字段' as message;
SELECT '新增视图：v_orders_complete, v_procurement_stats' as message;
