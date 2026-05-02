import os
import re
import hashlib
from datetime import datetime, timedelta
from typing import List, Optional
from enum import Enum as PyEnum

# 设置北京时间（UTC+8）
BEIJING_TZ = timedelta(hours=8)
def beijing_now():
    """返回北京时间"""
    return datetime.utcnow() + BEIJING_TZ

from fastapi import FastAPI, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import func, create_engine, Column, Integer, String, Float, Boolean, DateTime, ForeignKey, Text, text
from sqlalchemy.orm import sessionmaker, Session, relationship, declarative_base

# ==================== 配置 ====================

# Pydantic 模型
class UserLogin(BaseModel):
    username: str
    password: str

class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "user"

class UserLog(BaseModel):
    action: str
    detail: str = ""
DATABASE_URL = "sqlite:///./n1_lab_v3.db" # 升级版本以防万一
SECRET_PASSWORD = "n1lab2026"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ==================== 数据库模型 ====================
class Dealer(Base):
    __tablename__ = "dealers"
    id = Column(Integer, primary_key=True, index=True)
    company_name = Column(String)
    contact_name = Column(String)
    contact_phone = Column(String, unique=True)
    status = Column(String, default="pending") 
    created_at = Column(DateTime, default=beijing_now)

class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True, index=True)
    sku_code = Column(String, unique=True)
    product_name = Column(String)
    category = Column(String)
    n1_price = Column(Float)
    dealer_price = Column(Float)
    retail_price = Column(Float)
    stock_quantity = Column(Integer, default=0)  # 产品库存（整体）
    kit_stock_quantity = Column(Integer, default=0)  # 零件包库存（新增）
    kit_cost = Column(Float, default=0)  # 零件包成本（从 BOM 同步）
    total_bom_cost = Column(Float, default=0)  # 整体 BOM 成本（从 BOM 同步）
    sale_type = Column(String, default="parts_pack")  # 销售类型：parts_pack|complete
    is_parts_pack = Column(Boolean, default=True)  # 是否零件包
    bom_items = relationship("BOMItem", back_populates="product")

class BOMItem(Base):
    __tablename__ = "bom_items"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    part_name = Column(String)
    specs = Column(String)  # Added to match DB
    quantity = Column(String)  # Changed to String to match DB
    link = Column(String)  # Renamed from supplier_name to link to match DB
    estimated_cost = Column(Float)
    product = relationship("Product", back_populates="bom_items")

class BOMVersion(Base):
    __tablename__ = "bom_versions"
    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), index=True)
    version_no = Column(Integer)
    note = Column(String, default="")
    created_at = Column(DateTime, default=beijing_now)

class BOMVersionItem(Base):
    __tablename__ = "bom_version_items"
    id = Column(Integer, primary_key=True, index=True)
    version_id = Column(Integer, ForeignKey("bom_versions.id"), index=True)
    part_name = Column(String)
    specs = Column(String)
    quantity = Column(String)
    purchase_quantity = Column(String)
    estimated_cost = Column(Float)
    total_cost = Column(Float)
    link = Column(String)
    remark = Column(String)

class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True, index=True)
    order_no = Column(String, unique=True)  # 订单编号
    dealer_id = Column(Integer, ForeignKey("dealers.id"), nullable=True)
    customer_name = Column(String)  # 客户名称
    customer_contact = Column(String)  # 客户联系方式
    order_type = Column(String, default="kit")  # 订单类型：kit|complete
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)  # 关联产品
    product_sku = Column(String)  # 产品 SKU
    product_name = Column(String)  # 产品名称
    quantity = Column(Integer, default=1)  # 数量
    unit_price = Column(Float, default=0)  # 单价
    total_amount = Column(Float, default=0)  # 总金额
    status = Column(String, default="pending")  # pending, prepared, shipped, completed, cancelled
    remark = Column(Text, default="")  # 备注
    created_by = Column(Integer, nullable=True)  # 创建人 ID
    created_at = Column(DateTime, default=beijing_now)
    updated_at = Column(DateTime, nullable=True)  # 更新时间
    prepared_at = Column(DateTime, nullable=True)  # 备货完成时间
    shipped_at = Column(DateTime, nullable=True)  # 发货时间
    procurement_cost = Column(Float, default=0)  # 采购成本
    shipping_company = Column(String, nullable=True)  # 快递公司
    tracking_no = Column(String, nullable=True)  # 快递单号
    kit_id = Column(Integer, nullable=True)  # 关联零件包产品 ID
    kit_quantity = Column(Integer, default=0)  # 零件包数量
    items = relationship("OrderItem", back_populates="order")

class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id"))
    product_id = Column(Integer, ForeignKey("products.id"))
    quantity = Column(Integer)
    price = Column(Float)
    order = relationship("Order", back_populates="items")

Base.metadata.create_all(bind=engine)

