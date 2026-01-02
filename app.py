import streamlit as st
import pandas as pd
from datetime import datetime
import itertools
import io
import time
import os
from PIL import Image, ImageDraw, ImageFont

# 核心依赖：SQLAlchemy + Supabase
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, inspect, text
from sqlalchemy.orm import declarative_base, Session
from supabase import create_client, Client

# --- 1. 配置与连接 ---
st.set_page_config(page_title="童装国际站", layout="wide", page_icon="🌍")

# 从 Streamlit Secrets 获取敏感信息
# (部署到 Vercel 时，这些信息会从环境变量里读取)
try:
    # 优先尝试从 st.secrets 读取 (本地开发用 .streamlit/secrets.toml)
    # 在 Vercel 上，我们需要用 os.environ 读取环境变量
    DB_URL = st.secrets.get("DB_URL") or os.environ.get("DB_URL")
    SUPABASE_URL = st.secrets.get("SUPABASE_URL") or os.environ.get("SUPABASE_URL")
    SUPABASE_KEY = st.secrets.get("SUPABASE_KEY") or os.environ.get("SUPABASE_KEY")
    
    if not DB_URL or not SUPABASE_URL:
        st.warning("⚠️ 正在尝试连接... (如果是首次部署，请确保在 Vercel 填入了 Environment Variables)")
        st.stop()
except Exception as e:
    st.error(f"配置读取失败: {e}")
    st.stop()

# 连接数据库 (PostgreSQL)
# 修正：Supabase 的连接串通常是 postgresql://... 需要兼容 SQLAlchemy
if DB_URL and DB_URL.startswith("postgres://"):
    DB_URL = DB_URL.replace("postgres://", "postgresql://", 1)

try:
    engine = create_engine(DB_URL, echo=False, pool_pre_ping=True)
    Base = declarative_base()
except Exception as e:
    st.error(f"数据库连接失败，请检查 DB_URL 密码是否正确。错误: {e}")
    st.stop()

# 连接 Storage
try:
    supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    BUCKET_NAME = "images" 
except Exception as e:
    st.error(f"Supabase Storage 连接失败: {e}")
    st.stop()

# --- 数据模型 ---
class User(Base):
    __tablename__ = 'users'
    username = Column(String, primary_key=True)
    role = Column(String)
    created_at = Column(String)
    total_items_bought = Column(Integer, default=0)

class Product(Base):
    __tablename__ = 'products'
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String)
    description = Column(Text)
    status = Column(String, default='active')
    main_image = Column(String, default='')

class SKU(Base):
    __tablename__ = 'skus'
    id = Column(Integer, primary_key=True, autoincrement=True)
    product_id = Column(Integer)
    sku_code = Column(String)
    color = Column(String)
    size = Column(String)
    price = Column(Float)
    stock = Column(Integer)
    image_path = Column(String)

class Order(Base):
    __tablename__ = 'orders'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String)
    items = Column(Text)
    total_price = Column(Float)
    address = Column(Text)
    phone = Column(String)
    order_time = Column(String)
    status = Column(String)
    tracking_number = Column(String, default='')
    item_count = Column(Integer, default=0)

class Setting(Base):
    __tablename__ = 'settings'
    key = Column(String, primary_key=True)
    value = Column(String)

# --- 国际化配置 ---
LANGUAGES = {"中文": "zh", "English": "en", "ไทย": "th"}
DEFAULT_LANG = "th"

