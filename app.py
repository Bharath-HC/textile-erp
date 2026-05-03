"""
TextileERP v2 — Full-Stack Retail Showroom ERP
Features: Staff Organiser (Profile/Salary/Leaves), Geofenced Attendance, Sales Returns
"""

from flask import Flask, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, date, timedelta
from functools import wraps
import os, json, io, math
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.units import inch
from sqlalchemy import func

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'textile-erp-v2-secret-2024-xK9mP')
# Use /tmp for Render (ephemeral but writable), or local instance folder
import os as _os
_db_dir = '/tmp' if _os.environ.get('RENDER') else _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'instance')
_os.makedirs(_db_dir, exist_ok=True)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{_db_dir}/textile_erp.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
_upload_dir = '/tmp/uploads' if os.environ.get('RENDER') else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
os.makedirs(_upload_dir, exist_ok=True)
app.config['UPLOAD_FOLDER'] = _upload_dir
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

STORE_LAT = 14.4644
STORE_LNG = 75.9218
STORE_RADIUS_M = 300

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# ─── Models ────────────────────────────────────────────────────────────────────

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='staff')
    full_name = db.Column(db.String(120))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    def set_password(self, p): self.password_hash = generate_password_hash(p)
    def check_password(self, p): return check_password_hash(self.password_hash, p)

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)
    description = db.Column(db.String(200))
    products = db.relationship('Product', backref='category_ref', lazy=True)

class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    size = db.Column(db.String(20))
    color = db.Column(db.String(50))
    price = db.Column(db.Float, nullable=False)
    cost_price = db.Column(db.Float, default=0)
    quantity = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, default=10)
    barcode = db.Column(db.String(50), unique=True)
    image_path = db.Column(db.String(200))
    gst_rate = db.Column(db.Float, default=5.0)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    @property
    def is_low_stock(self): return self.quantity <= self.low_stock_threshold
    @property
    def category_name(self): return self.category_ref.name if self.category_ref else 'N/A'

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    invoice_number = db.Column(db.String(25), unique=True, nullable=False)
    customer_name = db.Column(db.String(120), default='Walk-in Customer')
    customer_phone = db.Column(db.String(20))
    subtotal = db.Column(db.Float, default=0)
    gst_amount = db.Column(db.Float, default=0)
    discount = db.Column(db.Float, default=0)
    total_amount = db.Column(db.Float, default=0)
    payment_method = db.Column(db.String(20), default='cash')
    created_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_returned = db.Column(db.Boolean, default=False)
    items = db.relationship('SaleItem', backref='sale', lazy=True, cascade='all, delete-orphan')
    staff = db.relationship('User', backref='sales', foreign_keys=[created_by])
    returns = db.relationship('SaleReturn', backref='original_sale', lazy=True)

class SaleItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    gst_rate = db.Column(db.Float, default=0)
    total_price = db.Column(db.Float, nullable=False)
    returned_qty = db.Column(db.Integer, default=0)
    product = db.relationship('Product', backref='sale_items')

class SaleReturn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    return_number = db.Column(db.String(25), unique=True, nullable=False)
    sale_id = db.Column(db.Integer, db.ForeignKey('sale.id'), nullable=False)
    customer_name = db.Column(db.String(120))
    customer_phone = db.Column(db.String(20))
    return_reason = db.Column(db.String(300))
    refund_amount = db.Column(db.Float, default=0)
    refund_method = db.Column(db.String(20), default='cash')
    processed_by = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    return_items = db.relationship('ReturnItem', backref='sale_return', lazy=True, cascade='all, delete-orphan')
    processor = db.relationship('User', foreign_keys=[processed_by])

class ReturnItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    return_id = db.Column(db.Integer, db.ForeignKey('sale_return.id'), nullable=False)
    sale_item_id = db.Column(db.Integer, db.ForeignKey('sale_item.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    unit_price = db.Column(db.Float, nullable=False)
    refund_price = db.Column(db.Float, nullable=False)
    sale_item = db.relationship('SaleItem')
    product = db.relationship('Product')

class Employee(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.String(20), unique=True, nullable=False)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120))
    phone = db.Column(db.String(20))
    role = db.Column(db.String(50), default='Staff')
    department = db.Column(db.String(80))
    salary = db.Column(db.Float, default=0)
    join_date = db.Column(db.Date, default=date.today)
    is_active = db.Column(db.Boolean, default=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    casual_leaves = db.Column(db.Integer, default=12)
    sick_leaves = db.Column(db.Integer, default=6)
    earned_leaves = db.Column(db.Integer, default=15)
    user = db.relationship('User', backref='employee_profile', foreign_keys=[user_id])
    attendances = db.relationship('Attendance', backref='employee', lazy=True)
    leave_applications = db.relationship('LeaveApplication', backref='employee', lazy=True)

    @property
    def total_leave_entitlement(self):
        return self.casual_leaves + self.sick_leaves + self.earned_leaves

    @property
    def leaves_used(self):
        year = date.today().year
        approved = LeaveApplication.query.filter_by(employee_id=self.id, status='approved').all()
        return sum(a.days for a in approved if a.from_date and a.from_date.year == year)

    @property
    def leaves_remaining(self):
        return max(0, self.total_leave_entitlement - self.leaves_used)

class Attendance(db.Model):
    """4 punches/day: session1 in/out + session2 in/out"""
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    date = db.Column(db.Date, default=date.today)
    status = db.Column(db.String(20), default='present')
    # Session 1
    check_in   = db.Column(db.DateTime)
    check_out  = db.Column(db.DateTime)
    geo_in     = db.Column(db.Boolean, default=False)
    # Session 2
    check_in2  = db.Column(db.DateTime)
    check_out2 = db.Column(db.DateTime)
    geo_in2    = db.Column(db.Boolean, default=False)
    # Meta
    marked_by  = db.Column(db.Integer, db.ForeignKey('user.id'))
    notes      = db.Column(db.String(200))
    self_marked = db.Column(db.Boolean, default=False)
    latitude   = db.Column(db.Float)
    longitude  = db.Column(db.Float)
    within_geofence = db.Column(db.Boolean, default=False)
    __table_args__ = (db.UniqueConstraint('employee_id', 'date', name='unique_attendance'),)

    @property
    def total_hours(self):
        total = 0
        if self.check_in and self.check_out:
            total += (self.check_out - self.check_in).total_seconds() / 3600
        if self.check_in2 and self.check_out2:
            total += (self.check_out2 - self.check_in2).total_seconds() / 3600
        return round(total, 2)

    @property
    def next_action(self):
        if not self.check_in:   return 'checkin'
        if not self.check_out:  return 'checkout'
        if not self.check_in2:  return 'checkin2'
        if not self.check_out2: return 'checkout2'
        return 'done'

class LeaveApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey('employee.id'), nullable=False)
    leave_type = db.Column(db.String(30), default='casual')
    from_date = db.Column(db.Date, nullable=False)
    to_date = db.Column(db.Date, nullable=False)
    days = db.Column(db.Integer, default=1)
    reason = db.Column(db.String(300))
    status = db.Column(db.String(20), default='pending')
    applied_on = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reviewed_on = db.Column(db.DateTime)
    review_note = db.Column(db.String(200))
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])