def ensure_bom_version_tables():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bom_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                version_no INTEGER,
                note TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS bom_version_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER,
                part_name TEXT,
                specs TEXT,
                quantity TEXT,
                purchase_quantity TEXT,
                estimated_cost REAL,
                total_cost REAL,
                link TEXT,
                remark TEXT
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS order_procurement_versions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id INTEGER,
                version_no INTEGER,
                note TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS order_procurement_version_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id INTEGER,
                part_name TEXT,
                specs TEXT,
                quantity REAL DEFAULT 0,
                unit_cost REAL DEFAULT 0,
                total_cost REAL DEFAULT 0,
                taobao_link TEXT,
                status TEXT DEFAULT 'pending'
            )
        """))

ensure_bom_version_tables()

# ==================== Pydantic 模型 ====================
class ProductSchema(BaseModel):
    sku_code: str
    product_name: str
    category: str
    n1_price: float
    dealer_price: float
    retail_price: float
    stock_quantity: int
    class Config: from_attributes = True

class OrderItemCreate(BaseModel):
    product_id: int
    quantity: int

class OrderCreate(BaseModel):
    dealer_phone: str
    items: List[OrderItemCreate]

class BatchOrderItem(BaseModel):
    product_id: int
    product_sku: str
    product_name: str
    quantity: int
    unit_price: float
    total_amount: float
    remark: Optional[str] = ""

class BatchOrderCreate(BaseModel):
    customer_name: str
    customer_contact: Optional[str] = ""
    order_type: str = "complete"
    items: List[BatchOrderItem]

class BOMEditItem(BaseModel):
    part_name: str = ""
    specs: str = ""
    quantity: str = ""
    purchase_quantity: str = ""
    estimated_cost: float = 0
    total_cost: float = 0
    link: str = ""
    remark: str = ""

class BOMSaveRequest(BaseModel):
    items: List[BOMEditItem]
    note: Optional[str] = ""

class ProcurementEditItem(BaseModel):
    part_name: str = ""
    specs: str = ""
    quantity: float = 0
    unit_cost: float = 0
    total_cost: float = 0
    taobao_link: str = ""
    status: str = "pending"

class ProcurementSaveRequest(BaseModel):
    items: List[ProcurementEditItem]
    note: Optional[str] = ""

def recalc_product_bom_costs(product_id: int, db: Session):
    rows = db.execute(text("""
        SELECT estimated_cost, total_cost, remark
        FROM bom_items WHERE product_id = :pid
    """), {"pid": product_id}).fetchall()

    kit_cost = 0
    total_cost = 0
    for r in rows:
        row_total = float(r[1] or 0)
        total_cost += row_total
        remark = r[2] or ""
        if "N+1" in remark or "零件包" in remark:
            kit_cost += row_total

    product = db.query(Product).filter(Product.id == product_id).first()
    if product:
        product.kit_cost = round(kit_cost, 2)
        product.total_bom_cost = round(total_cost, 2)

def snapshot_bom_version(product_id: int, note: str, db: Session):
    current = db.execute(text("SELECT COALESCE(MAX(version_no), 0) FROM bom_versions WHERE product_id = :pid"), {"pid": product_id}).fetchone()
    next_version = (current[0] if current and current[0] else 0) + 1

    db.execute(text("""
        INSERT INTO bom_versions (product_id, version_no, note, created_at)
        VALUES (:product_id, :version_no, :note, :created_at)
    """), {
        "product_id": product_id,
        "version_no": next_version,
        "note": note or "手动保存",
        "created_at": beijing_now()
    })

    version_id = db.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
    rows = db.execute(text("""
        SELECT part_name, specs, quantity, purchase_quantity, estimated_cost, total_cost, link, remark
        FROM bom_items WHERE product_id = :pid ORDER BY id
    """), {"pid": product_id}).fetchall()

    for row in rows:
        db.execute(text("""
            INSERT INTO bom_version_items (
                version_id, part_name, specs, quantity, purchase_quantity,
                estimated_cost, total_cost, link, remark
            ) VALUES (
                :version_id, :part_name, :specs, :quantity, :purchase_quantity,
                :estimated_cost, :total_cost, :link, :remark
            )
        """), {
            "version_id": version_id,
            "part_name": row[0],
            "specs": row[1],
            "quantity": row[2],
            "purchase_quantity": row[3],
            "estimated_cost": row[4],
            "total_cost": row[5],
            "link": row[6],
            "remark": row[7],
        })

    return next_version

def snapshot_order_procurement_version(order_id: int, note: str, db: Session):
    current = db.execute(text("SELECT COALESCE(MAX(version_no), 0) FROM order_procurement_versions WHERE order_id = :oid"), {"oid": order_id}).fetchone()
    next_version = (current[0] if current and current[0] else 0) + 1
    db.execute(text("""
        INSERT INTO order_procurement_versions (order_id, version_no, note, created_at)
        VALUES (:order_id, :version_no, :note, :created_at)
    """), {
        "order_id": order_id,
        "version_no": next_version,
        "note": note or "手动保存",
        "created_at": beijing_now()
    })
    version_id = db.execute(text("SELECT last_insert_rowid()")).fetchone()[0]
    rows = db.execute(text("""
        SELECT part_name, specs, quantity, unit_cost, total_cost, taobao_link, status
        FROM procurement_lists WHERE order_id = :oid ORDER BY id
    """), {"oid": order_id}).fetchall()
    for row in rows:
        db.execute(text("""
            INSERT INTO order_procurement_version_items (
                version_id, part_name, specs, quantity, unit_cost, total_cost, taobao_link, status
            ) VALUES (
                :version_id, :part_name, :specs, :quantity, :unit_cost, :total_cost, :taobao_link, :status
            )
        """), {
            "version_id": version_id,
            "part_name": row[0],
            "specs": row[1],
            "quantity": row[2],
            "unit_cost": row[3],
            "total_cost": row[4],
            "taobao_link": row[5],
            "status": row[6],
        })
    return next_version

def build_procurement_items_from_order(order, db: Session):
    sql = text("""
        SELECT part_name, specs, quantity, purchase_quantity, link, estimated_cost, total_cost
        FROM bom_items
        WHERE product_id = :pid
        ORDER BY id
    """)
    bom_items = db.execute(sql, {"pid": order.product_id}).fetchall()
    procurement_list = []
    for item in bom_items:
        part_name, specs, quantity_str, purchase_quantity_str, link, estimated_cost, total_cost = item
        try:
            purchase_qty = float(purchase_quantity_str) if purchase_quantity_str not in [None, ""] else float(quantity_str or 0)
        except:
            purchase_qty = 0
        order_qty = float(order.quantity or 1)
        final_qty = purchase_qty * order_qty
        unit_cost = float(estimated_cost or 0)
        final_total = float(total_cost or 0)
        if final_total == 0 and unit_cost:
            final_total = unit_cost * final_qty
        procurement_list.append({
            "part_name": part_name,
            "specs": specs or "",
            "quantity": final_qty,
            "unit_cost": unit_cost,
            "total_cost": final_total,
            "taobao_link": link or "",
            "status": "pending"
        })
    return procurement_list

# ==================== 安全验证 ====================
async def verify_auth(x_api_key: Optional[str] = Header(None)):
    if x_api_key != SECRET_PASSWORD:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_api_key

# ==================== FastAPI 应用 ====================
app = FastAPI(title="N+1 LAB API v3")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# 挂载静态文件目录（前端页面）
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "../frontend")
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

# 根路径和登录页面路由
@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/login.html")
def serve_login():
    return FileResponse(os.path.join(FRONTEND_DIR, "login.html"))

# 插件下载路由
@app.get("/downloads/n1_helper_v7.4_final.tar.gz")
def download_plugin():
    plugin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "n1_helper_v7.4_final.tar.gz")
    return FileResponse(
        plugin_path,
        media_type="application/gzip",
        filename="n1_helper_v7.4_final.tar.gz"
    )

@app.get("/downloads/n1_helper_v7.3_fix.tar.gz")
def download_plugin_v73():
    plugin_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "n1_helper_v7.3_fix.tar.gz")
    return FileResponse(
        plugin_path,
        media_type="application/gzip",
        filename="n1_helper_v7.3_fix.tar.gz"
    )

@app.get("/dealer.html")
async def dealer_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "dealer.html"))

@app.get("/dealer_v4.html")
async def dealer_v4_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "dealer_v4.html"))

@app.get("/dealer_v5.html")
async def dealer_v5_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "dealer_v5.html"))

@app.get("/dealer")
async def dealer_short_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "dealer_v5.html"))

@app.get("/index.html")
async def index_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/orders.html")
async def orders_page():
    """订单管理页面 v4.0"""
    return FileResponse(os.path.join(FRONTEND_DIR, "orders.html"))

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- 业务接口 ---
@app.get("/products/")
def list_products(db: Session = Depends(get_db)):
    return db.query(Product).all()

@app.post("/dealers/")
def apply_dealer(dealer_data: dict, db: Session = Depends(get_db)):
    """经销商入驻申请（接收 JSON body）"""
    company_name = dealer_data.get("company_name", "")
    contact_name = dealer_data.get("contact_name", "")
    contact_phone = dealer_data.get("contact_phone", "")
    
    if not company_name or not contact_name or not contact_phone:
        raise HTTPException(status_code=400, detail="公司名称、联系人、联系电话不能为空")
    
    # 检查手机号是否已注册
    existing = db.query(Dealer).filter(Dealer.contact_phone == contact_phone).first()
    if existing:
        raise HTTPException(status_code=400, detail="该手机号已注册")
    
    db_d = Dealer(company_name=company_name, contact_name=contact_name, contact_phone=contact_phone)
    db.add(db_d)
    db.commit()
    db.refresh(db_d)
    return {"status": "success", "id": db_d.id}

@app.get("/dealers/", dependencies=[Depends(verify_auth)])
def list_all_dealers(db: Session = Depends(get_db)):
    return db.query(Dealer).all()

@app.put("/dealers/{dealer_id}/status", dependencies=[Depends(verify_auth)])
def update_dealer(dealer_id: int, status: str, db: Session = Depends(get_db)):
    d = db.query(Dealer).filter(Dealer.id == dealer_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="经销商不存在")
    d.status = status
    db.commit()
    return {"status": "success"}

@app.get("/dealers/check/{phone}")
def check_dealer(phone: str, db: Session = Depends(get_db)):
    d = db.query(Dealer).filter(Dealer.contact_phone == phone).first()
    if not d: raise HTTPException(status_code=404)
    return {"status": d.status, "company_name": d.company_name, "id": d.id}

# --- 核心：批量下单接口（支持一次性创建多个 SKU，拆分为独立订单行） ---
@app.post("/orders/batch-create")
def batch_create_orders(
    batch_data: BatchOrderCreate,
    db: Session = Depends(get_db)
):
    """批量创建订单，每个 SKU 拆分为独立的 Order 记录，共享同一母单号前缀"""
    import datetime
    import random
    import string

    if not batch_data.customer_name:
        raise HTTPException(status_code=400, detail="客户姓名不能为空")
    
    if not batch_data.items:
        raise HTTPException(status_code=400, detail="至少需要选择一个产品")

    # 生成一个公共的主订单号前缀，如 ORD2026041912304567
    base_order_no = "ORD" + datetime.datetime.now().strftime("%Y%m%d%H%M") + ''.join(random.choices(string.digits, k=4))
    
    created_orders = []
    
    for idx, item in enumerate(batch_data.items):
        # 如果有多个商品，追加后缀
        order_no = base_order_no if len(batch_data.items) == 1 else f"{base_order_no}-{idx+1:02d}"
        
        cursor = db.execute(text("""
            INSERT INTO orders (
                order_no, customer_name, customer_contact, order_type,
                product_id, product_sku, product_name, quantity,
                unit_price, total_amount, status, remark, created_by
            ) VALUES (
                :order_no, :customer_name, :customer_contact, :order_type,
                :product_id, :product_sku, :product_name, :quantity,
                :unit_price, :total_amount, 'pending', :remark, :created_by
            )
        """), {
            "order_no": order_no,
            "customer_name": batch_data.customer_name,
            "customer_contact": batch_data.customer_contact,
            "order_type": batch_data.order_type,
            "product_id": item.product_id,
            "product_sku": item.product_sku,
            "product_name": item.product_name,
            "quantity": item.quantity,
            "unit_price": item.unit_price,
            "total_amount": item.total_amount,
            "remark": item.remark,
            "created_by": 1 # 默认管理员
        })
        created_orders.append({"order_no": order_no, "product_id": item.product_id})

    db.commit()
    return {"status": "success", "message": f"成功创建 {len(created_orders)} 笔订单", "orders": created_orders}

# --- 核心：下单接口（兼容旧版 index.html，单产品格式） ---
@app.post("/orders/")
def create_order_legacy(
    order_data: dict,
    db: Session = Depends(get_db)
):
    """创建订单（旧版 index.html 使用，单产品格式）"""
    import datetime
    import random
    import string
    
    customer_name = order_data.get("customer_name")
    customer_contact = order_data.get("customer_contact")
    order_type = order_data.get("order_type", "complete")
    product_id = order_data.get("product_id")
    product_sku = order_data.get("product_sku")
    product_name = order_data.get("product_name")
    quantity = order_data.get("quantity", 1)
    unit_price = order_data.get("unit_price", 0)
    total_amount = order_data.get("total_amount", 0)
    remark = order_data.get("remark", "")
    
    if not customer_name:
        raise HTTPException(status_code=400, detail="客户姓名不能为空")
    
    if not product_id:
        raise HTTPException(status_code=400, detail="产品 ID 不能为空")
    
    # 生成订单号
    order_no = "ORD" + datetime.datetime.now().strftime("%Y%m%d%H%M") + ''.join(random.choices(string.digits, k=4))
    
    # 插入订单
    cursor = db.execute(text("""
        INSERT INTO orders (
            order_no, customer_name, customer_contact, order_type,
            product_id, product_sku, product_name, quantity,
            unit_price, total_amount, status, remark, created_by
        ) VALUES (
            :order_no, :customer_name, :customer_contact, :order_type,
            :product_id, :product_sku, :product_name, :quantity,
            :unit_price, :total_amount, 'pending', :remark, :created_by
        )
    """), {
        "order_no": order_no,
        "customer_name": customer_name,
        "customer_contact": customer_contact or "未知",
        "order_type": order_type,
        "product_id": product_id,
        "product_sku": product_sku or "",
        "product_name": product_name or "",
        "quantity": quantity,
        "unit_price": unit_price,
        "total_amount": total_amount,
        "remark": remark,
        "created_by": 1
    })
    
    db.commit()
    
    return {
        "status": "success",
        "order_no": order_no,
        "message": "订单创建成功"
    }
#     db.commit()
#     return {"status": "success", "order_id": new_order.id, "total": total}

# 注意：此路由已被下面的 get_orders 函数覆盖（828 行）
# 保留作为经销商订单 API，使用不同路径
@app.get("/dealer/orders/", dependencies=[Depends(verify_auth)])
def list_dealer_orders(db: Session = Depends(get_db)):
    # 为了让前端能看到产品名，我们稍微关联一下
    orders = db.query(Order).all()
    res = []
    for o in orders:
        items = db.query(OrderItem).filter(OrderItem.order_id == o.id).all()
        item_list = []
        for i in items:
            p = db.query(Product).filter(Product.id == i.product_id).first()
            item_list.append({"product_name": p.product_name, "quantity": i.quantity, "product_id": p.id})
        res.append({"id": o.id, "dealer_id": o.dealer_id, "total_amount": o.total_amount, "status": o.status, "created_at": o.created_at, "items": item_list})
    return res

@app.get("/products/{product_id}/bom", dependencies=[Depends(verify_auth)])
def get_product_bom(product_id: int, db: Session = Depends(get_db)):
    # 查找关联的零件表（包含 total_cost 字段）
    from sqlalchemy import text
    sql = text("SELECT part_name, specs, quantity, purchase_quantity, link, estimated_cost, total_cost, remark FROM bom_items WHERE product_id = :pid")
    result = db.execute(sql, {"pid": product_id}).fetchall()
    return [{
        "part_name": r[0], 
        "specs": r[1], 
        "quantity": r[2],  # 零件数量（总个数）
        "purchase_quantity": r[3],  # 采购用量（下单次数）
        "link": r[4],
        "estimated_cost": r[5],  # 单价
        "total_cost": r[6],  # 总价（含运费，从数据库读取）
        "remark": r[7]  # 备注
    } for r in result]

@app.get("/admin/products/{product_id}/bom-editor")
def get_product_bom_editor(product_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    items = get_product_bom(product_id, db)
    latest = db.execute(text("""
        SELECT id, version_no, note, created_at
        FROM bom_versions
        WHERE product_id = :pid
        ORDER BY version_no DESC
        LIMIT 10
    """), {"pid": product_id}).fetchall()

    return {
        "product": {
            "id": product.id,
            "sku_code": product.sku_code,
            "product_name": product.product_name
        },
        "items": items,
        "versions": [{
            "id": r[0],
            "version_no": r[1],
            "note": r[2],
            "created_at": r[3]
        } for r in latest]
    }

@app.post("/admin/products/{product_id}/bom-editor")
def save_product_bom_editor(product_id: int, payload: BOMSaveRequest, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    snapshot_bom_version(product_id, payload.note or "保存前备份", db)
    db.execute(text("DELETE FROM bom_items WHERE product_id = :pid"), {"pid": product_id})

    for item in payload.items:
        if not any([
            item.part_name.strip(), item.specs.strip(), item.quantity.strip(), item.purchase_quantity.strip(),
            item.link.strip(), item.remark.strip(), float(item.estimated_cost or 0) != 0, float(item.total_cost or 0) != 0
        ]):
            continue

        db.execute(text("""
            INSERT INTO bom_items (
                product_id, part_name, specs, quantity, link, estimated_cost,
                remark, purchase_quantity, total_cost
            ) VALUES (
                :product_id, :part_name, :specs, :quantity, :link, :estimated_cost,
                :remark, :purchase_quantity, :total_cost
            )
        """), {
            "product_id": product_id,
            "part_name": item.part_name,
            "specs": item.specs,
            "quantity": item.quantity,
            "link": item.link,
            "estimated_cost": item.estimated_cost,
            "remark": item.remark,
            "purchase_quantity": item.purchase_quantity,
            "total_cost": item.total_cost,
        })

    recalc_product_bom_costs(product_id, db)
    saved_version = snapshot_bom_version(product_id, payload.note or "手动保存", db)
    db.commit()
    return {"status": "success", "version_no": saved_version}

@app.post("/admin/products/{product_id}/bom-editor/rollback/{version_id}")
def rollback_product_bom_editor(product_id: int, version_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    version = db.execute(text("SELECT id, version_no FROM bom_versions WHERE id = :vid AND product_id = :pid"), {
        "vid": version_id, "pid": product_id
    }).fetchone()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")

    snapshot_bom_version(product_id, f"回滚前备份", db)
    db.execute(text("DELETE FROM bom_items WHERE product_id = :pid"), {"pid": product_id})

    items = db.execute(text("""
        SELECT part_name, specs, quantity, purchase_quantity, estimated_cost, total_cost, link, remark
        FROM bom_version_items WHERE version_id = :vid ORDER BY id
    """), {"vid": version_id}).fetchall()

    for row in items:
        db.execute(text("""
            INSERT INTO bom_items (
                product_id, part_name, specs, quantity, link, estimated_cost,
                remark, purchase_quantity, total_cost
            ) VALUES (
                :product_id, :part_name, :specs, :quantity, :link, :estimated_cost,
                :remark, :purchase_quantity, :total_cost
            )
        """), {
            "product_id": product_id,
            "part_name": row[0],
            "specs": row[1],
            "quantity": row[2],
            "link": row[6],
            "estimated_cost": row[4],
            "remark": row[7],
            "purchase_quantity": row[3],
            "total_cost": row[5],
        })

    recalc_product_bom_costs(product_id, db)
    new_version = snapshot_bom_version(product_id, f"回滚到 v{version[1]}", db)
    db.commit()
    return {"status": "success", "version_no": new_version}

# ==================== 经销商门户 API ====================

@app.get("/dealer/profile")
def get_dealer_profile(phone: str, db: Session = Depends(get_db)):
    """获取经销商详细信息"""
    dealer = db.query(Dealer).filter(Dealer.contact_phone == phone).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="经销商不存在")
    return {
        "company_name": dealer.company_name,
        "contact_name": dealer.contact_name,
        "contact_phone": dealer.contact_phone,
        "business_license": getattr(dealer, 'business_license', None),
        "tax_id": getattr(dealer, 'tax_id', None),
        "invoice_title": getattr(dealer, 'invoice_title', None),
        "invoice_address": getattr(dealer, 'invoice_address', None),
        "shipping_address": getattr(dealer, 'shipping_address', None),
        "shipping_contact": getattr(dealer, 'shipping_contact', None),
        "shipping_phone": getattr(dealer, 'shipping_phone', None),
        "status": dealer.status,
        "created_at": dealer.created_at
    }

@app.put("/dealer/profile")
def update_dealer_profile(profile_data: dict, phone: str, db: Session = Depends(get_db)):
    """更新经销商信息"""
    dealer = db.query(Dealer).filter(Dealer.contact_phone == phone).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="经销商不存在")
    
    # 更新可修改的字段
    updatable_fields = [
        'company_name', 'contact_name', 'tax_id', 'invoice_title',
        'business_license', 'invoice_address', 'shipping_address',
        'shipping_contact', 'shipping_phone'
    ]
    for field in updatable_fields:
        if field in profile_data:
            setattr(dealer, field, profile_data[field])
    
    db.commit()
    return {"status": "success", "message": "信息已更新"}

@app.get("/dealer/orders/{phone}")
def get_dealer_orders(phone: str, db: Session = Depends(get_db)):
    """获取经销商订单列表（带物流信息）"""
    from sqlalchemy import text
    
    dealer = db.execute(text("SELECT id, company_name, contact_name FROM dealers WHERE contact_phone = :phone"), {"phone": phone}).fetchone()
    if not dealer:
        raise HTTPException(status_code=404, detail="经销商不存在")
    
    # 通过 customer_name 关联经销商（订单表没有 dealer_id 字段）
    orders = db.execute(text("""
        SELECT id, order_no, customer_name, customer_contact, order_type,
               product_id, product_sku, product_name, quantity,
               unit_price, total_amount, status, remark, created_at
        FROM orders
        WHERE customer_name = :customer_name
        ORDER BY created_at DESC
    """), {"customer_name": dealer.company_name}).fetchall()
    
    result = []
    for o in orders:
        result.append({
            "id": o[0],
            "order_no": o[1],
            "customer_name": o[2],
            "customer_contact": o[3],
            "order_type": o[4],  # 添加订单类型
            "status": o[11],
            "total_amount": o[10],
            "created_at": o[13],
            "items": [{
                "product_name": o[7],
                "quantity": o[8],
                "price": o[9]
            }]  # 每个订单只有一个产品
        })
    return result

@app.get("/dealer/stats/{phone}")
def get_dealer_stats(phone: str, db: Session = Depends(get_db)):
    """获取经销商统计数据（通过 customer_name 关联，与 get_dealer_orders 保持一致）"""
    dealer = db.query(Dealer).filter(Dealer.contact_phone == phone).first()
    if not dealer:
        raise HTTPException(status_code=404, detail="经销商不存在")
    
    # 使用 customer_name 关联订单（与 get_dealer_orders 一致）
    customer_name = dealer.company_name
    total_orders = db.query(func.count(Order.id)).filter(Order.customer_name == customer_name).scalar()
    total_amount = db.query(func.sum(Order.total_amount)).filter(Order.customer_name == customer_name).scalar() or 0
    pending = db.query(func.count(Order.id)).filter(Order.customer_name == customer_name, Order.status == 'pending').scalar()
    shipped = db.query(func.count(Order.id)).filter(Order.customer_name == customer_name, Order.status == 'shipped').scalar()
    completed = db.query(func.count(Order.id)).filter(Order.customer_name == customer_name, Order.status == 'completed').scalar()
    
    from datetime import datetime
    first_day = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    month_orders = db.query(func.count(Order.id)).filter(Order.customer_name == customer_name, Order.created_at >= first_day).scalar()
    month_amount = db.query(func.sum(Order.total_amount)).filter(Order.customer_name == customer_name, Order.created_at >= first_day).scalar() or 0
    
    return {
        "total_orders": total_orders or 0,
        "total_amount": round(total_amount, 2),
        "pending_orders": pending or 0,
        "shipped_orders": shipped or 0,
        "completed_orders": completed or 0,
        "this_month_orders": month_orders or 0,
        "this_month_amount": round(month_amount, 2)
    }

@app.put("/dealer/order/{order_id}/ship")
def ship_order(order_id: int, shipping_company: str, tracking_no: str, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    """管理员发货"""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    order.shipping_company = shipping_company
    order.tracking_no = tracking_no
    order.shipping_time = beijing_now()
    order.status = 'shipped'
    db.commit()
    return {"status": "success", "message": "已发货"}

@app.get("/dealer/bank-info")
def get_bank_info():
    """获取对公转账账户信息"""
    return {
        "company_name": "北京 N+1 实验室科技有限公司",
        "bank_name": "招商银行北京中关村支行",
        "bank_account": "1109 1234 5678 901",
        "bank_code": "308100005017",
        "address": "北京市海淀区中关村大街 1 号",
        "tax_id": "91110108MA01ABCD12",
        "phone": "010-8888 8888",
        "note": "请备注订单号，财务核实后发货"
    }

@app.get("/bom_center.html")
async def bom_center_page():
    return FileResponse(os.path.join(FRONTEND_DIR, "bom_center.html"))

@app.get("/admin/products/bom-costs")
def get_products_bom_costs(db: Session = Depends(get_db), auth=Depends(verify_auth)):
    """获取所有产品的 BOM 成本统计（从 products 表读取同步后的数据）"""
    products = db.query(Product).all()
    
    # 自定义排序：按 SKU 编号顺序（AP2401-SKU1 → AP2401-SKU2 → ... → AP2503-SKU2 → A2504-SKU1）
    def sort_key(p):
        sku = p.sku_code or ""
        # 提取系列号和产品号，例如 AP2401-SKU1 → (2401, 1)
        import re
        match = re.match(r'(?:AP)?(\d{4})-SKU(\d+)', sku)
        if match:
            series = int(match.group(1))  # 2401, 2402, 2403, 2501, 2502, 2503, 2504
            sku_num = int(match.group(2))  # 1, 2, 3...
            return (series, sku_num)
        else:
            # 对于 A2504-SKU1 这种格式
            match = re.match(r'A(\d{4})-SKU(\d+)', sku)
            if match:
                series = int(match.group(1))
                sku_num = int(match.group(2))
                return (series, sku_num)
            return (9999, 999)  # 无法解析的排到最后
    
    products = sorted(products, key=sort_key)
    
    result = []
    
    for p in products:
        # 从 products 表读取同步后的成本数据
        kit_cost = p.kit_cost or 0  # 零件包成本
        total_bom_cost = p.total_bom_cost or 0  # 整体 BOM 成本
        
        # 查询零件数量
        from sqlalchemy import text
        sql_count = text("""
            SELECT COUNT(*) as part_count 
            FROM bom_items 
            WHERE product_id = :pid
        """)
        count_result = db.execute(sql_count, {"pid": p.id}).fetchone()
        bom_count = count_result[0] if count_result and count_result[0] else 0
        
        # 计算零件包毛利润和毛利率
        kit_profit = p.dealer_price - kit_cost if p.dealer_price > 0 else 0
        kit_margin = ((p.dealer_price - kit_cost) / p.dealer_price * 100) if p.dealer_price > 0 else 0
        
        # 计算整体销售毛利润和毛利率
        retail_profit = p.retail_price - total_bom_cost if p.retail_price > 0 else 0
        retail_margin = ((p.retail_price - total_bom_cost) / p.retail_price * 100) if p.retail_price > 0 else 0
        
        result.append({
            "id": p.id,
            "sku_code": p.sku_code,
            "product_name": p.product_name,
            "category": p.category,
            "bom_cost": round(kit_cost, 2),  # 零件包成本（从 products 表读取）
            "total_cost": round(total_bom_cost, 2),  # 整体 BOM 成本（从 products 表读取）
            "dealer_price": p.dealer_price,  # 零件包售价
            "retail_price": p.retail_price,  # 整体零售价
            "kit_profit": round(kit_profit, 2),  # 零件包毛利润
            "kit_margin": round(kit_margin, 2),  # 零件包毛利率
            "retail_profit": round(retail_profit, 2),  # 整体销售毛利润
            "retail_margin": round(retail_margin, 2),  # 整体销售毛利率
            "stock_quantity": p.stock_quantity,  # 产品库存
            "kit_stock_quantity": p.kit_stock_quantity,  # 零件包库存（新增）
            "bom_count": bom_count  # 零件数量
        })
    
    return result

@app.put("/admin/products/{product_id}/prices")
def update_product_prices(
    product_id: int,
    dealer_price: float,
    retail_price: float,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """更新产品价格（零件包售价和零售价）"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    
    product.dealer_price = dealer_price
    product.retail_price = retail_price
    db.commit()
    
    return {"status": "success", "message": "价格已更新"}