TRANSLATIONS = {
    "zh": {
        "app_title": "童装ERP(国际版)", "login_title": "🔐 安全登录", "login_placeholder": "账号", "login_btn": "登录", "login_error": "用户不存在",
        "admin_tabs": ["🚀 发布商品", "📋 商品管理", "📦 订单处理", "⚙️ 规则设置", "👥 用户管理"],
        "user_tabs": ["🛍️ 商城", "🛒 购物车", "📦 我的订单"],
        "product_name_ph": "2026早春新款", "product_desc_label": "商品描述", "color_label": "颜色 (逗号分隔)", "size_label": "尺码 (逗号分隔)",
        "save_btn": "保存", "delete_btn": "删除商品", "order_status": "状态", "ship_status_pending": "待发货", "ship_status_shipped": "已发货", "ship_status_delivered": "交易成功",
        "confirm_ship_btn": "确认发货", "download_waybill": "下载面单", "shipping_fee_title": "运费设置", "vip_rules_title": "会员等级设置",
        "save_settings": "保存设置", "cart_empty": "购物车为空", "submit_order_btn": "提交订单", "order_success": "下单成功！", "my_orders_title": "我的订单",
        "confirm_receipt_btn": "确认收货 (交易成功)", "payment_method": "支付方式：货到付款", "track_num_info": "快递单号: {tracking_number}",
        "product_list_title": "已上架商品", "no_products": "暂无商品", "sku_table_header": "规格明细", "no_sku_info": "暂无规格数据",
        "product_desc_view": "📝 商品描述", "product_image_view": "🖼️ 商品图片",
        "shipping_base": "首件运费", "shipping_extra": "续件运费", "shipping_free": "包邮门槛(件)",
        "vip_l1_c": "银牌门槛(件)", "vip_l1_d": "银牌折扣", "vip_l2_c": "金牌门槛(件)", "vip_l2_d": "金牌折扣", "vip_l3_c": "钻石门槛(件)", "vip_l3_d": "钻石折扣",
        "view_details_btn": "查看详情", "recipient_label": "收件人", "phone_label": "电话", "address_label": "地址",
        "edit_btn": "编辑信息", "cancel_btn": "取消编辑", "save_changes_btn": "保存所有修改", "edit_instruction": "修改基础信息、价格库存及图片",
        "edit_image_title": "🖼️ 修改图片 (按颜色)", "upload_new": "上传新图", "current_img": "当前",
        "main_image_label": "商品主图 (封面)", "upload_main_image": "上传主图", "edit_main_image_title": "🖼️ 修改主图 (封面)"
    },
    "en": {
        "app_title": "Kids Shop ERP", "login_title": "🔐 Login", "login_placeholder": "Username", "login_btn": "Login", "login_error": "User not found",
        "admin_tabs": ["🚀 Add Product", "📋 Products", "📦 Orders", "⚙️ Settings", "👥 Users"],
        "user_tabs": ["🛍️ Shop", "🛒 Cart", "📦 Orders"],
        "product_name_ph": "Product Name", "product_desc_label": "Description", "color_label": "Colors", "size_label": "Sizes",
        "save_btn": "Save", "delete_btn": "Delete", "order_status": "Status", "ship_status_pending": "Pending", "ship_status_shipped": "Shipped", "ship_status_delivered": "Delivered",
        "confirm_ship_btn": "Ship", "download_waybill": "Waybill", "shipping_fee_title": "Shipping Fee", "vip_rules_title": "VIP Levels",
        "save_settings": "Save", "cart_empty": "Cart Empty", "submit_order_btn": "Order", "order_success": "Success!", "my_orders_title": "My Orders",
        "confirm_receipt_btn": "Confirm Receipt", "payment_method": "COD", "track_num_info": "Track: {tracking_number}",
        "product_list_title": "Product List", "no_products": "No Products", "sku_table_header": "Variants", "no_sku_info": "No Variants",
        "product_desc_view": "Description", "product_image_view": "Image",
        "shipping_base": "Base Fee", "shipping_extra": "Extra Fee", "shipping_free": "Free Threshold",
        "vip_l1_c": "Silver Qty", "vip_l1_d": "Silver Disc", "vip_l2_c": "Gold Qty", "vip_l2_d": "Gold Disc", "vip_l3_c": "Diamond Qty", "vip_l3_d": "Diamond Disc",
        "view_details_btn": "View Details", "recipient_label": "Recipient", "phone_label": "Phone", "address_label": "Address",
        "edit_btn": "Edit", "cancel_btn": "Cancel", "save_changes_btn": "Save Changes", "edit_instruction": "Edit details, price, stock and images",
        "edit_image_title": "🖼️ Edit Images (by Color)", "upload_new": "Upload New", "current_img": "Current",
        "main_image_label": "Main Image (Cover)", "upload_main_image": "Upload Cover", "edit_main_image_title": "🖼️ Edit Main Image"
    },
    "th": {
        "app_title": "ร้านเสื้อผ้าเด็ก (ERP)", "login_title": "🔐 เข้าสู่ระบบ", "login_placeholder": "ชื่อผู้ใช้", "login_btn": "เข้าสู่ระบบ", "login_error": "ไม่พบผู้ใช้",
        "admin_tabs": ["🚀 เพิ่มสินค้า", "📋 รายการสินค้า", "📦 จัดการออเดอร์", "⚙️ ตั้งค่า", "👥 ผู้ใช้"],
        "user_tabs": ["🛍️ เลือกซื้อ", "🛒 ตะกร้า", "📦 คำสั่งซื้อ"],
        "product_name_ph": "ชื่อสินค้า", "product_desc_label": "รายละเอียด", "color_label": "สี", "size_label": "ไซส์",
        "save_btn": "บันทึก", "delete_btn": "ลบสินค้า", "order_status": "สถานะ", "ship_status_pending": "รอส่ง", "ship_status_shipped": "ส่งแล้ว", "ship_status_delivered": "สำเร็จ",
        "confirm_ship_btn": "ยืนยันส่ง", "download_waybill": "ใบปะหน้า", "shipping_fee_title": "ค่าจัดส่ง", "vip_rules_title": "ระดับสมาชิก",
        "save_settings": "บันทึก", "cart_empty": "ตะกร้าว่าง", "submit_order_btn": "ยืนยัน", "order_success": "สำเร็จ!", "my_orders_title": "คำสั่งซื้อ",
        "confirm_receipt_btn": "ยืนยันรับของ", "payment_method": "เก็บเงินปลายทาง", "track_num_info": "เลขพัสดุ: {tracking_number}",
        "product_list_title": "รายการสินค้า", "no_products": "ไม่มีสินค้า", "sku_table_header": "รายละเอียด SKU", "no_sku_info": "ไม่มีข้อมูล SKU",
        "product_desc_view": "รายละเอียด", "product_image_view": "รูปภาพ",
        "shipping_base": "ค่าส่งแรกเข้า", "shipping_extra": "ค่าส่งชิ้นต่อไป", "shipping_free": "ส่งฟรีเมื่อครบ(ชิ้น)",
        "vip_l1_c": "Silver ขั้นต่ำ", "vip_l1_d": "ส่วนลด Silver", "vip_l2_c": "Gold ขั้นต่ำ", "vip_l2_d": "ส่วนลด Gold", "vip_l3_c": "Diamond ขั้นต่ำ", "vip_l3_d": "ส่วนลด Diamond",
        "view_details_btn": "ดูรายละเอียด", "recipient_label": "ผู้รับ", "phone_label": "เบอร์โทร", "address_label": "ที่อยู่",
        "edit_btn": "แก้ไข", "cancel_btn": "ยกเลิก", "save_changes_btn": "บันทึกการแก้ไข", "edit_instruction": "แก้ไขข้อมูล ราคา สต็อก และรูปภาพ",
        "edit_image_title": "🖼️ แก้ไขรูปภาพ (ตามสี)", "upload_new": "อัปโหลดใหม่", "current_img": "ปัจจุบัน",
        "main_image_label": "รูปหลัก (ปกสินค้า)", "upload_main_image": "อัปโหลดรูปปก", "edit_main_image_title": "🖼️ แก้ไขรูปปก"
    }
}