# ─── Helpers ────────────────────────────────────────────────────────────────────

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def gen_invoice():
    today = date.today(); prefix = f"INV{today.strftime('%Y%m%d')}"
    last = Sale.query.filter(Sale.invoice_number.like(f"{prefix}%")).order_by(Sale.id.desc()).first()
    return f"{prefix}{(int(last.invoice_number[-4:])+1 if last else 1):04d}"

def gen_return():
    today = date.today(); prefix = f"RET{today.strftime('%Y%m%d')}"
    last = SaleReturn.query.filter(SaleReturn.return_number.like(f"{prefix}%")).order_by(SaleReturn.id.desc()).first()
    return f"{prefix}{(int(last.return_number[-4:])+1 if last else 1):04d}"

def haversine(lat1, lng1, lat2, lng2):
    R = 6371000
    p1,p2 = math.radians(lat1), math.radians(lat2)
    dp,dl = math.radians(lat2-lat1), math.radians(lng2-lng1)
    a = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(a))

@login_manager.user_loader
def load_user(uid): return User.query.get(int(uid))

# ─── Auth ────────────────────────────────────────────────────────────────────────

@app.route('/')
def index(): return redirect(url_for('dashboard') if current_user.is_authenticated else url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated: return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user = User.query.filter_by(username=request.form.get('username')).first()
        if user and user.check_password(request.form.get('password')) and user.is_active:
            login_user(user)
            flash(f'Welcome back, {user.full_name or user.username}!', 'success')
            return redirect(url_for('dashboard'))
        flash('Invalid credentials.', 'danger')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user(); flash('Logged out.', 'info'); return redirect(url_for('login'))

# ─── Dashboard ────────────────────────────────────────────────────────────────────

@app.route('/dashboard')
@login_required
def dashboard():
    today = date.today()
    if current_user.role == 'staff':
        emp = Employee.query.filter_by(user_id=current_user.id).first()
        today_att = Attendance.query.filter_by(employee_id=emp.id if emp else -1, date=today).first() if emp else None
        pending_leaves = LeaveApplication.query.filter_by(employee_id=emp.id if emp else -1, status='pending').count() if emp else 0
        return render_template('staff_dashboard.html', emp=emp, today_att=today_att,
                               pending_leaves=pending_leaves, today=today,
                               store_lat=STORE_LAT, store_lng=STORE_LNG, store_radius=STORE_RADIUS_M)
    # Admin
    total_products = Product.query.count()
    low_stock_count = Product.query.filter(Product.quantity <= Product.low_stock_threshold).count()
    total_employees = Employee.query.filter_by(is_active=True).count()
    today_sales = db.session.query(func.sum(Sale.total_amount)).filter(func.date(Sale.created_at)==today).scalar() or 0
    month_sales = db.session.query(func.sum(Sale.total_amount)).filter(Sale.created_at>=today.replace(day=1)).scalar() or 0
    total_revenue = db.session.query(func.sum(Sale.total_amount)).scalar() or 0
    total_returns = db.session.query(func.sum(SaleReturn.refund_amount)).scalar() or 0
    today_present = Attendance.query.filter_by(date=today, status='present').count()
    pending_leaves = LeaveApplication.query.filter_by(status='pending').count()
    recent_sales = Sale.query.order_by(Sale.created_at.desc()).limit(5).all()
    top_products = db.session.query(Product.name, func.sum(SaleItem.quantity).label('ts'))\
        .join(SaleItem, Product.id==SaleItem.product_id).group_by(Product.id)\
        .order_by(func.sum(SaleItem.quantity).desc()).limit(5).all()
    sales_trend = []
    for i in range(6,-1,-1):
        d = today - timedelta(days=i)
        amt = db.session.query(func.sum(Sale.total_amount)).filter(func.date(Sale.created_at)==d).scalar() or 0
        sales_trend.append({'date':d.strftime('%d %b'),'amount':round(amt,2)})
    cat_sales = db.session.query(Category.name, func.sum(SaleItem.total_price).label('r'))\
        .join(Product, Category.id==Product.category_id)\
        .join(SaleItem, Product.id==SaleItem.product_id).group_by(Category.id).all()
    low_stock_products = Product.query.filter(Product.quantity<=Product.low_stock_threshold)\
        .order_by(Product.quantity.asc()).limit(5).all()
    return render_template('dashboard.html',
        total_products=total_products, low_stock_count=low_stock_count,
        total_employees=total_employees, today_sales=today_sales,
        month_sales=month_sales, total_revenue=total_revenue, total_returns=total_returns,
        today_present=today_present, pending_leaves=pending_leaves,
        recent_sales=recent_sales, top_products=top_products,
        sales_trend=json.dumps(sales_trend),
        cat_sales=json.dumps([{'name':c.name,'revenue':round(c.r or 0,2)} for c in cat_sales]),
        low_stock_products=low_stock_products)

# ─── Products ────────────────────────────────────────────────────────────────────

@app.route('/products')
@login_required
def products():
    search = request.args.get('search',''); cat_f = request.args.get('category',''); sort = request.args.get('sort','name')
    q = Product.query
    if search: q = q.filter((Product.name.ilike(f'%{search}%'))|(Product.barcode.ilike(f'%{search}%')))
    if cat_f: q = q.filter(Product.category_id==cat_f)
    if sort=='price': q=q.order_by(Product.price)
    elif sort=='quantity': q=q.order_by(Product.quantity)
    else: q=q.order_by(Product.name)
    return render_template('products.html', products=q.all(), categories=Category.query.all(),
                           search=search, category_filter=cat_f, sort=sort)

@app.route('/products/add', methods=['GET','POST'])
@login_required
@admin_required
def add_product():
    if request.method == 'POST':
        img = None
        f = request.files.get('image')
        if f and f.filename and allowed_file(f.filename):
            fn = secure_filename(f"{datetime.now().timestamp()}_{f.filename}")
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn)); img = f"uploads/{fn}"
        db.session.add(Product(name=request.form['name'], category_id=request.form['category_id'],
            size=request.form.get('size'), color=request.form.get('color'),
            price=float(request.form['price']), cost_price=float(request.form.get('cost_price',0)),
            quantity=int(request.form.get('quantity',0)),
            low_stock_threshold=int(request.form.get('low_stock_threshold',10)),
            barcode=request.form.get('barcode'), gst_rate=float(request.form.get('gst_rate',5)),
            description=request.form.get('description'), image_path=img))
        db.session.commit(); flash('Product added!','success')
        return redirect(url_for('products'))
    return render_template('product_form.html', product=None, categories=Category.query.all())