@app.put("/admin/products/{product_id}/stock")
def update_product_stock(
    product_id: int,
    stock_quantity: Optional[int] = None,
    kit_stock_quantity: Optional[int] = None,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """更新产品库存（支持分别更新产品库存和零件包库存）"""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    
    if stock_quantity is not None:
        product.stock_quantity = stock_quantity
    if kit_stock_quantity is not None:
        product.kit_stock_quantity = kit_stock_quantity
    
    db.commit()
    
    return {
        "status": "success",
        "message": "库存已更新",
        "data": {
            "stock_quantity": product.stock_quantity,
            "kit_stock_quantity": product.kit_stock_quantity
        }
    }

@app.get("/admin/order/{order_id}/bom")
def get_order_bom(order_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    """获取订单的 BOM 拆解清单（多产品自动汇总）"""
    from sqlalchemy import text
    
    # 先获取订单信息
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # 获取订单所有商品
    order_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
    
    # 汇总 BOM
    bom_summary = {}
    for item in order_items:
        # 查询该产品的 BOM
        sql = text("SELECT part_name, specs, quantity, link, estimated_cost FROM bom_items WHERE product_id = :pid")
        result = db.execute(sql, {"pid": item.product_id}).fetchall()
        
        for row in result:
            part_name, specs, quantity_str, link, estimated_cost = row
            try:
                quantity = float(quantity_str) if quantity_str else 0
            except:
                quantity = 0
            
            # 计算该零件的总需求数量
            total_qty = quantity * item.quantity
            total_cost = (estimated_cost or 0) * total_qty
            
            # 汇总相同零件
            key = f"{part_name}_{specs}"
            if key in bom_summary:
                bom_summary[key]['quantity'] += total_qty
                bom_summary[key]['total_cost'] += total_cost
            else:
                # 从 Product 表查询产品名称（OrderItem 没有 product_name 字段）
                product = db.query(Product).filter(Product.id == item.product_id).first()
                product_display_name = product.product_name if product else '未知商品'
                bom_summary[key] = {
                    'part_name': part_name,
                    'specs': specs,
                    'quantity': total_qty,
                    'link': link,
                    'unit_cost': estimated_cost or 0,
                    'total_cost': total_cost,
                    'product_name': product_display_name
                }
    
    # 转换为列表并排序
    bom_list = sorted(bom_summary.values(), key=lambda x: x['part_name'])
    
    # 安全获取经销商名称（防止 Dealer 记录不存在时 NoneType 报错）
    dealer_name = "未知"
    if order.dealer_id:
        dealer_obj = db.query(Dealer).filter(Dealer.id == order.dealer_id).first()
        if dealer_obj:
            dealer_name = dealer_obj.company_name
    elif order.customer_name:
        dealer_name = order.customer_name
    
    return {
        "order_id": order_id,
        "order_no": getattr(order, 'order_no', f"ORD{order_id:05d}"),
        "dealer": dealer_name,
        "items_count": len(order_items),
        "total_amount": order.total_amount,
        "bom_items": bom_list,
        "total_parts": len(bom_list),
        "estimated_total_cost": sum(item['total_cost'] for item in bom_list)
    }

@app.get("/admin/product-bom-center")
def get_product_bom_center(db: Session = Depends(get_db), auth=Depends(verify_auth)):
    """获取所有产品的 BOM 数据（用于可视化展示）"""
    from sqlalchemy import text
    
    products = db.query(Product).all()
    result = []
    
    for p in products:
        # 查询该产品的 BOM
        sql = text("SELECT part_name, specs, quantity, link, estimated_cost FROM bom_items WHERE product_id = :pid ORDER BY part_name")
        bom_result = db.execute(sql, {"pid": p.id}).fetchall()
        
        bom_items = []
        total_cost = 0
        for row in bom_result:
            part_name, specs, quantity_str, link, estimated_cost = row
            try:
                quantity = float(quantity_str) if quantity_str else 0
            except:
                quantity = 0
            
            item_cost = (estimated_cost or 0) * quantity
            total_cost += item_cost
            
            bom_items.append({
                "part_name": part_name,
                "specs": specs,
                "quantity": quantity,
                "link": link,
                "estimated_cost": estimated_cost or 0,
                "item_cost": round(item_cost, 2)
            })
        
        result.append({
            "id": p.id,
            "sku_code": p.sku_code,
            "product_name": p.product_name,
            "category": p.category,
            "n1_price": p.n1_price,
            "dealer_price": p.dealer_price,
            "retail_price": p.retail_price,
            "stock_quantity": p.stock_quantity,
            "bom_items": bom_items,
            "bom_count": len(bom_items),
            "total_bom_cost": round(total_cost, 2),
            "margin": round(((p.dealer_price - total_cost) / p.dealer_price * 100) if p.dealer_price > 0 else 0, 2)
        })
    
    return result

@app.get("/admin/orders/bom-export")
def export_orders_bom(
    order_ids: str,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """批量导出多个订单的 BOM 汇总（用于采购）"""
    from sqlalchemy import text
    import json
    
    # 解析订单 ID 列表
    ids = [int(x.strip()) for x in order_ids.split(',') if x.strip().isdigit()]
    
    # 汇总所有订单的 BOM
    bom_summary = {}
    total_revenue = 0
    
    for order_id in ids:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            continue
        
        total_revenue += order.total_amount
        order_items = db.query(OrderItem).filter(OrderItem.order_id == order_id).all()
        
        for item in order_items:
            sql = text("SELECT part_name, specs, quantity, link, estimated_cost FROM bom_items WHERE product_id = :pid")
            result = db.execute(sql, {"pid": item.product_id}).fetchall()
            
            for row in result:
                part_name, specs, quantity_str, link, estimated_cost = row
                try:
                    quantity = float(quantity_str) if quantity_str else 0
                except:
                    quantity = 0
                
                total_qty = quantity * item.quantity
                total_cost = (estimated_cost or 0) * total_qty
                
                key = f"{part_name}_{specs}"
                if key in bom_summary:
                    bom_summary[key]['quantity'] += total_qty
                    bom_summary[key]['total_cost'] += total_cost
                    bom_summary[key]['order_count'] += 1
                else:
                    bom_summary[key] = {
                        'part_name': part_name,
                        'specs': specs,
                        'quantity': total_qty,
                        'link': link,
                        'unit_cost': estimated_cost or 0,
                        'total_cost': total_cost,
                        'order_count': 1
                    }
    
    bom_list = sorted(bom_summary.values(), key=lambda x: x['part_name'])
    total_cost = sum(item['total_cost'] for item in bom_list)
    
    return {
        "order_count": len(ids),
        "total_revenue": total_revenue,
        "total_cost": total_cost,
        "gross_profit": total_revenue - total_cost,
        "profit_margin": round((total_revenue - total_cost) / total_revenue * 100, 2) if total_revenue > 0 else 0,
        "total_parts": len(bom_list),
        "bom_items": bom_list
    }

# ==================== 用户管理 API ====================

@app.get("/users/")
def get_users(db: Session = Depends(get_db), auth=Depends(verify_auth)):
    """获取所有用户列表"""
    users = db.execute(text("SELECT id, username, role, status, created_at, last_login, purchase_count FROM users ORDER BY id")).fetchall()
    return [
        {
            "id": u[0],
            "username": u[1],
            "role": u[2],
            "status": u[3],
            "created_at": u[4],
            "last_login": u[5],
            "purchase_count": u[6]
        }
        for u in users
    ]

@app.post("/users/")
def create_user(
    username: str,
    password: str,
    role: str = "user",
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """创建新用户"""
    import hashlib
    import re
    from sqlalchemy import text
    
    # 验证
    if len(username) < 3 or len(username) > 20:
        raise HTTPException(status_code=400, detail="用户名长度必须在 3-20 位之间")
    if not re.match(r'^[a-zA-Z0-9_]+$', username):
        raise HTTPException(status_code=400, detail="用户名只能包含字母、数字和下划线")
    if len(password) < 6:
        raise HTTPException(status_code=400, detail="密码长度至少 6 位")
    
    # 加密密码
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    try:
        db.execute(text("""
            INSERT INTO users (username, password_hash, role)
            VALUES (:username, :password_hash, :role)
        """), {"username": username, "password_hash": password_hash, "role": role})
        db.commit()
        return {"status": "success", "message": f"用户 {username} 创建成功"}
    except Exception as e:
        if "UNIQUE constraint failed" in str(e):
            raise HTTPException(status_code=400, detail="用户名已存在")
        raise

@app.post("/users/login")
def user_login(login_data: UserLogin, db: Session = Depends(get_db)):
    """用户登录"""
    import hashlib
    from sqlalchemy import text
    
    username = login_data.username
    password = login_data.password
    
    # 加密密码
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    # 查询用户
    result = db.execute(text("""
        SELECT id, username, role, status
        FROM users
        WHERE username = :username AND password_hash = :password_hash
    """), {"username": username, "password_hash": password_hash}).fetchone()
    
    if not result:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    
    if result[3] != 'active':
        raise HTTPException(status_code=403, detail="账户已被禁用")
    
    # 更新最后登录时间
    db.execute(text("""
        UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = :id
    """), {"id": result[0]})
    db.commit()
    
    return {
        "status": "success",
        "user": {
            "id": result[0],
            "username": result[1],
            "role": result[2]
        }
    }

@app.get("/users/{user_id}/logs")
def get_user_logs(user_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    """获取用户操作日志"""
    logs = db.execute(text("""
        SELECT l.id, l.action, l.detail, l.created_at, u.username
        FROM user_logs l
        JOIN users u ON l.user_id = u.id
        WHERE l.user_id = :user_id
        ORDER BY l.created_at DESC
        LIMIT 50
    """), {"user_id": user_id}).fetchall()
    
    return [
        {
            "id": log[0],
            "action": log[1],
            "detail": log[2],
            "created_at": log[3],
            "username": log[4]
        }
        for log in logs
    ]

@app.post("/users/{user_id}/log")
def add_user_log(
    user_id: int,
    action: str,
    detail: str = "",
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """添加用户操作日志"""
    db.execute(text("""
        INSERT INTO user_logs (user_id, action, detail)
        VALUES (:user_id, :action, :detail)
    """), {"user_id": user_id, "action": action, "detail": detail})
    db.commit()
    return {"status": "success"}

@app.get("/users/stats")
def get_user_stats(db: Session = Depends(get_db), auth=Depends(verify_auth)):
    """获取用户统计数据"""
    stats = db.execute(text("""
        SELECT 
            COUNT(*) as total,
            SUM(CASE WHEN status = 'active' THEN 1 ELSE 0 END) as active,
            SUM(CASE WHEN purchase_count > 0 THEN 1 ELSE 0 END) as with_purchases,
            SUM(CASE WHEN DATE(last_login) = DATE('now') THEN 1 ELSE 0 END) as today_active
        FROM users
    """)).fetchone()
    
    return {
        "total": stats[0] or 0,
        "active": stats[1] or 0,
        "with_purchases": stats[2] or 0,
        "today_active": stats[3] or 0
    }

# ==================== 数据看板 API ====================

@app.get("/dashboard/stats")
def get_dashboard_stats(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """获取数据看板统计数据（支持时间筛选）"""
    
    # 构建时间筛选条件
    # time_filter: 用于单表查询（orders 单表、purchases 单表）
    # time_filter_aliased: 用于 JOIN 查询（需要 o. 前缀消除歧义）
    time_filter = ""
    time_filter_aliased = ""
    params = {}
    if start_date:
        time_filter += " AND DATE(created_at) >= DATE(:start_date)"
        time_filter_aliased += " AND DATE(o.created_at) >= DATE(:start_date)"
        params["start_date"] = start_date
    if end_date:
        time_filter += " AND DATE(created_at) <= DATE(:end_date)"
        time_filter_aliased += " AND DATE(o.created_at) <= DATE(:end_date)"
        params["end_date"] = end_date
    
    # 订单统计
    order_stats = db.execute(text(f"""
        SELECT 
            COUNT(*) as total_orders,
            SUM(total_amount) as total_amount,
            SUM(procurement_cost) as total_procurement_cost,
            SUM(total_amount - procurement_cost) as total_profit
        FROM orders
        WHERE status != 'cancelled'
        {time_filter}
    """), params).fetchone()
    
    # 库存采购统计（从 purchases 表）
    try:
        inventory_stats = db.execute(text(f"""
            SELECT 
                SUM(actual_cost * quantity) as total_inventory_cost
            FROM purchases
            WHERE 1=1
            {time_filter}
        """), params).fetchone()
        inventory_cost = inventory_stats[0] or 0 if inventory_stats else 0
    except Exception:
        inventory_cost = 0
    
    # 计算总采购成本（订单采购 + 库存采购）
    total_procurement = (order_stats[2] or 0) + inventory_cost
    total_profit = (order_stats[3] or 0) - inventory_cost
    
    # 按状态统计订单
    status_stats = db.execute(text(f"""
        SELECT 
            status,
            COUNT(*) as count,
            SUM(total_amount) as amount
        FROM orders
        WHERE 1=1
        {time_filter}
        GROUP BY status
    """), params).fetchall()
    
    status_breakdown = {}
    for row in status_stats:
        status_breakdown[row[0]] = {"count": row[1] or 0, "amount": row[2] or 0}
    
    # 按产品类别统计（JOIN 查询需用 time_filter_aliased 消除歧义）
    category_stats = db.execute(text(f"""
        SELECT 
            p.category,
            COUNT(o.id) as order_count,
            SUM(o.total_amount) as total_amount,
            SUM(o.procurement_cost) as total_cost,
            SUM(o.total_amount - o.procurement_cost) as total_profit
        FROM orders o
        LEFT JOIN products p ON o.product_id = p.id
        WHERE o.status != 'cancelled'
        {time_filter_aliased}
        GROUP BY p.category
        ORDER BY total_amount DESC
    """), params).fetchall()
    
    category_breakdown = []
    for row in category_stats:
        category_breakdown.append({
            "category": row[0] or "未分类",
            "order_count": row[1] or 0,
            "total_amount": row[2] or 0,
            "total_cost": row[3] or 0,
            "total_profit": row[4] or 0
        })
    
    return {
        "summary": {
            "total_orders": order_stats[0] or 0,
            "total_amount": round(order_stats[1] or 0, 2),
            "total_procurement_cost": round(total_procurement, 2),
            "total_profit": round(total_profit, 2),
            "profit_margin": round((total_profit / (order_stats[1] or 1)) * 100, 2)
        },
        "status_breakdown": status_breakdown,
        "category_breakdown": category_breakdown,
        "inventory_cost": round(inventory_cost, 2),
        "order_procurement_cost": round(order_stats[2] or 0, 2),
        "time_range": {
            "start_date": start_date,
            "end_date": end_date
        }
    }

# ==================== 采购管理 API ====================

@app.post("/admin/purchases")
def record_purchase(
    purchase_data: dict,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """记录采购历史并更新产品库存"""
    product_id = purchase_data.get("product_id")
    purchase_type = purchase_data.get("purchase_type") # 'kit' or 'complete'
    quantity = purchase_data.get("quantity", 1)
    bom_cost = purchase_data.get("bom_cost", 0)
    actual_cost = purchase_data.get("actual_cost", 0)
    # auth 返回的是 API Key 字符串，不是 dict，直接使用默认 user_id
    user_id = 1

    # 1. 记录采购历史
    db.execute(text("""
        INSERT INTO purchases (
            product_id, purchase_type, quantity, bom_cost, actual_cost, user_id
        ) VALUES (
            :product_id, :purchase_type, :quantity, :bom_cost, :actual_cost, :user_id
        )
    """), {
        "product_id": product_id,
        "purchase_type": purchase_type,
        "quantity": quantity,
        "bom_cost": bom_cost,
        "actual_cost": actual_cost,
        "user_id": user_id
    })

    # 2. 更新产品库存
    if purchase_type == "kit":
        # 更新零件包库存
        db.execute(text("""
            UPDATE products 
            SET kit_stock_quantity = COALESCE(kit_stock_quantity, 0) + :quantity
            WHERE id = :product_id
        """), {"quantity": quantity, "product_id": product_id})
    else:
        # 更新整体产品库存
        db.execute(text("""
            UPDATE products 
            SET stock_quantity = COALESCE(stock_quantity, 0) + :quantity
            WHERE id = :product_id
        """), {"quantity": quantity, "product_id": product_id})

    # 3. 添加操作日志
    detail = f"采购{ '零件包' if purchase_type == 'kit' else '整体产品' }：{quantity}件，实际支出 ¥{actual_cost}"
    db.execute(text("""
        INSERT INTO user_logs (user_id, action, detail)
        VALUES (:user_id, 'purchase', :detail)
    """), {"user_id": user_id, "detail": detail})

    db.commit()
    return {"status": "success", "message": "采购记录已保存，库存已更新"}

# ==================== 订单管理 API ====================

@app.get("/orders/")
def get_orders(
    status: str = None,
    order_type: str = None,
    limit: int = 100,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """获取订单列表"""
    query = """
        SELECT o.id, o.order_no, o.customer_name, o.order_type, 
               o.product_sku, o.product_name, o.quantity, o.unit_price, 
               o.total_amount, o.status, o.created_at, u.username as created_by,
               o.product_id
        FROM orders o
        LEFT JOIN users u ON o.created_by = u.id
        WHERE 1=1
    """
    params = {}
    
    if status:
        query += " AND o.status = :status"
        params['status'] = status
    
    if order_type:
        query += " AND o.order_type = :order_type"
        params['order_type'] = order_type
    
    query += " ORDER BY o.created_at DESC LIMIT :limit"
    params['limit'] = limit
    
    orders = db.execute(text(query), params).fetchall()
    
    return [
        {
            "id": o[0],
            "order_no": o[1],
            "customer_name": o[2],
            "order_type": o[3],
            "product_sku": o[4],
            "product_name": o[5],
            "quantity": o[6],
            "unit_price": o[7],
            "total_amount": o[8],
            "status": o[9],
            "created_at": o[10],
            "created_by": o[11],
            "product_id": o[12]
        }
        for o in orders
    ]

# 注意：订单创建 API 已在 880 行定义，此处删除重复定义

@app.get("/orders/{order_id}")
def get_order_detail(order_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    """获取订单详情"""
    # 订单基本信息
    order = db.execute(text("""
        SELECT o.id, o.order_no, o.customer_name, o.customer_contact, o.order_type,
               o.product_sku, o.product_name, o.quantity, o.unit_price,
               o.total_amount, o.status, o.remark, o.created_at, u.username as created_by
        FROM orders o
        LEFT JOIN users u ON o.created_by = u.id
        WHERE o.id = :order_id
    """), {"order_id": order_id}).fetchone()
    
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    # 订单明细（BOM 零件）
    items = db.execute(text("""
        SELECT part_name, specification, quantity, unit_price, total_price, taobao_link, status
        FROM order_items
        WHERE order_id = :order_id
    """), {"order_id": order_id}).fetchall()
    
    return {
        "order": {
            "id": order[0],
            "order_no": order[1],
            "customer_name": order[2],
            "customer_contact": order[3],
            "order_type": order[4],
            "product_sku": order[5],
            "product_name": order[6],
            "quantity": order[7],
            "unit_price": order[8],
            "total_amount": order[9],
            "status": order[10],
            "remark": order[11],
            "created_at": order[12],
            "created_by": order[13]
        },
        "items": [
            {
                "part_name": item[0],
                "specification": item[1],
                "quantity": item[2],
                "unit_price": item[3],
                "total_price": item[4],
                "taobao_link": item[5],
                "status": item[6]
            }
            for item in items
        ]
    }

@app.put("/orders/{order_id}/status")
def update_order_status(
    order_id: int,
    status_data: dict,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """更新订单状态（支持采购成本记录）"""
    new_status = status_data.get("status")
    procurement_cost = status_data.get("procurement_cost", 0)
    
    if new_status not in ["pending", "prepared", "shipped", "completed", "cancelled"]:
        raise HTTPException(status_code=400, detail="无效的状态")
    
    # 获取原状态
    old = db.execute(text("SELECT status FROM orders WHERE id = :id"), {"id": order_id}).fetchone()
    old_status = old[0] if old else None
    
    # 更新订单状态
    # 始终提供所有 SQL 绑定参数的默认值，避免缺失参数错误
    update_fields = {
        "status": new_status,
        "updated_at": beijing_now(),
        "prepared_at": None,
        "procurement_cost": 0
    }
    if new_status == "prepared":
        update_fields["prepared_at"] = beijing_now()
        if procurement_cost > 0:
            update_fields["procurement_cost"] = procurement_cost
    
    db.execute(text("""
        UPDATE orders
        SET status = :status, 
            prepared_at = COALESCE(:prepared_at, prepared_at),
            procurement_cost = CASE WHEN :procurement_cost > 0 THEN :procurement_cost ELSE procurement_cost END,
            updated_at = :updated_at
        WHERE id = :order_id
    """), {**update_fields, "order_id": order_id})
    
    # 记录操作日志
    db.execute(text("""
        INSERT INTO order_logs (order_id, action, old_status, new_status, detail)
        VALUES (:order_id, 'update_status', :old_status, :new_status, :detail)
    """), {
        "order_id": order_id,
        "old_status": old_status,
        "new_status": new_status,
        "detail": f"采购成本：¥{procurement_cost}" if procurement_cost > 0 else ""
    })
    
    db.commit()
    
    return {"status": "success", "message": f"订单状态已更新为 {new_status}"}

@app.delete("/orders/{order_id}")
def delete_order(order_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    """删除订单"""
    db.execute(text("DELETE FROM order_items WHERE order_id = :order_id"), {"order_id": order_id})
    db.execute(text("DELETE FROM orders WHERE id = :order_id"), {"order_id": order_id})
    db.commit()
    
    return {"status": "success", "message": "订单已删除"}

@app.post("/orders/{order_id}/ship")
def ship_order(
    order_id: int,
    ship_data: dict,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """订单发货"""
    shipping_company = ship_data.get("shipping_company", "")
    tracking_no = ship_data.get("tracking_no", "")
    
    # 更新订单
    db.execute(text("""
        UPDATE orders
        SET status = 'shipped', 
            shipping_company = :shipping_company,
            tracking_no = :tracking_no,
            shipped_at = :shipped_at,
            updated_at = :updated_at
        WHERE id = :order_id
    """), {
        "order_id": order_id,
        "shipping_company": shipping_company,
        "tracking_no": tracking_no,
        "shipped_at": beijing_now(),
        "updated_at": beijing_now()
    })
    
    # 记录操作日志
    db.execute(text("""
        INSERT INTO order_logs (order_id, action, old_status, new_status, detail)
        VALUES (:order_id, 'ship', 'prepared', 'shipped', :detail)
    """), {
        "order_id": order_id,
        "detail": f"快递公司：{shipping_company}, 单号：{tracking_no}"
    })
    
    db.commit()
    
    return {"status": "success", "message": "订单已发货"}

@app.post("/admin/orders/{order_id}/allocate-kit")
def allocate_kit_to_order(
    order_id: int,
    alloc_data: dict,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """为订单调用零件包库存"""
    product_id = alloc_data.get("product_id")
    quantity = alloc_data.get("quantity", 1)
    
    # 检查产品库存
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    
    if product.kit_stock_quantity < quantity:
        raise HTTPException(status_code=400, detail=f"零件包库存不足，当前库存：{product.kit_stock_quantity}")
    
    # 扣减库存
    product.kit_stock_quantity -= quantity
    
    # 记录调用日志
    db.execute(text("""
        INSERT INTO kit_allocations (order_id, product_id, kit_sku, kit_name, quantity, kit_cost, total_cost, user_id)
        VALUES (:order_id, :product_id, :kit_sku, :kit_name, :quantity, :kit_cost, :total_cost, 1)
    """), {
        "order_id": order_id,
        "product_id": product_id,
        "kit_sku": product.sku_code,
        "kit_name": product.product_name,
        "quantity": quantity,
        "kit_cost": product.kit_cost or 0,
        "total_cost": (product.kit_cost or 0) * quantity,
        "user_id": 1
    })
    
    # 更新订单关联
    db.execute(text("""
        UPDATE orders
        SET kit_id = :product_id, kit_quantity = :quantity, updated_at = :updated_at
        WHERE id = :order_id
    """), {
        "order_id": order_id,
        "product_id": product_id,
        "quantity": quantity,
        "updated_at": beijing_now()
    })
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"已调用 {quantity} 个零件包",
        "kit_stock_after": product.kit_stock_quantity
    }

@app.get("/admin/orders/{order_id}/procurement-list")
def get_order_procurement_list(
    order_id: int,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """获取订单的采购清单（BOM 拆解 - 已调用零件包）"""
    from sqlalchemy import text
    
    # 获取订单信息
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    
    existing = db.execute(text("""
        SELECT part_name, specs, quantity, unit_cost, total_cost, taobao_link, status
        FROM procurement_lists WHERE order_id = :oid ORDER BY id
    """), {"oid": order_id}).fetchall()

    procurement_list = []
    if existing:
        for item in existing:
            procurement_list.append({
                "part_name": item[0],
                "specs": item[1] or "",
                "quantity": item[2] or 0,
                "unit_cost": item[3] or 0,
                "total_cost": item[4] or 0,
                "taobao_link": item[5] or "",
                "status": item[6] or "pending"
            })
    else:
        procurement_list = build_procurement_items_from_order(order, db)
    
    return {
        "order_id": order_id,
        "order_no": order.order_no,
        "product_name": order.product_name,
        "order_quantity": order.quantity,
        "kit_quantity": order.kit_quantity,
        "total_parts": len(procurement_list),
        "estimated_cost": sum(item["total_cost"] for item in procurement_list),
        "items": procurement_list
    }

@app.get("/admin/orders/{order_id}/procurement-editor")
def get_order_procurement_editor(order_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    data = get_order_procurement_list(order_id, db, auth)
    versions = db.execute(text("""
        SELECT id, version_no, note, created_at
        FROM order_procurement_versions
        WHERE order_id = :oid
        ORDER BY version_no DESC
        LIMIT 10
    """), {"oid": order_id}).fetchall()
    return {
        "order": {
            "id": order.id,
            "order_no": order.order_no,
            "product_name": order.product_name,
            "quantity": order.quantity
        },
        "items": data["items"],
        "versions": [{
            "id": r[0], "version_no": r[1], "note": r[2], "created_at": r[3]
        } for r in versions]
    }

@app.post("/admin/orders/{order_id}/procurement-editor")
def save_order_procurement_editor(order_id: int, payload: ProcurementSaveRequest, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    snapshot_order_procurement_version(order_id, payload.note or "保存前备份", db)
    db.execute(text("DELETE FROM procurement_lists WHERE order_id = :oid"), {"oid": order_id})
    for item in payload.items:
        if not any([
            item.part_name.strip(), item.specs.strip(), item.taobao_link.strip(),
            float(item.quantity or 0) != 0, float(item.unit_cost or 0) != 0, float(item.total_cost or 0) != 0
        ]):
            continue
        db.execute(text("""
            INSERT INTO procurement_lists (order_id, part_name, specs, quantity, unit_cost, total_cost, taobao_link, status)
            VALUES (:order_id, :part_name, :specs, :quantity, :unit_cost, :total_cost, :taobao_link, :status)
        """), {
            "order_id": order_id,
            "part_name": item.part_name,
            "specs": item.specs,
            "quantity": item.quantity,
            "unit_cost": item.unit_cost,
            "total_cost": item.total_cost,
            "taobao_link": item.taobao_link,
            "status": item.status or "pending"
        })
    order.procurement_cost = sum(float(i.total_cost or 0) for i in payload.items)
    order.updated_at = beijing_now()
    new_version = snapshot_order_procurement_version(order_id, payload.note or "手动保存", db)
    db.commit()
    return {"status": "success", "version_no": new_version}

@app.post("/admin/orders/{order_id}/procurement-editor/rollback/{version_id}")
def rollback_order_procurement_editor(order_id: int, version_id: int, db: Session = Depends(get_db), auth=Depends(verify_auth)):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="订单不存在")
    version = db.execute(text("SELECT id, version_no FROM order_procurement_versions WHERE id = :vid AND order_id = :oid"), {
        "vid": version_id, "oid": order_id
    }).fetchone()
    if not version:
        raise HTTPException(status_code=404, detail="版本不存在")
    snapshot_order_procurement_version(order_id, "回滚前备份", db)
    db.execute(text("DELETE FROM procurement_lists WHERE order_id = :oid"), {"oid": order_id})
    rows = db.execute(text("""
        SELECT part_name, specs, quantity, unit_cost, total_cost, taobao_link, status
        FROM order_procurement_version_items WHERE version_id = :vid ORDER BY id
    """), {"vid": version_id}).fetchall()
    for row in rows:
        db.execute(text("""
            INSERT INTO procurement_lists (order_id, part_name, specs, quantity, unit_cost, total_cost, taobao_link, status)
            VALUES (:order_id, :part_name, :specs, :quantity, :unit_cost, :total_cost, :taobao_link, :status)
        """), {
            "order_id": order_id,
            "part_name": row[0], "specs": row[1], "quantity": row[2], "unit_cost": row[3],
            "total_cost": row[4], "taobao_link": row[5], "status": row[6]
        })
    order.procurement_cost = sum(float(r[4] or 0) for r in rows)
    order.updated_at = beijing_now()
    new_version = snapshot_order_procurement_version(order_id, f"回滚到 v{version[1]}", db)
    db.commit()
    return {"status": "success", "version_no": new_version}

@app.post("/admin/orders/{order_id}/save-procurement")
def save_order_procurement(
    order_id: int,
    proc_data: dict,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """保存订单的采购记录"""
    items = proc_data.get("items", [])
    actual_cost = proc_data.get("actual_cost", 0)
    
    # 保存采购清单项
    for item in items:
        db.execute(text("""
            INSERT INTO procurement_lists (order_id, part_name, specs, quantity, unit_cost, total_cost, taobao_link, status)
            VALUES (:order_id, :part_name, :specs, :quantity, :unit_cost, :total_cost, :link, 'purchased')
        """), {
            "order_id": order_id,
            "part_name": item.get("part_name"),
            "specs": item.get("specs", ""),
            "quantity": item.get("quantity", 0),
            "unit_cost": item.get("unit_cost", 0),
            "total_cost": item.get("total_cost", 0),
            "link": item.get("taobao_link", "")
        })
    
    # 更新订单采购成本
    db.execute(text("""
        UPDATE orders
        SET procurement_cost = :cost, updated_at = :updated_at
        WHERE id = :order_id
    """), {
        "cost": actual_cost,
        "order_id": order_id,
        "updated_at": beijing_now()
    })
    
    db.commit()
    
    return {"status": "success", "message": "采购记录已保存"}

@app.get("/admin/orders/bom-consolidated")
def get_consolidated_bom(
    order_ids: str,  # 逗号分隔的订单 ID 列表，如 "1,2,3"
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """生成多个订单的 BOM 总表（汇总相同零件）"""
    from sqlalchemy import text
    import json
    
    # 解析订单 ID 列表
    ids = [int(x.strip()) for x in order_ids.split(',') if x.strip().isdigit()]
    
    if not ids:
        raise HTTPException(status_code=400, detail="请提供有效的订单 ID 列表")
    
    # 汇总所有订单的 BOM
    bom_summary = {}
    order_info = []
    
    for order_id in ids:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            continue
        
        order_info.append({
            "order_id": order_id,
            "order_no": order.order_no,
            "product_name": order.product_name,
            "quantity": order.quantity
        })
        
        # 获取该订单产品的 BOM
        sql = text("""
            SELECT part_name, specs, quantity, link, estimated_cost
            FROM bom_items
            WHERE product_id = :pid
        """)
        result = db.execute(sql, {"pid": order.product_id}).fetchall()
        
        for row in result:
            part_name, specs, quantity_str, link, estimated_cost = row
            try:
                quantity = float(quantity_str) if quantity_str else 0
            except:
                quantity = 0
            
            # 计算该零件的总需求（BOM 用量 × 订单数量）
            total_qty = quantity * order.quantity
            total_cost = (estimated_cost or 0) * total_qty
            
            # 汇总相同零件（零件名 + 规格作为 key）
            key = f"{part_name}___{specs}"
            if key in bom_summary:
                bom_summary[key]['quantity'] += total_qty
                bom_summary[key]['total_cost'] += total_cost
                bom_summary[key]['order_count'] += 1
            else:
                bom_summary[key] = {
                    'part_name': part_name,
                    'specs': specs or '',
                    'quantity': total_qty,
                    'unit_cost': estimated_cost or 0,
                    'total_cost': total_cost,
                    'taobao_link': link or '',
                    'order_count': 1,  # 被多少个订单需要
                    'orders': [order_id]
                }
    
    # 转换为列表并排序
    bom_list = sorted(bom_summary.values(), key=lambda x: x['part_name'])
    
    # 计算总计
    total_parts = len(bom_list)
    total_cost = sum(item['total_cost'] for item in bom_list)
    total_revenue = db.query(func.sum(Order.total_amount)).filter(Order.id.in_(ids)).scalar() or 0
    
    return {
        "order_count": len(ids),
        "orders": order_info,
        "total_parts": total_parts,
        "total_cost": round(total_cost, 2),
        "total_revenue": round(total_revenue, 2),
        "gross_profit": round(total_revenue - total_cost, 2),
        "profit_margin": round((total_revenue - total_cost) / total_revenue * 100, 2) if total_revenue > 0 else 0,
        "bom_items": bom_list
    }

@app.get("/admin/orders/procurement-query")
def query_order_procurement_data(
    search: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """查询所有订单的零部件采购数据（第三项功能：订单采购数据可查询）"""
    from sqlalchemy import text

    # 构建筛选条件
    conditions = ["o.status != 'cancelled'"]
    params = {}
    if search:
        conditions.append("(o.order_no LIKE :search OR o.product_name LIKE :search OR o.customer_name LIKE :search)")
        params["search"] = f"%{search}%"
    if start_date:
        conditions.append("DATE(o.created_at) >= DATE(:start_date)")
        params["start_date"] = start_date
    if end_date:
        conditions.append("DATE(o.created_at) <= DATE(:end_date)")
        params["end_date"] = end_date

    where_clause = " AND ".join(conditions)

    # 获取订单列表
    orders = db.execute(text(f"""
        SELECT o.id, o.order_no, o.product_name, o.product_sku, o.quantity,
               o.total_amount, o.procurement_cost, o.status, o.created_at,
               o.customer_name
        FROM orders o
        WHERE {where_clause}
        ORDER BY o.created_at DESC
    """), params).fetchall()

    result = []
    for row in orders:
        order_id = row[0]
        # 查询该订单的采购明细
        procurement_items = db.execute(text("""
            SELECT part_name, specs, quantity, unit_cost, total_cost, taobao_link, status
            FROM procurement_lists
            WHERE order_id = :oid
            ORDER BY id
        """), {"oid": order_id}).fetchall()

        items = []
        actual_procurement_total = 0
        for item in procurement_items:
            item_total = item[4] or 0
            actual_procurement_total += item_total
            items.append({
                "part_name": item[0],
                "specs": item[1] or "",
                "quantity": item[2] or 0,
                "unit_cost": item[3] or 0,
                "total_cost": item_total,
                "taobao_link": item[5] or "",
                "status": item[6] or "pending"
            })

        result.append({
            "order_id": order_id,
            "order_no": row[1],
            "product_name": row[2] or "",
            "product_sku": row[3] or "",
            "quantity": row[4] or 0,
            "total_amount": row[5] or 0,
            "procurement_cost": row[6] or 0,
            "status": row[7] or "",
            "created_at": str(row[8]) if row[8] else "",
            "customer_name": row[9] or "",
            "parts_count": len(items),
            "actual_procurement_total": round(actual_procurement_total, 2),
            "procurement_items": items
        })

    # 汇总统计
    total_orders = len(result)
    total_revenue = sum(r["total_amount"] for r in result)
    total_procurement = sum(r["procurement_cost"] for r in result)
    total_parts = sum(r["parts_count"] for r in result)

    return {
        "summary": {
            "total_orders": total_orders,
            "total_revenue": round(total_revenue, 2),
            "total_procurement": round(total_procurement, 2),
            "total_profit": round(total_revenue - total_procurement, 2),
            "total_parts": total_parts
        },
        "orders": result
    }


@app.post("/admin/orders/export-bom-csv")
def export_bom_to_csv(
    order_ids: str,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """导出 BOM 总表为 CSV 格式（供插件使用）"""
    import csv
    import io
    from fastapi.responses import StreamingResponse
    
    # 获取 BOM 总表
    bom_data = get_consolidated_bom(order_ids, db, auth)
    
    # 生成 CSV
    output = io.StringIO()
    writer = csv.writer(output)
    
    # 表头
    writer.writerow(['零件名称', '规格', '采购数量', '单价', '总价', '淘宝链接', '备注'])
    
    # 数据行
    for item in bom_data['bom_items']:
        writer.writerow([
            item['part_name'],
            item['specs'],
            item['quantity'],
            item['unit_cost'],
            item['total_cost'],
            item['taobao_link'],
            f"共{item['order_count']}个订单需要"
        ])
    
    # 生成文件
    csv_content = output.getvalue()
    output.close()
    
    # 创建响应
    response = StreamingResponse(
        iter([csv_content.encode('utf-8-sig')]),  # UTF-8 with BOM for Excel
        media_type="text/csv"
    )
    response.headers["Content-Disposition"] = f"attachment; filename=BOM_采购清单_{len(bom_data['orders'])}个订单.csv"
    
    return response

@app.post("/admin/orders/batch-procure")
def batch_procure_orders(
    order_ids: str,
    db: Session = Depends(get_db),
    auth=Depends(verify_auth)
):
    """批量采购：生成每个订单的 BOM 并保存到采购清单"""
    from sqlalchemy import text
    
    # 解析订单 ID 列表
    ids = [int(x.strip()) for x in order_ids.split(',') if x.strip().isdigit()]
    
    # 为了保持返回的统计数据
    bom_data = get_consolidated_bom(order_ids, db, auth)
    
    # 分别获取每个订单的 BOM 并保存到采购清单表
    for order_id in ids:
        order_bom = get_order_bom(order_id, db, auth)
        for item in order_bom.get('bom_items', []):
            db.execute(text("""
                INSERT INTO procurement_lists (order_id, part_name, specs, quantity, unit_cost, total_cost, taobao_link, status)
                VALUES (:order_id, :part_name, :specs, :quantity, :unit_cost, :total_cost, :link, 'pending')
            """), {
                "order_id": order_id,
                "part_name": item['part_name'],
                "specs": item['specs'],
                "quantity": item['quantity'],
                "unit_cost": item['unit_cost'],
                "total_cost": item['total_cost'],
                "link": item['link']
            })
    
    db.commit()
    
    return {
        "status": "success",
        "message": f"已为 {len(ids)} 个订单生成采购清单，共 {bom_data['total_parts']} 个零件",
        "bom_summary": {
            "total_parts": bom_data['total_parts'],
            "total_cost": bom_data['total_cost'],
            "total_revenue": bom_data['total_revenue']
        }
    }