def t(key):
    lang_code = st.session_state.get('language', DEFAULT_LANG)
    return TRANSLATIONS.get(lang_code, TRANSLATIONS['th']).get(key, key)

# --- 数据库自动迁移 (PostgreSQL 版) ---
def auto_migrate_db():
    inspector = inspect(engine)
    with engine.connect() as conn:
        Base.metadata.create_all(engine)
        # Postgres 字段检查与补全
        check_cols = {
            'products': ['main_image'],
            'orders': ['tracking_number', 'item_count'],
            'users': ['total_items_bought', 'created_at'],
            'skus': ['sku_code']
        }
        for tbl, cols in check_cols.items():
            existing = [c['name'] for c in inspector.get_columns(tbl)]
            for col in cols:
                if col not in existing:
                    d_type = "VARCHAR" if col in ['main_image', 'tracking_number', 'created_at', 'sku_code'] else "INTEGER"
                    conn.execute(text(f"ALTER TABLE {tbl} ADD COLUMN {col} {d_type}"))
        
        # 初始化设置
        if 'settings' in inspector.get_table_names():
             if not conn.execute(text("SELECT * FROM settings WHERE key='language'")).fetchone():
                 conn.execute(text("INSERT INTO settings (key, value) VALUES ('language', :v)"), {'v': DEFAULT_LANG})
             
             defaults = {'shipping_base':'10', 'shipping_extra':'5', 'free_threshold':'3', 'vip_l1_count':'10', 'vip_l1_discount':'0.95', 'vip_l2_count':'50', 'vip_l2_discount':'0.90', 'vip_l3_count':'100', 'vip_l3_discount':'0.85'}
             for k, v in defaults.items():
                 if not conn.execute(text(f"SELECT * FROM settings WHERE key='{k}'")).fetchone():
                     conn.execute(text(f"INSERT INTO settings (key, value) VALUES ('{k}', '{v}')"))
        conn.commit()