@app.route('/products/edit/<int:id>', methods=['GET','POST'])
@login_required
@admin_required
def edit_product(id):
    p = Product.query.get_or_404(id)
    if request.method == 'POST':
        f = request.files.get('image')
        if f and f.filename and allowed_file(f.filename):
            fn = secure_filename(f"{datetime.now().timestamp()}_{f.filename}")
            os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn)); p.image_path = f"uploads/{fn}"
        p.name=request.form['name']; p.category_id=request.form['category_id']
        p.size=request.form.get('size'); p.color=request.form.get('color')
        p.price=float(request.form['price']); p.cost_price=float(request.form.get('cost_price',0))
        p.quantity=int(request.form.get('quantity',0))
        p.low_stock_threshold=int(request.form.get('low_stock_threshold',10))
        p.barcode=request.form.get('barcode'); p.gst_rate=float(request.form.get('gst_rate',5))
        p.description=request.form.get('description')
        db.session.commit(); flash('Product updated!','success')
        return redirect(url_for('products'))
    return render_template('product_form.html', product=p, categories=Category.query.all())

@app.route('/products/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_product(id):
    p = Product.query.get_or_404(id)
    db.session.delete(p); db.session.commit(); flash('Deleted.','success')
    return redirect(url_for('products'))

@app.route('/api/product/barcode/<bc>')
@login_required
def product_by_barcode(bc):
    p = Product.query.filter_by(barcode=bc).first()
    if p: return jsonify({'id':p.id,'name':p.name,'price':p.price,'quantity':p.quantity,'gst_rate':p.gst_rate,'image':p.image_path or '','category':p.category_name})
    return jsonify({'error':'Not found'}),404

@app.route('/api/product/search')
@login_required
def product_search_api():
    q = request.args.get('q','')
    ps = Product.query.filter((Product.name.ilike(f'%{q}%'))|(Product.barcode.ilike(f'%{q}%'))).filter(Product.quantity>0).limit(10).all()
    return jsonify([{'id':p.id,'name':p.name,'price':p.price,'quantity':p.quantity,'barcode':p.barcode or '','gst_rate':p.gst_rate,'category':p.category_name,'image':p.image_path or ''} for p in ps])

# ─── Billing ────────────────────────────────────────────────────────────────────

@app.route('/billing')
@login_required
def billing():
    return render_template('billing.html')

@app.route('/billing/complete', methods=['POST'])
@login_required
def complete_sale():
    data = request.get_json()
    if not data or not data.get('items'): return jsonify({'error':'No items'}),400
    sale = Sale(invoice_number=gen_invoice(), customer_name=data.get('customer_name','Walk-in Customer'),
        customer_phone=data.get('customer_phone',''), subtotal=data.get('subtotal',0),
        gst_amount=data.get('gst_amount',0), discount=data.get('discount',0),
        total_amount=data.get('total',0), payment_method=data.get('payment_method','cash'),
        created_by=current_user.id)
    db.session.add(sale); db.session.flush()
    for item in data['items']:
        p = Product.query.get(item['product_id'])
        if not p or p.quantity < item['quantity']:
            db.session.rollback(); return jsonify({'error':f'Insufficient stock for {p.name if p else "product"}'}),400
        p.quantity -= item['quantity']
        db.session.add(SaleItem(sale_id=sale.id, product_id=item['product_id'],
            quantity=item['quantity'], unit_price=item['price'],
            gst_rate=item.get('gst_rate',0), total_price=item['total']))
    db.session.commit()
    return jsonify({'success':True,'invoice_number':sale.invoice_number,'sale_id':sale.id})

@app.route('/billing/invoice/<int:sale_id>')
@login_required
def view_invoice(sale_id):
    return render_template('invoice.html', sale=Sale.query.get_or_404(sale_id))

@app.route('/billing/invoice/<int:sale_id>/pdf')
@login_required
def download_invoice_pdf(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet(); story = []
    story.append(Paragraph("TEXTILE SHOWROOM", ParagraphStyle('T',parent=styles['Title'],fontSize=22,textColor=colors.HexColor('#1a1a2e'),spaceAfter=4)))
    story.append(Paragraph("Your Fashion Destination | GST: 29AAXXXX1234Z1", ParagraphStyle('S',parent=styles['Normal'],fontSize=10,textColor=colors.HexColor('#666'),spaceAfter=2)))
    story.append(Spacer(1,0.2*inch))
    info = Table([['Invoice No:',sale.invoice_number,'Date:',sale.created_at.strftime('%d %b %Y %I:%M %p')],
                  ['Customer:',sale.customer_name,'Phone:',sale.customer_phone or '-'],
                  ['Payment:',sale.payment_method.upper(),'Staff:',sale.staff.full_name if sale.staff else '-']],
                 colWidths=[1.2*inch,2*inch,1.2*inch,2*inch])
    info.setStyle(TableStyle([('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    story.append(info); story.append(Spacer(1,0.2*inch))
    idata = [['#','Product','Qty','Unit Price','GST%','Total']]
    for i,item in enumerate(sale.items,1):
        idata.append([str(i),item.product.name if item.product else 'N/A',str(item.quantity),f"₹{item.unit_price:.2f}",f"{item.gst_rate}%",f"₹{item.total_price:.2f}"])
    it = Table(idata, colWidths=[0.4*inch,3*inch,0.6*inch,1.2*inch,0.8*inch,1.2*inch])
    it.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a1a2e')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.white,colors.HexColor('#f8f9fa')]),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#dee2e6')),('ALIGN',(2,0),(-1,-1),'RIGHT'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.append(it); story.append(Spacer(1,0.15*inch))
    tot = Table([['','','Subtotal:',f"₹{sale.subtotal:.2f}"],['','','GST:',f"₹{sale.gst_amount:.2f}"],
                 ['','','Discount:',f"-₹{sale.discount:.2f}"],['','','TOTAL:',f"₹{sale.total_amount:.2f}"]],
                colWidths=[2*inch,2*inch,1.5*inch,1.8*inch])
    tot.setStyle(TableStyle([('FONTNAME',(2,0),(-1,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),10),('FONTSIZE',(2,3),(-1,3),13),('BACKGROUND',(2,3),(-1,3),colors.HexColor('#1a1a2e')),('TEXTCOLOR',(2,3),(-1,3),colors.white),('ALIGN',(2,0),(-1,-1),'RIGHT'),('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    story.append(tot); story.append(Spacer(1,0.3*inch))
    story.append(Paragraph("Thank you for shopping with us!", ParagraphStyle('f',parent=styles['Normal'],alignment=1,textColor=colors.HexColor('#888'))))
    doc.build(story); buffer.seek(0)
    return send_file(buffer,as_attachment=True,download_name=f"invoice_{sale.invoice_number}.pdf",mimetype='application/pdf')

# ─── Sales Returns ────────────────────────────────────────────────────────────────

@app.route('/sales/return/<int:sale_id>', methods=['GET','POST'])
@login_required
@admin_required
def sale_return(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    if request.method == 'POST':
        data = request.get_json()
        if not data or not data.get('items'): return jsonify({'error':'No items'}),400
        refund_total = sum(i['refund'] for i in data['items'])
        ret = SaleReturn(return_number=gen_return(), sale_id=sale.id,
            customer_name=data.get('customer_name', sale.customer_name),
            customer_phone=data.get('customer_phone', sale.customer_phone or ''),
            return_reason=data.get('reason',''), refund_amount=refund_total,
            refund_method=data.get('refund_method','cash'), processed_by=current_user.id)
        db.session.add(ret); db.session.flush()
        for ri in data['items']:
            si = SaleItem.query.get(ri['sale_item_id'])
            if not si: continue
            si.returned_qty = (si.returned_qty or 0) + ri['qty']
            p = Product.query.get(ri['product_id'])
            if p: p.quantity += ri['qty']
            db.session.add(ReturnItem(return_id=ret.id, sale_item_id=si.id,
                product_id=ri['product_id'], quantity=ri['qty'],
                unit_price=si.unit_price, refund_price=ri['refund']))
        sale.total_amount = max(0, sale.total_amount - refund_total)
        if all((i.returned_qty or 0) >= i.quantity for i in sale.items): sale.is_returned = True
        db.session.commit()
        return jsonify({'success':True,'return_number':ret.return_number,'return_id':ret.id,'refund':refund_total})
    return render_template('sale_return.html', sale=sale)

@app.route('/sales/returns')
@login_required
@admin_required
def all_returns():
    returns = SaleReturn.query.order_by(SaleReturn.created_at.desc()).all()
    return render_template('returns_list.html', returns=returns)

@app.route('/sales/return/credit/<int:ret_id>/pdf')
@login_required
def download_credit_note(ret_id):
    ret = SaleReturn.query.get_or_404(ret_id)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=0.5*inch, bottomMargin=0.5*inch)
    styles = getSampleStyleSheet(); story = []
    story.append(Paragraph("CREDIT NOTE", ParagraphStyle('CN',parent=styles['Title'],fontSize=24,textColor=colors.HexColor('#e94560'),spaceAfter=4)))
    story.append(Paragraph("TEXTILE SHOWROOM | GST: 29AAXXXX1234Z1", ParagraphStyle('S',parent=styles['Normal'],fontSize=10,textColor=colors.HexColor('#666'))))
    story.append(Spacer(1,0.2*inch))
    info = Table([['Return No:',ret.return_number,'Date:',ret.created_at.strftime('%d %b %Y %I:%M %p')],
                  ['Original Inv:',ret.original_sale.invoice_number,'Refund Method:',ret.refund_method.upper()],
                  ['Customer:',ret.customer_name,'Reason:',ret.return_reason or '-']],
                 colWidths=[1.4*inch,1.8*inch,1.4*inch,2*inch])
    info.setStyle(TableStyle([('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    story.append(info); story.append(Spacer(1,0.2*inch))
    idata=[['#','Product','Qty Returned','Unit Price','Refund Amount']]
    for i,ri in enumerate(ret.return_items,1):
        idata.append([str(i),ri.product.name if ri.product else 'N/A',str(ri.quantity),f"₹{ri.unit_price:.2f}",f"₹{ri.refund_price:.2f}"])
    idata.append(['','','','TOTAL REFUND:',f"₹{ret.refund_amount:.2f}"])
    it=Table(idata,colWidths=[0.4*inch,3.4*inch,1*inch,1.2*inch,1.2*inch])
    it.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e94560')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('GRID',(0,0),(-1,-2),0.5,colors.HexColor('#dee2e6')),('ALIGN',(2,0),(-1,-1),'RIGHT'),('FONTNAME',(3,-1),(4,-1),'Helvetica-Bold'),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.append(it)
    doc.build(story); buffer.seek(0)
    return send_file(buffer,as_attachment=True,download_name=f"credit_note_{ret.return_number}.pdf",mimetype='application/pdf')

@app.route('/sales')
@login_required
def sales():
    page = request.args.get('page',1,type=int); search = request.args.get('search','')
    q = Sale.query
    if search: q=q.filter((Sale.invoice_number.ilike(f'%{search}%'))|(Sale.customer_name.ilike(f'%{search}%')))
    return render_template('sales.html', sales=q.order_by(Sale.created_at.desc()).paginate(page=page,per_page=20), search=search)

# ─── Analytics ────────────────────────────────────────────────────────────────────

@app.route('/analytics')
@login_required
@admin_required
def analytics():
    today = date.today()
    monthly = []
    for i in range(5,-1,-1):
        m=today.month-i; y=today.year
        while m<=0: m+=12; y-=1
        start=date(y,m,1); em=m%12+1; ey=y+(1 if m==12 else 0); end=date(ey,em,1)
        amt=db.session.query(func.sum(Sale.total_amount)).filter(Sale.created_at>=start,Sale.created_at<end).scalar() or 0
        monthly.append({'month':start.strftime('%b %Y'),'amount':round(amt,2)})
    top=db.session.query(Product.name,func.sum(SaleItem.quantity).label('qty'),func.sum(SaleItem.total_price).label('rev'))\
        .join(SaleItem).group_by(Product.id).order_by(func.sum(SaleItem.quantity).desc()).limit(10).all()
    cat_data=db.session.query(Category.name,func.sum(SaleItem.total_price).label('rev'))\
        .join(Product,Category.id==Product.category_id).join(SaleItem,Product.id==SaleItem.product_id).group_by(Category.id).all()
    pay_data=db.session.query(Sale.payment_method,func.count(Sale.id).label('cnt'),func.sum(Sale.total_amount).label('tot'))\
        .group_by(Sale.payment_method).all()
    total_revenue=db.session.query(func.sum(Sale.total_amount)).scalar() or 0
    total_orders=Sale.query.count()
    total_returns=db.session.query(func.sum(SaleReturn.refund_amount)).scalar() or 0
    return render_template('analytics.html',
        monthly=json.dumps(monthly),
        top_products=json.dumps([{'name':t.name,'qty':t.qty,'revenue':round(t.rev or 0,2)} for t in top]),
        cat_data=json.dumps([{'name':c.name,'revenue':round(c.rev or 0,2)} for c in cat_data]),
        pay_data=json.dumps([{'method':p.payment_method,'count':p.cnt,'total':round(p.tot or 0,2)} for p in pay_data]),
        total_revenue=total_revenue, total_orders=total_orders, avg_order=total_revenue/total_orders if total_orders else 0,
        total_returns=total_returns)

# ─── Employees ────────────────────────────────────────────────────────────────────

@app.route('/employees')
@login_required
@admin_required
def employees():
    return render_template('employees.html', employees=Employee.query.order_by(Employee.full_name).all())

@app.route('/employees/add', methods=['GET','POST'])
@login_required
@admin_required
def add_employee():
    if request.method == 'POST':
        username=request.form.get('username'); password=request.form.get('password'); user=None
        if username and password:
            if User.query.filter_by(username=username).first():
                flash('Username exists.','danger'); return render_template('employee_form.html',employee=None)
            user=User(username=username,email=request.form.get('email',f"{username}@textile.com"),
                      full_name=request.form['full_name'],role='staff')
            user.set_password(password); db.session.add(user); db.session.flush()
        db.session.add(Employee(employee_id=request.form['employee_id'],full_name=request.form['full_name'],
            email=request.form.get('email'),phone=request.form.get('phone'),
            role=request.form.get('role','Staff'),department=request.form.get('department'),
            salary=float(request.form.get('salary',0)),
            join_date=datetime.strptime(request.form['join_date'],'%Y-%m-%d').date() if request.form.get('join_date') else date.today(),
            casual_leaves=int(request.form.get('casual_leaves',12)),
            sick_leaves=int(request.form.get('sick_leaves',6)),
            earned_leaves=int(request.form.get('earned_leaves',15)),
            user_id=user.id if user else None))
        db.session.commit(); flash('Employee added!','success')
        return redirect(url_for('employees'))
    return render_template('employee_form.html',employee=None)

@app.route('/employees/edit/<int:id>', methods=['GET','POST'])
@login_required
@admin_required
def edit_employee(id):
    emp=Employee.query.get_or_404(id)
    if request.method=='POST':
        emp.full_name=request.form['full_name']; emp.email=request.form.get('email')
        emp.phone=request.form.get('phone'); emp.role=request.form.get('role','Staff')
        emp.department=request.form.get('department'); emp.salary=float(request.form.get('salary',0))
        emp.casual_leaves=int(request.form.get('casual_leaves',12))
        emp.sick_leaves=int(request.form.get('sick_leaves',6))
        emp.earned_leaves=int(request.form.get('earned_leaves',15))
        emp.is_active='is_active' in request.form
        db.session.commit(); flash('Updated!','success')
        return redirect(url_for('employees'))
    return render_template('employee_form.html',employee=emp)

# ─── Attendance ────────────────────────────────────────────────────────────────────

@app.route('/attendance')
@login_required
def attendance():
    today=date.today()
    sel_str=request.args.get('date',today.strftime('%Y-%m-%d'))
    try: sel=datetime.strptime(sel_str,'%Y-%m-%d').date()
    except: sel=today
    if current_user.role=='admin':
        emps=Employee.query.filter_by(is_active=True).all()
        recs={a.employee_id:a for a in Attendance.query.filter_by(date=sel).all()}
        return render_template('attendance_admin.html',employees=emps,records=recs,selected_date=sel,today=today,store_radius=STORE_RADIUS_M)
    else:
        emp=Employee.query.filter_by(user_id=current_user.id).first()
        if not emp: flash('No employee linked.','warning'); return redirect(url_for('dashboard'))
        today_rec=Attendance.query.filter_by(employee_id=emp.id,date=today).first()
        history=Attendance.query.filter_by(employee_id=emp.id).order_by(Attendance.date.desc()).limit(30).all()
        return render_template('attendance_staff.html',employee=emp,today_record=today_rec,
                               history=history,today=today,
                               store_lat=STORE_LAT,store_lng=STORE_LNG,store_radius=STORE_RADIUS_M)

@app.route('/attendance/mark', methods=['POST'])
@login_required
def mark_attendance():
    """Admin: bulk mark by status. Staff: handled via /attendance/punch"""
    if current_user.role == 'admin':
        sel_str = request.form.get('date', date.today().strftime('%Y-%m-%d'))
        sel = datetime.strptime(sel_str, '%Y-%m-%d').date()
        for emp in Employee.query.filter_by(is_active=True).all():
            status = request.form.get(f'status_{emp.id}', 'absent')
            existing = Attendance.query.filter_by(employee_id=emp.id, date=sel).first()
            if existing:
                existing.status = status
                existing.marked_by = current_user.id
            else:
                db.session.add(Attendance(
                    employee_id=emp.id, date=sel, status=status,
                    marked_by=current_user.id,
                    check_in=datetime.now() if status == 'present' else None
                ))
        db.session.commit()
        flash('Attendance saved!', 'success')
        return redirect(url_for('attendance', date=sel_str))
    else:
        # Staff: redirect to punch endpoint
        return redirect(url_for('attendance'))


@app.route('/attendance/punch', methods=['POST'])
@login_required
def attendance_punch():
    """
    Staff self-punch with GPS geofencing.
    Supports 4 punches per day:
      punch 1 = check_in   (session 1 start)
      punch 2 = check_out  (session 1 end)
      punch 3 = check_in2  (session 2 start)
      punch 4 = check_out2 (session 2 end)
    """
    data = request.get_json() or {}
    lat = float(data.get('lat') or 0)
    lng = float(data.get('lng') or 0)

    emp = Employee.query.filter_by(user_id=current_user.id).first()
    if not emp:
        return jsonify({'error': 'No employee profile linked to your account.'}), 400

    today = date.today()

    # Geofence check
    within = False
    distance = None
    if lat and lng:
        distance = haversine(lat, lng, STORE_LAT, STORE_LNG)
        within = distance <= STORE_RADIUS_M

    now = datetime.now()
    existing = Attendance.query.filter_by(employee_id=emp.id, date=today).first()

    if not existing:
        # First punch of the day → check_in (session 1)
        rec = Attendance(
            employee_id=emp.id, date=today, status='present',
            check_in=now, geo_in=within,
            marked_by=current_user.id, self_marked=True,
            latitude=lat or None, longitude=lng or None,
            within_geofence=within
        )
        db.session.add(rec)
        db.session.commit()
        return jsonify({
            'success': True,
            'action': 'checkin',
            'punch': 1,
            'time': now.strftime('%I:%M %p'),
            'within_geofence': within,
            'distance': round(distance, 1) if distance else None,
            'message': f'Session 1 Check-In recorded at {now.strftime("%I:%M %p")}',
            'next': 'checkout'
        })

    action = existing.next_action

    if action == 'checkout':
        existing.check_out = now
        existing.latitude = lat or existing.latitude
        existing.longitude = lng or existing.longitude
        db.session.commit()
        return jsonify({
            'success': True,
            'action': 'checkout',
            'punch': 2,
            'time': now.strftime('%I:%M %p'),
            'within_geofence': within,
            'distance': round(distance, 1) if distance else None,
            'message': f'Session 1 Check-Out recorded at {now.strftime("%I:%M %p")}',
            'next': 'checkin2'
        })

    elif action == 'checkin2':
        existing.check_in2 = now
        existing.geo_in2 = within
        existing.latitude = lat or existing.latitude
        existing.longitude = lng or existing.longitude
        existing.within_geofence = within or existing.within_geofence
        db.session.commit()
        return jsonify({
            'success': True,
            'action': 'checkin2',
            'punch': 3,
            'time': now.strftime('%I:%M %p'),
            'within_geofence': within,
            'distance': round(distance, 1) if distance else None,
            'message': f'Session 2 Check-In recorded at {now.strftime("%I:%M %p")}',
            'next': 'checkout2'
        })

    elif action == 'checkout2':
        existing.check_out2 = now
        existing.latitude = lat or existing.latitude
        existing.longitude = lng or existing.longitude
        db.session.commit()
        return jsonify({
            'success': True,
            'action': 'checkout2',
            'punch': 4,
            'time': now.strftime('%I:%M %p'),
            'within_geofence': within,
            'distance': round(distance, 1) if distance else None,
            'message': f'Session 2 Check-Out recorded at {now.strftime("%I:%M %p")}',
            'next': 'done'
        })

    else:
        return jsonify({
            'error': 'All 4 punches completed for today.',
            'done': True,
            'total_hours': existing.total_hours
        })


@app.route('/attendance/report')
@login_required
@admin_required
def attendance_report():
    month=request.args.get('month',date.today().strftime('%Y-%m'))
    try: md=datetime.strptime(month,'%Y-%m').date()
    except: md=date.today().replace(day=1)
    emps=Employee.query.filter_by(is_active=True).all()
    start=md.replace(day=1)
    end=start.replace(month=start.month%12+1) if start.month<12 else start.replace(year=start.year+1,month=1)
    records={}
    for emp in emps:
        recs=Attendance.query.filter(Attendance.employee_id==emp.id,Attendance.date>=start,Attendance.date<end).all()
        records[emp.id]={a.date:a for a in recs}
    days=[]; cur=start
    while cur<end and cur<=date.today(): days.append(cur); cur+=timedelta(days=1)
    return render_template('attendance_report.html',employees=emps,records=records,days=days,month=month,month_date=md)

# ─── Leaves ────────────────────────────────────────────────────────────────────────

@app.route('/leaves')
@login_required
def leaves():
    if current_user.role=='admin':
        pending=LeaveApplication.query.filter_by(status='pending').order_by(LeaveApplication.applied_on.desc()).all()
        all_leaves=LeaveApplication.query.order_by(LeaveApplication.applied_on.desc()).limit(50).all()
        return render_template('leaves_admin.html',pending=pending,all_leaves=all_leaves)
    else:
        emp=Employee.query.filter_by(user_id=current_user.id).first()
        if not emp: flash('No employee profile.','warning'); return redirect(url_for('dashboard'))
        my_leaves=LeaveApplication.query.filter_by(employee_id=emp.id).order_by(LeaveApplication.applied_on.desc()).all()
        return render_template('leaves_staff.html',emp=emp,my_leaves=my_leaves)

@app.route('/leaves/apply', methods=['POST'])
@login_required
def apply_leave():
    emp=Employee.query.filter_by(user_id=current_user.id).first()
    if not emp: flash('No profile.','danger'); return redirect(url_for('leaves'))
    fd=datetime.strptime(request.form['from_date'],'%Y-%m-%d').date()
    td=datetime.strptime(request.form['to_date'],'%Y-%m-%d').date()
    if td<fd: flash('End date before start date.','danger'); return redirect(url_for('leaves'))
    days=(td-fd).days+1
    if days>emp.leaves_remaining: flash(f'Only {emp.leaves_remaining} leaves remaining!','danger'); return redirect(url_for('leaves'))
    db.session.add(LeaveApplication(employee_id=emp.id,leave_type=request.form.get('leave_type','casual'),
        from_date=fd,to_date=td,days=days,reason=request.form.get('reason','')))
    db.session.commit(); flash(f'Leave applied for {days} day(s). Pending approval.','success')
    return redirect(url_for('leaves'))

@app.route('/leaves/review/<int:lid>/<action>', methods=['POST'])
@login_required
@admin_required
def review_leave(lid,action):
    la=LeaveApplication.query.get_or_404(lid)
    if action in ('approved','rejected'):
        la.status=action; la.reviewed_by=current_user.id; la.reviewed_on=datetime.utcnow()
        la.review_note=request.form.get('note','')
        if action=='approved':
            cur=la.from_date
            while cur<=la.to_date:
                ex=Attendance.query.filter_by(employee_id=la.employee_id,date=cur).first()
                if ex: ex.status='leave'
                else: db.session.add(Attendance(employee_id=la.employee_id,date=cur,status='leave',
                    marked_by=current_user.id,notes=f"Leave: {la.reason}"))
                cur+=timedelta(days=1)
        db.session.commit(); flash(f'Leave {action}.','success')
    return redirect(url_for('leaves'))

# ─── Staff Organiser ────────────────────────────────────────────────────────────────

@app.route('/organiser')
@login_required
def organiser():
    if current_user.role=='admin': flash('Organiser is for staff.','info'); return redirect(url_for('dashboard'))
    emp=Employee.query.filter_by(user_id=current_user.id).first()
    if not emp: flash('No employee profile.','warning'); return redirect(url_for('dashboard'))
    tab=request.args.get('tab','profile')
    today=date.today(); months=[]
    for i in range(5,-1,-1):
        m=today.month-i; y=today.year
        while m<=0: m+=12; y-=1
        start=date(y,m,1); em=m%12+1; ey=y+(1 if m==12 else 0); end=date(ey,em,1)
        present=Attendance.query.filter(Attendance.employee_id==emp.id,
            Attendance.date>=start,Attendance.date<end,Attendance.status=='present').count()
        leaves_days=Attendance.query.filter(Attendance.employee_id==emp.id,
            Attendance.date>=start,Attendance.date<end,Attendance.status=='leave').count()
        absent=Attendance.query.filter(Attendance.employee_id==emp.id,
            Attendance.date>=start,Attendance.date<end,Attendance.status=='absent').count()
        working_days=(end-start).days
        per_day=emp.salary/26 if emp.salary else 0
        net=per_day*present-(per_day*absent)-(per_day*present*0.12)-(per_day*present*0.0075)
        months.append({'label':start.strftime('%B %Y'),'value':start.strftime('%Y-%m'),
            'present':present,'leaves':leaves_days,'absent':absent,
            'working_days':working_days,'y':y,'m':m,'net_salary':round(max(0,net),2)})
    my_leaves=LeaveApplication.query.filter_by(employee_id=emp.id).order_by(LeaveApplication.applied_on.desc()).all()
    return render_template('organiser.html',emp=emp,tab=tab,months=months,my_leaves=my_leaves,
                           today=today,
                           store_lat=STORE_LAT,store_lng=STORE_LNG,store_radius=STORE_RADIUS_M)

@app.route('/organiser/profile/update', methods=['POST'])
@login_required
def update_profile():
    emp=Employee.query.filter_by(user_id=current_user.id).first()
    if emp:
        emp.phone=request.form.get('phone',emp.phone)
        emp.email=request.form.get('email',emp.email)
        emp.full_name=request.form.get('full_name',emp.full_name)
        current_user.full_name=emp.full_name
    new_pass=request.form.get('new_password','')
    if new_pass and len(new_pass)>=6:
        if current_user.check_password(request.form.get('current_password','')):
            current_user.set_password(new_pass); flash('Password changed!','success')
        else: flash('Wrong current password.','danger')
    db.session.commit(); flash('Profile updated!','success')
    return redirect(url_for('organiser',tab='profile'))

@app.route('/organiser/salary-slip/<int:year>/<int:month>/pdf')
@login_required
def salary_slip_pdf(year,month):
    emp=Employee.query.filter_by(user_id=current_user.id).first()
    if not emp: flash('No profile.','danger'); return redirect(url_for('organiser'))
    start=date(year,month,1); em=month%12+1; ey=year+(1 if month==12 else 0); end=date(ey,em,1)
    working_days=(end-start).days
    present_days=Attendance.query.filter(Attendance.employee_id==emp.id,Attendance.date>=start,Attendance.date<end,Attendance.status=='present').count()
    leave_days=Attendance.query.filter(Attendance.employee_id==emp.id,Attendance.date>=start,Attendance.date<end,Attendance.status=='leave').count()
    absent_days=max(0,working_days-present_days-leave_days)
    per_day=emp.salary/26; earned=per_day*present_days
    pf=earned*0.12; esi=earned*0.0075; net=max(0,earned-pf-esi)
    buffer=io.BytesIO()
    doc=SimpleDocTemplate(buffer,pagesize=A4,topMargin=0.6*inch,bottomMargin=0.6*inch,leftMargin=0.7*inch,rightMargin=0.7*inch)
    styles=getSampleStyleSheet(); story=[]
    story.append(Paragraph("🏬 TEXTILE SHOWROOM",ParagraphStyle('H',parent=styles['Title'],fontSize=20,textColor=colors.HexColor('#1a1a2e'),spaceAfter=4)))
    story.append(Paragraph(f"SALARY SLIP — {start.strftime('%B %Y').upper()}",ParagraphStyle('SS',parent=styles['Heading2'],fontSize=14,textColor=colors.HexColor('#e94560'),spaceAfter=6)))
    story.append(HRFlowable(width="100%",thickness=2,color=colors.HexColor('#e94560'))); story.append(Spacer(1,0.15*inch))
    emp_t=Table([['Employee Name',emp.full_name,'Employee ID',emp.employee_id],
                 ['Department',emp.department or '-','Designation',emp.role],
                 ['Pay Period',start.strftime('%B %Y'),'Working Days',str(working_days)]],
                colWidths=[1.8*inch,2.5*inch,1.8*inch,1.6*inch])
    emp_t.setStyle(TableStyle([('FONTNAME',(0,0),(0,-1),'Helvetica-Bold'),('FONTNAME',(2,0),(2,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6),('ROWBACKGROUNDS',(0,0),(-1,-1),[colors.white,colors.HexColor('#f8f9fa')])]))
    story.append(emp_t); story.append(Spacer(1,0.15*inch))
    story.append(Paragraph("Attendance Summary",ParagraphStyle('AH',parent=styles['Heading3'],fontSize=11,textColor=colors.HexColor('#0f3460'))))
    att_t=Table([['Present','Leave','Absent','Working Days'],[str(present_days),str(leave_days),str(absent_days),str(working_days)]],colWidths=[1.8*inch]*4)
    att_t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#0f3460')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),9),('ALIGN',(0,0),(-1,-1),'CENTER'),('TOPPADDING',(0,0),(-1,-1),6),('BOTTOMPADDING',(0,0),(-1,-1),6)]))
    story.append(att_t); story.append(Spacer(1,0.15*inch))
    story.append(Paragraph("Earnings & Deductions",ParagraphStyle('EH',parent=styles['Heading3'],fontSize=11,textColor=colors.HexColor('#0f3460'))))
    ed_t=Table([['EARNINGS','AMOUNT','DEDUCTIONS','AMOUNT'],
                ['Basic (Monthly)',f"₹{emp.salary:.2f}",'Provident Fund (12%)',f"₹{pf:.2f}"],
                ['Salary Earned',f"₹{earned:.2f}",'ESI (0.75%)',f"₹{esi:.2f}"],
                ['','',f'Absence ({absent_days} days)',f"₹{per_day*absent_days:.2f}"],
                ['GROSS EARNINGS',f"₹{earned:.2f}",'TOTAL DEDUCTIONS',f"₹{pf+esi:.2f}"]],
               colWidths=[2.5*inch,1.5*inch,2.5*inch,1.5*inch])
    ed_t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#1a1a2e')),('TEXTCOLOR',(0,0),(-1,0),colors.white),('FONTNAME',(0,0),(-1,0),'Helvetica-Bold'),('FONTNAME',(0,-1),(-1,-1),'Helvetica-Bold'),('BACKGROUND',(0,-1),(-1,-1),colors.HexColor('#f0f2f8')),('FONTSIZE',(0,0),(-1,-1),9),('GRID',(0,0),(-1,-1),0.5,colors.HexColor('#dee2e6')),('TOPPADDING',(0,0),(-1,-1),5),('BOTTOMPADDING',(0,0),(-1,-1),5)]))
    story.append(ed_t); story.append(Spacer(1,0.15*inch))
    net_t=Table([[f"NET TAKE-HOME PAY",f"₹{net:.2f}"]],colWidths=[5.5*inch,2.2*inch])
    net_t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.HexColor('#e94560')),('TEXTCOLOR',(0,0),(-1,-1),colors.white),('FONTNAME',(0,0),(-1,-1),'Helvetica-Bold'),('FONTSIZE',(0,0),(-1,-1),14),('ALIGN',(0,0),(-1,-1),'CENTER'),('TOPPADDING',(0,0),(-1,-1),12),('BOTTOMPADDING',(0,0),(-1,-1),12)]))
    story.append(net_t); story.append(Spacer(1,0.3*inch))
    story.append(Paragraph("This is a computer-generated salary slip and does not require a signature.",ParagraphStyle('f',parent=styles['Normal'],fontSize=8,textColor=colors.HexColor('#aaa'),alignment=1)))
    doc.build(story); buffer.seek(0)
    return send_file(buffer,as_attachment=True,download_name=f"salary_slip_{emp.employee_id}_{year}_{month:02d}.pdf",mimetype='application/pdf')

# ─── Categories ────────────────────────────────────────────────────────────────────

@app.route('/categories')
@login_required
@admin_required
def categories():
    return render_template('categories.html',categories=Category.query.all())

@app.route('/categories/add', methods=['POST'])
@login_required
@admin_required
def add_category():
    name=request.form.get('name','').strip()
    if name and not Category.query.filter_by(name=name).first():
        db.session.add(Category(name=name,description=request.form.get('description',''))); db.session.commit()
        flash(f'Category "{name}" added.','success')
    else: flash('Already exists or empty.','warning')
    return redirect(url_for('categories'))

@app.route('/categories/delete/<int:id>', methods=['POST'])
@login_required
@admin_required
def delete_category(id):
    cat=Category.query.get_or_404(id)
    if cat.products: flash('Has products.','danger')
    else: db.session.delete(cat); db.session.commit(); flash('Deleted.','success')
    return redirect(url_for('categories'))

# ─── Seed ────────────────────────────────────────────────────────────────────────

def seed_data():
    if User.query.count()>0: return
    admin=User(username='admin',email='admin@textile.com',full_name='Store Admin',role='admin')
    admin.set_password('admin123')
    s1=User(username='staff1',email='rahul@textile.com',full_name='Rahul Sharma',role='staff')
    s1.set_password('staff123')
    s2=User(username='staff2',email='priya@textile.com',full_name='Priya Nair',role='staff')
    s2.set_password('staff123')
    db.session.add_all([admin,s1,s2]); db.session.flush()
    cat_names=['Men\'s Wear','Women\'s Wear','Kids Wear','Ethnic Wear','Sportswear','Accessories','Innerwear','Winter Wear']
    cats={}
    for c in cat_names:
        obj=Category(name=c); db.session.add(obj); cats[c]=obj
    db.session.flush()
    pd=[('Men\'s Cotton Shirt','Men\'s Wear','M,L,XL','White',899,400,45,'MCS001'),
        ('Men\'s Formal Trousers','Men\'s Wear','32,34,36','Black',1299,600,30,'MFT002'),
        ('Men\'s Denim Jeans','Men\'s Wear','30,32,34','Blue',1599,750,25,'MDJ003'),
        ('Women\'s Kurti','Women\'s Wear','S,M,L','Red',799,350,60,'WKU004'),
        ('Women\'s Saree','Ethnic Wear','Free Size','Multi',2499,1200,20,'WSR005'),
        ('Kids T-Shirt','Kids Wear','4Y,6Y,8Y','Yellow',399,180,80,'KTS006'),
        ('Sports Shorts','Sportswear','S,M,L,XL','Black',599,250,40,'SS007'),
        ('Men\'s Blazer','Men\'s Wear','M,L,XL','Navy',3499,1800,8,'MB008'),
        ('Women\'s Leggings','Women\'s Wear','S,M,L','Black',499,200,55,'WL009'),
        ('Boys Shirt','Kids Wear','6Y,8Y,10Y','Blue',449,200,35,'BS010'),
        ('Ethnic Kurta','Ethnic Wear','M,L,XL','Cream',1199,550,28,'EK011'),
        ('Sports Jacket','Sportswear','S,M,L','Grey',1899,900,15,'SJ012'),
        ('Winter Hoodie','Winter Wear','M,L,XL','Green',1499,700,20,'WH013'),
        ('Scarf','Accessories','Free','Multi',299,120,100,'SC014'),
        ('Innerwear Pack','Innerwear','M,L,XL','White',349,150,70,'MI015')]
    prods=[]
    for name,cat,sz,col,price,cost,qty,bc in pd:
        p=Product(name=name,category_id=cats[cat].id,size=sz,color=col,price=price,cost_price=cost,quantity=qty,barcode=bc,gst_rate=5.0,low_stock_threshold=10)
        db.session.add(p); prods.append(p)
    db.session.flush()
    e1=Employee(employee_id='EMP001',full_name='Rahul Sharma',email='rahul@textile.com',phone='9876543210',role='Staff',department='Sales',salary=22000,join_date=date(2023,3,15),user_id=s1.id,casual_leaves=12,sick_leaves=6,earned_leaves=15)
    e2=Employee(employee_id='EMP002',full_name='Priya Nair',email='priya@textile.com',phone='9876543211',role='Staff',department='Billing',salary=20000,join_date=date(2023,6,1),user_id=s2.id,casual_leaves=12,sick_leaves=6,earned_leaves=15)
    e3=Employee(employee_id='EMP003',full_name='Kiran Kumar',email='kiran@textile.com',phone='9876543212',role='Manager',department='Operations',salary=35000,join_date=date(2022,1,10),casual_leaves=15,sick_leaves=8,earned_leaves=18)
    db.session.add_all([e1,e2,e3]); db.session.flush()
    import random
    for i in range(30):
        day=date.today()-timedelta(days=i)
        for _ in range(random.randint(3,12)):
            inv=f"INV{day.strftime('%Y%m%d')}{random.randint(1000,9999)}"
            if Sale.query.filter_by(invoice_number=inv).first(): continue
            sp=random.sample(prods,random.randint(1,3)); sub=0; gst_t=0
            sale=Sale(invoice_number=inv,customer_name=random.choice(['Walk-in','Amit Patel','Sunita Rao','Vikram Singh']),
                customer_phone=f"98{random.randint(10000000,99999999)}",payment_method=random.choice(['cash','card','upi','upi']),
                created_by=random.choice([s1.id,s2.id]),
                created_at=datetime(day.year,day.month,day.day,random.randint(10,20),random.randint(0,59)))
            db.session.add(sale); db.session.flush()
            for p in sp:
                qty=random.randint(1,3); gst=p.price*qty*p.gst_rate/100; tot=p.price*qty+gst
                sub+=p.price*qty; gst_t+=gst
                db.session.add(SaleItem(sale_id=sale.id,product_id=p.id,quantity=qty,unit_price=p.price,gst_rate=p.gst_rate,total_price=round(tot,2)))
            sale.subtotal=round(sub,2); sale.gst_amount=round(gst_t,2); sale.total_amount=round(sub+gst_t,2)
    for emp in [e1,e2,e3]:
        for i in range(14):
            d=date.today()-timedelta(days=i); status='present' if i<12 else 'absent'
            if not Attendance.query.filter_by(employee_id=emp.id,date=d).first():
                db.session.add(Attendance(employee_id=emp.id,date=d,status=status,marked_by=admin.id,
                    check_in=datetime(d.year,d.month,d.day,9,30) if status=='present' else None,
                    check_out=datetime(d.year,d.month,d.day,13,0) if status=='present' else None,
                    check_in2=datetime(d.year,d.month,d.day,14,0) if status=='present' else None,
                    check_out2=datetime(d.year,d.month,d.day,18,0) if status=='present' else None,
                    geo_in=True, geo_in2=True,
                    within_geofence=True,self_marked=True))
    la1=LeaveApplication(employee_id=e1.id,leave_type='casual',from_date=date.today()+timedelta(days=3),to_date=date.today()+timedelta(days=4),days=2,reason='Family function',status='pending')
    la2=LeaveApplication(employee_id=e2.id,leave_type='sick',from_date=date.today()-timedelta(days=5),to_date=date.today()-timedelta(days=5),days=1,reason='Fever',status='approved',reviewed_by=admin.id,reviewed_on=datetime.utcnow())
    db.session.add_all([la1,la2])
    db.session.commit(); print("✅ Demo data seeded!")

# Serve uploaded files from /tmp on Render
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    from flask import send_from_directory
    upload_dir = '/tmp/uploads' if os.environ.get('RENDER') else os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
    return send_from_directory(upload_dir, filename)

with app.app_context():
    db.create_all(); seed_data()

if __name__=='__main__':
    import os
    app.run(debug=os.environ.get('FLASK_DEBUG','0')=='1', port=int(os.environ.get('PORT',5000)))