# --- 云存储函数 (Supabase Storage) ---
def save_file_to_supabase(file, prefix):
    if not file: return ""
    try:
        ts = int(time.time())
        ext = file.name.split('.')[-1]
        fname = f"{prefix}_{ts}.{ext}"
        content_type = "image/png" if ext.lower()=='png' else "image/jpeg"
        
        # 上传
        supabase.storage.from_(BUCKET_NAME).upload(path=fname, file=file.getvalue(), file_options={"content-type": content_type})
        # 获取公开链接
        return supabase.storage.from_(BUCKET_NAME).get_public_url(fname)
    except Exception as e:
        st.error(f"Image Upload Failed: {e}")
        return ""

# --- 辅助函数 ---
def get_setting(key, default_value):
    with Session(engine) as session:
        setting = session.query(Setting).filter_by(key=key).first()
        return setting.value if setting else default_value

def format_currency(amount):
    return f"฿ {amount:,.2f}"

def get_font(size=20):
    try: return ImageFont.truetype("arial.ttf", size) 
    except: return ImageFont.load_default()

def generate_waybill(order_obj):
    W, H = 600, 850
    img = Image.new('RGB', (W, H), 'white')
    draw = ImageDraw.Draw(img)
    font_L, font_M = get_font(35), get_font(26)
    black = (0,0,0)
    
    draw.text((20, 20), "PACKING LIST", font=font_L, fill=black)
    draw.line([(20, 70), (580, 70)], fill=black, width=3)
    draw.text((20, 90), f"NO. {order_obj.id}", font=font_M, fill=black)
    draw.rectangle([(20, 140), (580, 280)], outline=black, width=2)
    draw.text((35, 155), f"TO: {order_obj.username}", font=font_L, fill=black)
    draw.text((35, 200), f"TEL: {order_obj.phone}", font=font_L, fill=black)
    draw.text((35, 245), f"ADD: {order_obj.address[:25]}...", font=get_font(22), fill=black)
    draw.text((20, 310), "ITEMS:", font=font_M, fill=black)
    y = 350
    for item in order_obj.items.split('\n'):
        if y > 650: break
        draw.text((30, y), item, font=get_font(20), fill=black)
        y += 40
    draw.line([(20, 700), (580, 700)], fill=black, width=3)
    draw.text((220, 710), f"฿ {order_obj.total_price}", font=get_font(50), fill=(255,0,0))
    if order_obj.tracking_number:
        draw.text((20, 800), f"TRACK: {order_obj.tracking_number}", font=font_M, fill=black)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

def get_vip_and_ship_rules():
    defaults = {'vip_l1_count': '10', 'vip_l1_discount': '0.95', 'vip_l2_count': '50', 'vip_l2_discount': '0.90',
                'vip_l3_count': '100', 'vip_l3_discount': '0.85', 'shipping_base': '10', 'shipping_extra': '5', 'free_threshold': '3'}
    return {k: float(get_setting(k, v)) for k, v in defaults.items()}

def calculate_user_discount(username):
    with Session(engine) as session:
        user = session.query(User).filter_by(username=username).first()
        count = user.total_items_bought if user else 0
    r = get_vip_and_ship_rules()
    if count >= r['vip_l3_count']: return r['vip_l3_discount'], "💎 Diamond", count
    elif count >= r['vip_l2_count']: return r['vip_l2_discount'], "🥇 Gold", count
    elif count >= r['vip_l1_count']: return r['vip_l1_discount'], "🥈 Silver", count
    else: return 1.0, "👶 Normal", count

# --- 后台管理 ---
def admin_page():
    st.title(t("app_title"))
    tabs = st.tabs(TRANSLATIONS[st.session_state.get('language', DEFAULT_LANG)]['admin_tabs'])
    
    # 1. 发布
    with tabs[0]:
        with st.container(border=True):
            p_name = st.text_input(t("product_name_ph"))
            p_desc = st.text_area(t("product_desc_label"))
            main_img_file = st.file_uploader(t("main_image_label"), type=['jpg','png'], key="pub_main")
            c1, c2 = st.columns(2)
            colors = [x.strip() for x in c1.text_area(t("color_label"), "Red,Yellow").replace("，",",").split(',') if x.strip()]
            sizes = [x.strip() for x in c2.text_area(t("size_label"), "S,M").replace("，",",").split(',') if x.strip()]
        
        color_imgs = {}
        if colors:
            cols = st.columns(len(colors))
            for i, c in enumerate(colors):
                f = cols[i].file_uploader(f"{c}", type=['jpg','png'], key=f"u_{c}")
                if f: color_imgs[c] = f

        if p_name and colors and sizes:
            matrix = [{"颜色": c, "尺码": s, "货号(SKU)": f"{c}-{s}", "价格": 99.0, "库存": 100} for c, s in itertools.product(colors, sizes)]
            edited = st.data_editor(pd.DataFrame(matrix), hide_index=True, use_container_width=True)
            if st.button(t("save_btn"), type="primary"):
                with Session(engine) as session:
                    main_path = save_file_to_supabase(main_img_file, "main")
                    new_p = Product(name=p_name, description=p_desc, main_image=main_path)
                    session.add(new_p); session.flush()
                    for _, row in edited.iterrows():
                        c, s = row['颜色'], row['尺码']
                        img_path = save_file_to_supabase(color_imgs.get(c), f"{new_p.id}_{c}")
                        session.add(SKU(product_id=new_p.id, sku_code=row['货号(SKU)'], color=c, size=s, price=row['价格'], stock=row['库存'], image_path=img_path))
                    session.commit()
                st.success("Success!")

    # 2. 商品管理
    with tabs[1]:
        st.subheader(t("product_list_title"))
        with Session(engine) as session:
            products = session.query(Product).filter_by(status='active').order_by(Product.id.desc()).all()
            if not products: st.info(t("no_products"))
            else:
                for p in products:
                    is_editing = st.session_state.get(f'edit_mode_{p.id}', False)
                    skus = session.query(SKU).filter_by(product_id=p.id).all()
                    display_img = p.main_image if p.main_image else next((s.image_path for s in skus if s.image_path), None)
                    
                    with st.expander(f"🆔 {p.id} | {p.name}", expanded=is_editing):
                        if not is_editing:
                            c_img, c_info = st.columns([1, 3])
                            with c_img:
                                if display_img: st.image(display_img, use_container_width=True)
                                else: st.caption("No Image")
                            with c_info:
                                st.write(p.description)
                                if skus:
                                    data = [{"SKU": s.sku_code, "Color": s.color, "Size": s.size, "Price": format_currency(s.price), "Stock": s.stock} for s in skus]
                                    st.dataframe(data, hide_index=True)
                                c_btns = st.columns([1, 1, 4])
                                if c_btns[0].button(f"✏️ {t('edit_btn')}", key=f"e_{p.id}"): st.session_state[f'edit_mode_{p.id}']=True; st.rerun()
                                if c_btns[1].button(f"🗑️ {t('delete_btn')}", key=f"d_{p.id}"):
                                    session.query(SKU).filter_by(product_id=p.id).delete(); session.delete(p); session.commit(); st.rerun()
                        else:
                            new_name = st.text_input("Name", p.name, key=f"en_{p.id}")
                            new_desc = st.text_area("Desc", p.description, key=f"ed_{p.id}")
                            st.markdown(f"#### {t('edit_main_image_title')}")
                            if p.main_image: st.image(p.main_image, width=100)
                            new_main_file = st.file_uploader(t("upload_main_image"), type=['jpg','png'], key=f"em_{p.id}")
                            
                            if skus:
                                sku_data = [{"_id":s.id, "SKU":s.sku_code, "Color":s.color, "Size":s.size, "Price":s.price, "Stock":s.stock} for s in skus]
                                df_edit = st.data_editor(pd.DataFrame(sku_data), key=f"ted_{p.id}", disabled=["_id","Color","Size"], column_config={"_id":None}, use_container_width=True)
                            
                            st.divider(); st.markdown(f"#### {t('edit_image_title')}")
                            new_uploads = {}
                            for color in list(set([s.color for s in skus])):
                                c_cur, c_up = st.columns([1,3])
                                cur_img = next((s.image_path for s in skus if s.color == color and s.image_path), None)
                                with c_cur: 
                                    st.caption(color)
                                    if cur_img: st.image(cur_img, width=60)
                                with c_up:
                                    up = st.file_uploader(f"{t('upload_new')} ({color})", key=f"eu_{p.id}_{color}")
                                    if up: new_uploads[color] = up
                            
                            if st.button(f"💾 {t('save_changes_btn')}", key=f"sv_{p.id}", type="primary"):
                                p.name = new_name; p.description = new_desc
                                if new_main_file: p.main_image = save_file_to_supabase(new_main_file, f"main_{p.id}")
                                for _, row in df_edit.iterrows():
                                    so = session.query(SKU).get(row['_id'])
                                    if so: so.price=row['Price']; so.stock=row['Stock']; so.sku_code=row['SKU']
                                for clr, f in new_uploads.items():
                                    path = save_file_to_supabase(f, f"{p.id}_{clr}")
                                    session.query(SKU).filter_by(product_id=p.id, color=clr).update({"image_path": path})
                                session.commit(); st.session_state[f'edit_mode_{p.id}']=False; st.rerun()
                            if st.button(t("cancel_btn"), key=f"c_{p.id}"): st.session_state[f'edit_mode_{p.id}']=False; st.rerun()

    # 3. 订单
    with tabs[2]:
        with Session(engine) as session:
            for o in session.query(Order).order_by(Order.id.desc()).all():
                icon = "🟢" if o.status == '交易成功' else ("🔵" if o.status == '已发货' else "🟠")
                with st.expander(f"{icon} #{o.id} | {o.username} | {format_currency(o.total_price)}"):
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        st.code(o.items); st.write(f"{o.address} ({o.phone})")
                        if o.status == '待发货':
                            tn = st.text_input("Track No.", key=f"tn_{o.id}")
                            if st.button(t("confirm_ship_btn"), key=f"cs_{o.id}"):
                                o.status='已发货'; o.tracking_number=tn; session.commit(); st.rerun()
                        elif o.status == '已发货': st.info(f"Track: {o.tracking_number}")
                    with c2:
                        wb = generate_waybill(o); st.image(wb, width=150)
                        st.download_button(t("download_waybill"), wb, f"wb_{o.id}.png", "image/png")

    # 4. 设置
    with tabs[3]:
        r = get_vip_and_ship_rules()
        with st.form("set"):
            st.subheader(t("shipping_fee_title"))
            c1, c2, c3 = st.columns(3)
            sb = c1.number_input(t("shipping_base"), value=r['shipping_base'])
            se = c2.number_input(t("shipping_extra"), value=r['shipping_extra'])
            st_val = c3.number_input(t("shipping_free"), value=r['free_threshold'])
            st.divider(); st.subheader(t("vip_rules_title"))
            rc1, rc2 = st.columns(2); l1c = rc1.number_input(t("vip_l1_c"), value=int(r['vip_l1_count'])); l1d = rc2.number_input(t("vip_l1_d"), value=r['vip_l1_discount'])
            rc3, rc4 = st.columns(2); l2c = rc3.number_input(t("vip_l2_c"), value=int(r['vip_l2_count'])); l2d = rc4.number_input(t("vip_l2_d"), value=r['vip_l2_discount'])
            rc5, rc6 = st.columns(2); l3c = rc5.number_input(t("vip_l3_c"), value=int(r['vip_l3_count'])); l3d = rc6.number_input(t("vip_l3_d"), value=r['vip_l3_discount'])
            if st.form_submit_button(t("save_settings")):
                with Session(engine) as session:
                    map_val = {'shipping_base':sb, 'shipping_extra':se, 'free_threshold':st_val, 'vip_l1_count':l1c, 'vip_l1_discount':l1d, 'vip_l2_count':l2c, 'vip_l2_discount':l2d, 'vip_l3_count':l3c, 'vip_l3_discount':l3d}
                    for k,v in map_val.items():
                        s=session.query(Setting).filter_by(key=k).first()
                        if s: s.value=str(v)
                        else: session.add(Setting(key=k, value=str(v)))
                    session.commit(); st.success("Saved")

    # 5. 用户
    with tabs[4]:
        nu = st.text_input("New User")
        if st.button("Add"):
            with Session(engine) as session:
                if not session.query(User).filter_by(username=nu).first():
                    session.add(User(username=nu, role='user', created_at=str(datetime.now())))
                    session.commit(); st.success("Added")
        with Session(engine) as session:
            users = session.query(User).filter(User.role!='admin').all()
            if users: st.dataframe([{"User":u.username, "Items":u.total_items_bought} for u in users])

# --- 前台 ---
def user_page():
    if 'cart' not in st.session_state: st.session_state['cart'] = []
    disc, lvl, cnt = calculate_user_discount(st.session_state['user'])
    with st.sidebar:
        st.info(f"{st.session_state['user']}\n{lvl} (-{int((1-disc)*100)}%)")
        if st.button("Logout"): st.session_state['logged_in']=False; st.rerun()

    t_names = TRANSLATIONS[st.session_state.get('language', DEFAULT_LANG)]['user_tabs']
    t1, t2, t3 = st.tabs(t_names)

    with t1: # Shop
        with Session(engine) as session:
            for p in session.query(Product).filter_by(status='active').all():
                with st.container(border=True):
                    c1, c2 = st.columns([1,3])
                    skus = session.query(SKU).filter_by(product_id=p.id).all()
                    if not skus: continue
                    m_img = p.main_image if p.main_image else next((s.image_path for s in skus if s.image_path), None)
                    with c2:
                        st.subheader(p.name)
                        colors = list(set([s.color for s in skus]))
                        sel_c = st.pills("Color", colors, key=f"sc_{p.id}")
                        if sel_c:
                            target_img = next((s.image_path for s in skus if s.color==sel_c and s.image_path), None)
                            if target_img: m_img = target_img
                            sizes = [s.size for s in skus if s.color==sel_c]
                            sel_s = st.pills("Size", sizes, key=f"ss_{p.id}")
                            if sel_s:
                                target = next(s for s in skus if s.color==sel_c and s.size==sel_s)
                                st.write(f"#### {format_currency(target.price * disc)}")
                                if st.button(t("add_to_cart_btn"), key=f"ab_{target.id}", type="primary"):
                                    st.session_state['cart'].append({"name":p.name, "sku":target.sku_code, "spec":f"{sel_c}/{sel_s}", "price":target.price*disc, "img":target.image_path})
                                    st.toast("Added")
                    with c1:
                        if m_img: st.image(m_img, use_container_width=True)

    with t2: # Cart
        cart = st.session_state['cart']
        if not cart: st.info(t("cart_empty"))
        else:
            total = sum(item['price'] for item in cart)
            for i, item in enumerate(cart):
                c1, c2 = st.columns([1,4])
                with c1: 
                    if item['img']: st.image(item['img'])
                with c2:
                    st.write(f"**{item['name']}** {item['spec']}"); st.write(format_currency(item['price']))
                    if st.button("Del", key=f"cd_{i}"): cart.pop(i); st.rerun()
            st.divider(); st.write(f"Total: :red[{format_currency(total)}]")
            with st.form("co"):
                name = st.text_input(t("recipient_label")); phone = st.text_input(t("phone_label")); addr = st.text_area(t("address_label"))
                if st.form_submit_button(t("submit_order_btn"), type="primary"):
                    if name:
                        with Session(engine) as session:
                            items_str = "\n".join([f"[{x['sku']}] {x['name']} {x['spec']}" for x in cart])
                            session.add(Order(username=st.session_state['user'], items=items_str, total_price=total, address=f"{addr} ({name})", phone=phone, order_time=str(datetime.now()), status='待发货', item_count=len(cart)))
                            session.commit()
                        st.session_state['cart']=[]; st.success(t("order_success")); st.rerun()

    with t3: # My Orders
        with Session(engine) as session:
            for o in session.query(Order).filter_by(username=st.session_state['user']).order_by(Order.id.desc()).all():
                with st.container(border=True):
                    st.write(f"#{o.id} | {o.status} | {format_currency(o.total_price)}")
                    st.caption(f"Track: {o.tracking_number if o.tracking_number else '-'}")
                    with st.expander(t("view_details_btn")):
                        st.code(o.items); st.caption(f"{t('address_label')}: {o.address} ({o.phone})")
                    if o.status == '已发货':
                        if st.button(t("confirm_receipt_btn"), key=f"cr_{o.id}"):
                            o.status='交易成功'
                            u = session.query(User).filter_by(username=st.session_state['user']).first()
                            u.total_items_bought += o.item_count
                            session.commit(); st.rerun()

if __name__ == "__main__":
    auto_migrate_db()
    with Session(engine) as session:
        if not session.query(User).filter_by(username='admin').first():
            session.add(User(username='admin', role='admin', created_at=str(datetime.now())))
            session.commit()
    main()
