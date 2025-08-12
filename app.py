from flask import Flask, render_template, request, redirect, url_for, jsonify, flash, session, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import joinedload
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
import os
import uuid
import json
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from email.utils import formataddr
import logging

# 配置日志 - 只显示错误级别
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('flask').setLevel(logging.ERROR)

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config['SECRET_KEY'] = 'unihome_secret_key'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.jinja_env.auto_reload = True
# 确保使用绝对路径，避免数据库文件位置混乱
import os
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{os.path.join(basedir, "unihome.db")}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'mp4', 'webm'}

# 关闭Flask默认日志
app.logger.setLevel(logging.ERROR)

db = SQLAlchemy(app)

# 数据模型
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    properties = db.relationship('Property', backref='owner', lazy=True)
    # 邮箱验证相关字段
    email_verified = db.Column(db.Boolean, default=False)  # 邮箱是否已验证
    email_code = db.Column(db.String(10))                 # 邮箱验证码
    email_code_sent_at = db.Column(db.DateTime)           # 验证码发送时间
    # 管理员联系信息字段
    phone = db.Column(db.String(20))                      # 电话号码
    wechat = db.Column(db.String(50))                     # 微信号
    avatar = db.Column(db.String(200))                    # 头像路径
    display_name = db.Column(db.String(100))              # 显示名称
    address = db.Column(db.String(200))                   # 地理位置/地址
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.username}>'

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    location = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(50), nullable=False)  # 'Canada' or 'China'
    address = db.Column(db.String(200))
    price = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='$')  # '$' or '¥'
    bedrooms = db.Column(db.Integer)
    bathrooms = db.Column(db.Integer)
    area = db.Column(db.Float)  # 面积，单位m²
    property_type = db.Column(db.String(50))  # 房屋类型：整套公寓、合租房间、学生宿舍
    status = db.Column(db.String(20), default='pending')  # pending, active, inactive
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    images = db.relationship('PropertyImage', backref='property', lazy=True, cascade="all, delete-orphan")
    videos = db.relationship('PropertyVideo', backref='property', lazy=True, cascade="all, delete-orphan")
    rent = db.Column(db.Float)
    deposit = db.Column(db.Float)
    utility = db.Column(db.String(50))
    min_term = db.Column(db.String(50))
    extra_info = db.Column(db.Text)  # 存储自定义JSON内容
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'location': self.location,
            'country': self.country,
            'address': self.address,
            'price': self.price,
            'currency': self.currency,
            'bedrooms': self.bedrooms,
            'bathrooms': self.bathrooms,
            'area': self.area,
            'property_type': self.property_type,
            'status': self.status,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'images': [img.path for img in self.images],
            'videos': [vid.path for vid in self.videos],
            'rent': self.rent,
            'deposit': self.deposit,
            'utility': self.utility,
            'min_term': self.min_term,
            'minTerm': self.min_term,
            'desc': [],
            'facilities': [],
            'traffic': [],
            'surroundings': [],
            'landlord': {},
        }
    
    def __repr__(self):
        return f'<Property {self.name}>'

class PropertyImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(200), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    
    def __repr__(self):
        return f'<PropertyImage {self.path}>'

class PropertyVideo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    path = db.Column(db.String(200), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)

    def __repr__(self):
        return f'<PropertyVideo {self.path}>'

class Location(db.Model):
    """位置管理模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # 位置名称，如"多伦多"
    country = db.Column(db.String(50), nullable=False)  # 国家，如"Canada"或"China"
    display_name = db.Column(db.String(150))  # 显示名称，如"多伦多 (加拿大)"
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    sort_order = db.Column(db.Integer, default=0)  # 排序顺序
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 注意：这里不直接定义relationship，因为Property表使用location字段存储位置名称
    # 而不是外键。我们将在查询时手动关联

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'country': self.country,
            'display_name': self.display_name or self.name,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def __repr__(self):
        return f'<Location {self.name} ({self.country})>'

class PropertyType(db.Model):
    """房屋类型管理模型"""
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)  # 类型名称，如"整套公寓"
    description = db.Column(db.String(200))  # 类型描述
    is_active = db.Column(db.Boolean, default=True)  # 是否启用
    sort_order = db.Column(db.Integer, default=0)  # 排序顺序
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # 注意：这里不直接定义relationship，因为Property表使用property_type字段存储类型名称
    # 而不是外键。我们将在查询时手动关联

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'is_active': self.is_active,
            'sort_order': self.sort_order,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

# 预约看房模型
class Appointment(db.Model):
    """预约看房模型"""
    __tablename__ = 'appointment'
    
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=True)
    preferred_date = db.Column(db.String(50), nullable=False)
    preferred_time = db.Column(db.String(50), nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending, confirmed, cancelled, completed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联到房源
    property = db.relationship('Property', backref='appointments', lazy=True)
    
    def to_dict(self):
        """转换为字典格式"""
        return {
            'id': self.id,
            'property_id': self.property_id,
            'property_name': self.property.name if self.property else None,
            'property_location': self.property.location if self.property else None,
            'name': self.name,
            'phone': self.phone,
            'email': self.email,
            'preferred_date': self.preferred_date,
            'preferred_time': self.preferred_time,
            'message': self.message,
            'status': self.status,
            'status_display': {
                'pending': '待确认',
                'confirmed': '已确认',
                'cancelled': '已取消',
                'completed': '已完成'
            }.get(self.status, self.status),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<Appointment {self.name} - {self.property_id}>'

# 收藏模型
class Favorite(db.Model):
    """用户收藏房源模型"""
    __tablename__ = 'favorite'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 建立关系
    user = db.relationship('User', backref=db.backref('favorites', lazy=True))
    property = db.relationship('Property', backref=db.backref('favorited_by', lazy=True))

    # 确保同一用户不能重复收藏同一房源
    __table_args__ = (db.UniqueConstraint('user_id', 'property_id', name='unique_user_property_favorite'),)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'property_id': self.property_id,
            'property': self.property.to_dict() if self.property else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }

    def __repr__(self):
        return f'<Favorite User:{self.user_id} Property:{self.property_id}>'

# 辅助函数
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_file(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
        file.save(file_path)
        # 返回相对路径，与UPLOAD_FOLDER保持一致
        return os.path.join(app.config['UPLOAD_FOLDER'], unique_filename).replace('\\', '/')
    return None

# 路由
@app.route('/')
def index():
    properties = Property.query.filter_by(status='active').order_by(Property.created_at.desc()).limit(6).all()
    return render_template('index.html', properties=properties)

@app.route('/favorites')
def favorites():
    """收藏页面"""
    return render_template('favorites.html')



@app.route('/search')
def search():
    location = request.args.get('location', '')
    price_range = request.args.get('price', '')
    property_type = request.args.get('type', '')
    sort_by = request.args.get('sort', 'recommended')
    
    query = Property.query.filter_by(status='active')
    
    if location and location != '全部':
        query = query.filter_by(location=location)
    
    if property_type and property_type != '全部':
        query = query.filter_by(property_type=property_type)
    
    if price_range and price_range != '全部':
        if price_range == '¥1000-3000 / $200-500':
            query = query.filter((Property.currency == '¥') & (Property.price.between(1000, 3000)) | 
                               (Property.currency == '$') & (Property.price.between(200, 500)))
        elif price_range == '¥3000-5000 / $500-800':
            query = query.filter((Property.currency == '¥') & (Property.price.between(3000, 5000)) | 
                               (Property.currency == '$') & (Property.price.between(500, 800)))
        elif price_range == '¥5000+ / $800+':
            query = query.filter((Property.currency == '¥') & (Property.price > 5000) | 
                               (Property.currency == '$') & (Property.price > 800))
    
    if sort_by == '价格 ↑':
        query = query.order_by(Property.price.asc())
    elif sort_by == '价格 ↓':
        query = query.order_by(Property.price.desc())
    elif sort_by == '最新':
        query = query.order_by(Property.created_at.desc())
    
    properties = query.all()
    return render_template('search.html', properties=properties, filters={
        'location': location,
        'price': price_range,
        'type': property_type,
        'sort': sort_by
    })

@app.route('/property/<int:id>')
def property_detail(id):
    # 直接查询房源并确保owner关系被加载
    property = Property.query.get_or_404(id)
    # 显式访问owner属性以触发加载
    if property.owner:
        # 确保owner的所有属性都被加载
        _ = property.owner.phone
        _ = property.owner.wechat
        _ = property.owner.email
        _ = property.owner.display_name
        _ = property.owner.avatar

    similar_properties = Property.query.filter(
        Property.location == property.location,
        Property.id != property.id,
        Property.status == 'active'
    ).limit(3).all()
    return render_template('detail.html', property=property, similar_properties=similar_properties)

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password) and user.is_admin:
            session['user_id'] = user.id
            return redirect(url_for('admin_dashboard'))
        else:
            flash('Invalid username or password', 'error')

    # 直接返回HTML，绕过模板缓存
    return '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>租房管理平台 - 管理员登录</title>

    <!-- 本地CSS资源 -->
    <link href="/static/css/tailwind.min.css" rel="stylesheet">
    <link rel="stylesheet" href="/static/css/all.min.css">

    <style>
    /* 内联样式确保基本样式正确显示 */
    * {
        box-sizing: border-box;
    }

    body {
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
        background-color: #f3f4f6;
        min-height: 100vh;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    .login-container {
        width: 100%;
        max-width: 28rem;
        padding: 2rem;
        background: white;
        border-radius: 0.5rem;
        box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25);
        margin: 1rem;
    }

    .login-header {
        text-align: center;
        margin-bottom: 2rem;
    }

    .login-icon {
        width: 4rem;
        height: 4rem;
        background-color: #4f46e5;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 1.5rem;
        color: white;
        font-size: 1.5rem;
    }

    .login-title {
        font-size: 1.875rem;
        font-weight: 800;
        color: #111827;
        margin: 0 0 0.5rem;
    }

    .login-subtitle {
        color: #6b7280;
        font-size: 0.875rem;
        margin: 0;
    }

    .form-group {
        margin-bottom: 1rem;
        position: relative;
    }

    .form-icon {
        position: absolute;
        left: 0.75rem;
        top: 50%;
        transform: translateY(-50%);
        color: #9ca3af;
        pointer-events: none;
    }

    .form-input {
        width: 100%;
        padding: 0.75rem 0.75rem 0.75rem 2.5rem;
        border: 1px solid #d1d5db;
        border-radius: 0.375rem;
        font-size: 1rem;
        transition: all 0.2s;
    }

    .form-input:focus {
        outline: none;
        border-color: #4f46e5;
        box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
    }

    .login-button {
        width: 100%;
        padding: 0.75rem 1rem;
        background-color: #4f46e5;
        color: white;
        border: none;
        border-radius: 0.375rem;
        font-size: 0.875rem;
        font-weight: 500;
        cursor: pointer;
        transition: background-color 0.2s;
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 0.5rem;
    }

    .login-button:hover {
        background-color: #4338ca;
    }

    .back-link {
        text-align: center;
        margin-top: 1.5rem;
    }

    .back-link a {
        color: #6b7280;
        text-decoration: none;
        font-size: 0.875rem;
        transition: color 0.2s;
    }

    .back-link a:hover {
        color: #4f46e5;
    }

    .footer {
        position: fixed;
        bottom: 1rem;
        left: 50%;
        transform: translateX(-50%);
        color: #6b7280;
        font-size: 0.875rem;
        text-align: center;
    }

    /* Font Awesome 图标备用样式 */
    .fa-user-shield::before { content: "🛡️"; }
    .fa-user::before { content: "👤"; }
    .fa-lock::before { content: "🔒"; }
    .fa-sign-in-alt::before { content: "➡️"; }
    .fa-arrow-left::before { content: "←"; }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="login-header">
            <div class="login-icon">
                <i class="fas fa-user-shield"></i>
            </div>
            <h1 class="login-title">管理员登录</h1>
            <p class="login-subtitle">使用您的管理员账号登录系统</p>
        </div>
        <form method="post" action="/admin/login">
            <div class="form-group">
                <div class="form-icon">
                    <i class="fas fa-user"></i>
                </div>
                <input name="username" type="text" required class="form-input" placeholder="用户名">
            </div>

            <div class="form-group">
                <div class="form-icon">
                    <i class="fas fa-lock"></i>
                </div>
                <input name="password" type="password" required class="form-input" placeholder="密码">
            </div>

            <button type="submit" class="login-button">
                <i class="fas fa-sign-in-alt"></i>
                <span>登录</span>
            </button>
        </form>
        <div class="back-link">
            <a href="/">
                <i class="fas fa-arrow-left"></i> 返回前台页面
            </a>
        </div>
    </div>

    <div class="footer">
        <p>© 2025 租房管理平台. 保留所有权利。</p>
    </div>

</body>
</html>'''



@app.route('/admin/logout')
def admin_logout():
    session.pop('user_id', None)
    return redirect(url_for('admin_login'))

@app.route('/admin/profile', methods=['GET', 'POST'])
def admin_profile():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))

    if request.method == 'POST':
        try:
            # 更新用户信息
            user.display_name = request.form.get('display_name', '').strip()
            user.phone = request.form.get('phone', '').strip()
            user.wechat = request.form.get('wechat', '').strip()
            user.address = request.form.get('address', '').strip()

            # 处理邮箱更新
            new_email = request.form.get('email', '').strip()
            if new_email and new_email != user.email:
                # 检查邮箱唯一性
                existing_user = User.query.filter(User.email == new_email, User.id != user.id).first()
                if existing_user:
                    return jsonify({'success': False, 'message': '该邮箱已被其他用户使用'})

                # 验证邮箱格式
                import re
                email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
                if not re.match(email_pattern, new_email):
                    return jsonify({'success': False, 'message': '邮箱格式不正确'})

                user.email = new_email

            # 处理头像上传
            if 'avatar' in request.files:
                avatar_file = request.files['avatar']
                if avatar_file and avatar_file.filename:
                    # 检查文件类型
                    if allowed_file(avatar_file.filename):
                        # 删除旧头像文件（如果存在且不是默认头像）
                        if user.avatar and user.avatar != 'static/images/icon_lg.png':
                            try:
                                if os.path.exists(user.avatar):
                                    os.remove(user.avatar)
                            except:
                                pass

                        # 保存新头像
                        avatar_path = save_file(avatar_file)
                        if avatar_path:
                            user.avatar = avatar_path

            db.session.commit()
            return jsonify({'success': True, 'message': '资料更新成功'})

        except Exception as e:
            db.session.rollback()
            return jsonify({'success': False, 'message': str(e)})

    return render_template('admin/profile.html', user=user)

# 位置管理路由
@app.route('/admin/locations')
def admin_locations():
    """位置管理页面"""
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))

    return render_template('admin/locations.html', user=user)

@app.route('/admin/locations', methods=['POST'])
def admin_locations_create():
    """创建位置"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    try:
        data = request.get_json()

        # 检查位置名称是否已存在
        existing = Location.query.filter_by(name=data['name']).first()
        if existing:
            return jsonify({'success': False, 'message': '位置名称已存在'})

        # 创建新位置
        location = Location(
            name=data['name'],
            country=data['country'],
            display_name=data.get('display_name') or f"{data['name']} ({data['country']})",
            sort_order=data.get('sort_order', 0),
            is_active=data.get('is_active', True)
        )

        db.session.add(location)
        db.session.commit()

        return jsonify({'success': True, 'message': '位置创建成功', 'data': location.to_dict()})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/locations/<int:id>', methods=['PUT'])
def admin_locations_update(id):
    """更新位置"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    try:
        location = Location.query.get_or_404(id)
        data = request.get_json()

        # 检查名称冲突（排除自己）
        if 'name' in data:
            existing = Location.query.filter(Location.name == data['name'], Location.id != id).first()
            if existing:
                return jsonify({'success': False, 'message': '位置名称已存在'})
            location.name = data['name']

        # 更新其他字段
        if 'country' in data:
            location.country = data['country']
        if 'display_name' in data:
            location.display_name = data['display_name']
        if 'sort_order' in data:
            location.sort_order = data['sort_order']
        if 'is_active' in data:
            location.is_active = data['is_active']

        location.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'message': '位置更新成功', 'data': location.to_dict()})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/locations/<int:id>', methods=['DELETE'])
def admin_locations_delete(id):
    """删除位置"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    try:
        location = Location.query.get_or_404(id)

        # 检查是否有房源使用此位置
        property_count = Property.query.filter_by(location=location.name).count()
        if property_count > 0:
            return jsonify({'success': False, 'message': f'无法删除，有 {property_count} 个房源正在使用此位置'})

        db.session.delete(location)
        db.session.commit()

        return jsonify({'success': True, 'message': '位置删除成功'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

# 房屋类型管理路由
@app.route('/admin/property_types')
def admin_property_types():
    """房屋类型管理页面"""
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))

    return render_template('admin/property_types.html', user=user)

# 预约管理路由
@app.route('/admin/appointments')
def admin_appointments():
    """预约管理页面"""
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))

    return render_template('admin/appointments.html', user=user)

@app.route('/admin/customer_favorites')
def admin_customer_favorites():
    """客户收藏管理页面"""
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))

    return render_template('admin/customer_favorites.html', user=user)

@app.route('/admin/property_types', methods=['POST'])
def admin_property_types_create():
    """创建房屋类型"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    try:
        data = request.get_json()

        # 检查类型名称是否已存在
        existing = PropertyType.query.filter_by(name=data['name']).first()
        if existing:
            return jsonify({'success': False, 'message': '房屋类型名称已存在'})

        # 创建新房屋类型
        property_type = PropertyType(
            name=data['name'],
            description=data.get('description', ''),
            sort_order=data.get('sort_order', 0),
            is_active=data.get('is_active', True)
        )

        db.session.add(property_type)
        db.session.commit()

        return jsonify({'success': True, 'message': '房屋类型创建成功', 'data': property_type.to_dict()})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/property_types/<int:id>', methods=['PUT'])
def admin_property_types_update(id):
    """更新房屋类型"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    try:
        property_type = PropertyType.query.get_or_404(id)
        data = request.get_json()

        # 检查名称冲突（排除自己）
        if 'name' in data:
            existing = PropertyType.query.filter(PropertyType.name == data['name'], PropertyType.id != id).first()
            if existing:
                return jsonify({'success': False, 'message': '房屋类型名称已存在'})
            property_type.name = data['name']

        # 更新其他字段
        if 'description' in data:
            property_type.description = data['description']
        if 'sort_order' in data:
            property_type.sort_order = data['sort_order']
        if 'is_active' in data:
            property_type.is_active = data['is_active']

        property_type.updated_at = datetime.utcnow()
        db.session.commit()

        return jsonify({'success': True, 'message': '房屋类型更新成功', 'data': property_type.to_dict()})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/property_types/<int:id>', methods=['DELETE'])
def admin_property_types_delete(id):
    """删除房屋类型"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': '未登录'}), 401

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return jsonify({'success': False, 'message': '权限不足'}), 403

    try:
        property_type = PropertyType.query.get_or_404(id)

        # 检查是否有房源使用此类型
        property_count = Property.query.filter_by(property_type=property_type.name).count()
        if property_count > 0:
            return jsonify({'success': False, 'message': f'无法删除，有 {property_count} 个房源正在使用此类型'})

        db.session.delete(property_type)
        db.session.commit()

        return jsonify({'success': True, 'message': '房屋类型删除成功'})

    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin')
def admin_index():
    """管理后台首页重定向"""
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))

    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))

    # 基础统计数据
    properties_count = Property.query.count()
    users_count = User.query.count()

    # 房源状态统计
    active_properties = Property.query.filter_by(status='active').count()
    pending_properties = Property.query.filter_by(status='pending').count()
    inactive_properties = Property.query.filter_by(status='inactive').count()

    # 最近房源（用于表格显示）
    recent_properties = Property.query.order_by(Property.created_at.desc()).limit(10).all()

    # 计算订单和消息数据
    orders_count = active_properties + pending_properties
    messages_count = pending_properties

    # 计算总页数（用于分页显示）
    total_pages = (properties_count + 9) // 10  # 每页10条，向上取整

    return render_template('admin/dashboard.html',
                         user=user,
                         properties_count=properties_count,
                         users_count=users_count,
                         active_properties=active_properties,
                         pending_properties=pending_properties,
                         inactive_properties=inactive_properties,
                         recent_properties=recent_properties,
                         orders_count=orders_count,
                         messages_count=messages_count,
                         total_pages=total_pages)

@app.route('/admin/properties')
def admin_properties():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))
    
    properties = Property.query.order_by(Property.created_at.desc()).all()
    return render_template('admin/properties.html', user=user, properties=properties)

@app.route('/admin/property/add', methods=['GET', 'POST'])
def admin_property_add():
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))
    if request.method == 'POST':
        new_property = Property(
            name=request.form.get('name'),
            description=request.form.get('description'),
            location=request.form.get('location'),
            country=request.form.get('country'),
            address=request.form.get('address'),
            price=float(request.form.get('price')),
            currency=request.form.get('currency'),
            bedrooms=int(request.form.get('bedrooms')) if request.form.get('bedrooms') else None,
            bathrooms=int(request.form.get('bathrooms')) if request.form.get('bathrooms') else None,
            area=float(request.form.get('area')) if request.form.get('area') else None,
            property_type=request.form.get('property_type'),
            status=request.form.get('status', 'pending'),
            user_id=user.id,
            # 添加缺失的字段
            rent=float(request.form.get('price')),  # 租金使用价格字段的值
            deposit=float(request.form.get('deposit')) if request.form.get('deposit') else None,
            utility=request.form.get('utility'),
            min_term=request.form.get('min_term')
        )
        # 解析结构化JSON字段并存入 extra_info
        extra = {}

        # 处理设施复选框数据
        facilities_list = []
        selected_facilities = request.form.getlist('facilities')

        # 设施映射表
        facility_mapping = {
            'wifi': {'icon': 'fa-wifi', 'label': '免费WiFi'},
            'tv': {'icon': 'fa-tv', 'label': '电视'},
            'parking': {'icon': 'fa-parking', 'label': '停车位'},
            'air_conditioning': {'icon': 'fa-snowflake', 'label': '空调'},
            'heating': {'icon': 'fa-fire', 'label': '暖气'},
            'kitchen': {'icon': 'fa-utensils', 'label': '厨房'},
            'refrigerator': {'icon': 'fa-cube', 'label': '冰箱'},
            'microwave': {'icon': 'fa-microchip', 'label': '微波炉'},
            'washing_machine': {'icon': 'fa-tshirt', 'label': '洗衣机'},
            'dishwasher': {'icon': 'fa-sink', 'label': '洗碗机'},
            'gym': {'icon': 'fa-dumbbell', 'label': '健身房'},
            'pool': {'icon': 'fa-swimming-pool', 'label': '游泳池'},
            'elevator': {'icon': 'fa-elevator', 'label': '电梯'},
            'security': {'icon': 'fa-shield-alt', 'label': '24小时安保'},
            'pets_allowed': {'icon': 'fa-paw', 'label': '允许宠物'}
        }

        # 添加选中的设施
        for facility in selected_facilities:
            if facility in facility_mapping:
                facilities_list.append(facility_mapping[facility])

        # 处理自定义设施
        custom_facilities = request.form.get('custom_facilities', '').strip()
        if custom_facilities:
            for custom in custom_facilities.split(','):
                custom = custom.strip()
                if custom:
                    facilities_list.append({'icon': 'fa-check', 'label': custom})

        if facilities_list:
            extra['facilities'] = facilities_list

        # 处理交通信息复选框数据
        traffic_list = []
        selected_traffic = request.form.getlist('traffic')

        # 交通映射表
        traffic_mapping = {
            'bus': {'icon': 'fa-bus', 'label': '附近公交站'},
            'subway': {'icon': 'fa-subway', 'label': '地铁站'},
            'taxi': {'icon': 'fa-taxi', 'label': '出租车站'},
            'bike': {'icon': 'fa-bicycle', 'label': '共享单车'},
            'airport': {'icon': 'fa-plane', 'label': '机场巴士'}
        }

        # 添加选中的交通信息
        for traffic in selected_traffic:
            if traffic in traffic_mapping:
                traffic_list.append(traffic_mapping[traffic])

        # 处理自定义交通信息
        custom_traffic = request.form.get('custom_traffic', '').strip()
        if custom_traffic:
            for custom in custom_traffic.split(','):
                custom = custom.strip()
                if custom:
                    traffic_list.append({'icon': 'fa-route', 'label': custom})

        if traffic_list:
            extra['traffic'] = traffic_list

        # 处理周边环境复选框数据
        surroundings_list = []
        selected_surroundings = request.form.getlist('surroundings')

        # 周边环境映射表
        surroundings_mapping = {
            'supermarket': {'icon': 'fa-shopping-basket', 'label': '附近超市'},
            'mall': {'icon': 'fa-shopping-bag', 'label': '购物中心'},
            'restaurant': {'icon': 'fa-utensils', 'label': '餐厅'},
            'school': {'icon': 'fa-school', 'label': '学校'},
            'hospital': {'icon': 'fa-hospital', 'label': '医院'},
            'library': {'icon': 'fa-book', 'label': '图书馆'},
            'park': {'icon': 'fa-tree', 'label': '公园'},
            'gym': {'icon': 'fa-dumbbell', 'label': '健身房'},
            'cinema': {'icon': 'fa-film', 'label': '电影院'}
        }

        # 添加选中的周边环境
        for surrounding in selected_surroundings:
            if surrounding in surroundings_mapping:
                surroundings_list.append(surroundings_mapping[surrounding])

        # 处理自定义周边环境
        custom_surroundings = request.form.get('custom_surroundings', '').strip()
        if custom_surroundings:
            for custom in custom_surroundings.split(','):
                custom = custom.strip()
                if custom:
                    surroundings_list.append({'icon': 'fa-map-marker-alt', 'label': custom})

        if surroundings_list:
            extra['surroundings'] = surroundings_list

        # 处理其他JSON字段
        for k in ['desc']:
            val = request.form.get(k)
            if val:
                try:
                    extra[k] = json.loads(val)
                except Exception:
                    pass
        for k in ['map','video']:
            val = request.form.get(k)
            if val:
                extra[k] = val
        if extra:
            new_property.extra_info = json.dumps(extra, ensure_ascii=False)
        db.session.add(new_property)
        db.session.commit()
        # 处理图片上传
        images_uploaded = 0
        for image in request.files.getlist('images'):
            if image.filename:  # 确保文件不为空
                file_path = save_file(image)
                if file_path:
                    property_image = PropertyImage(path=file_path, property_id=new_property.id)
                    db.session.add(property_image)
                    images_uploaded += 1

        # 处理视频上传
        videos_uploaded = 0
        for video in request.files.getlist('videos'):
            if video.filename:  # 确保文件不为空
                file_path = save_file(video)
                if file_path:
                    property_video = PropertyVideo(path=file_path, property_id=new_property.id)
                    db.session.add(property_video)
                    videos_uploaded += 1

        db.session.commit()

        # 提供详细的成功信息
        success_msg = f'房源添加成功！'
        if images_uploaded > 0:
            success_msg += f' 上传了 {images_uploaded} 张图片。'
        if videos_uploaded > 0:
            success_msg += f' 上传了 {videos_uploaded} 个视频。'

        flash(success_msg, 'success')
        return redirect(url_for('admin_properties'))
    return render_template('admin/property_form.html', user=user, property=None)

@app.route('/admin/property/edit/<int:id>', methods=['GET', 'POST'])
def admin_property_edit(id):
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))
    property = Property.query.get_or_404(id)
    if request.method == 'POST':
        property.name = request.form.get('name')
        property.description = request.form.get('description')
        property.location = request.form.get('location')
        property.country = request.form.get('country')
        property.address = request.form.get('address')
        property.price = float(request.form.get('price'))
        property.currency = request.form.get('currency')
        property.bedrooms = int(request.form.get('bedrooms')) if request.form.get('bedrooms') else None
        property.bathrooms = int(request.form.get('bathrooms')) if request.form.get('bathrooms') else None
        property.area = float(request.form.get('area')) if request.form.get('area') else None
        property.property_type = request.form.get('property_type')
        property.status = request.form.get('status')
        # 添加缺失的字段
        property.rent = float(request.form.get('price'))  # 租金使用价格字段的值
        property.deposit = float(request.form.get('deposit')) if request.form.get('deposit') else None
        property.utility = request.form.get('utility')
        property.min_term = request.form.get('min_term')
        # 解析结构化JSON字段并存入 extra_info
        extra = {}

        # 处理设施复选框数据
        facilities_list = []
        selected_facilities = request.form.getlist('facilities')

        # 设施映射表
        facility_mapping = {
            'wifi': {'icon': 'fa-wifi', 'label': '免费WiFi'},
            'tv': {'icon': 'fa-tv', 'label': '电视'},
            'parking': {'icon': 'fa-parking', 'label': '停车位'},
            'air_conditioning': {'icon': 'fa-snowflake', 'label': '空调'},
            'heating': {'icon': 'fa-fire', 'label': '暖气'},
            'kitchen': {'icon': 'fa-utensils', 'label': '厨房'},
            'refrigerator': {'icon': 'fa-cube', 'label': '冰箱'},
            'microwave': {'icon': 'fa-microchip', 'label': '微波炉'},
            'washing_machine': {'icon': 'fa-tshirt', 'label': '洗衣机'},
            'dishwasher': {'icon': 'fa-sink', 'label': '洗碗机'},
            'gym': {'icon': 'fa-dumbbell', 'label': '健身房'},
            'pool': {'icon': 'fa-swimming-pool', 'label': '游泳池'},
            'elevator': {'icon': 'fa-elevator', 'label': '电梯'},
            'security': {'icon': 'fa-shield-alt', 'label': '24小时安保'},
            'pets_allowed': {'icon': 'fa-paw', 'label': '允许宠物'}
        }

        # 添加选中的设施
        for facility in selected_facilities:
            if facility in facility_mapping:
                facilities_list.append(facility_mapping[facility])

        # 处理自定义设施
        custom_facilities = request.form.get('custom_facilities', '').strip()
        if custom_facilities:
            for custom in custom_facilities.split(','):
                custom = custom.strip()
                if custom:
                    facilities_list.append({'icon': 'fa-check', 'label': custom})

        if facilities_list:
            extra['facilities'] = facilities_list

        # 处理交通信息复选框数据
        traffic_list = []
        selected_traffic = request.form.getlist('traffic')

        # 交通映射表
        traffic_mapping = {
            'bus': {'icon': 'fa-bus', 'label': '附近公交站'},
            'subway': {'icon': 'fa-subway', 'label': '地铁站'},
            'taxi': {'icon': 'fa-taxi', 'label': '出租车站'},
            'bike': {'icon': 'fa-bicycle', 'label': '共享单车'},
            'airport': {'icon': 'fa-plane', 'label': '机场巴士'}
        }

        # 添加选中的交通信息
        for traffic in selected_traffic:
            if traffic in traffic_mapping:
                traffic_list.append(traffic_mapping[traffic])

        # 处理自定义交通信息
        custom_traffic = request.form.get('custom_traffic', '').strip()
        if custom_traffic:
            for custom in custom_traffic.split(','):
                custom = custom.strip()
                if custom:
                    traffic_list.append({'icon': 'fa-route', 'label': custom})

        if traffic_list:
            extra['traffic'] = traffic_list

        # 处理周边环境复选框数据
        surroundings_list = []
        selected_surroundings = request.form.getlist('surroundings')

        # 周边环境映射表
        surroundings_mapping = {
            'supermarket': {'icon': 'fa-shopping-basket', 'label': '附近超市'},
            'mall': {'icon': 'fa-shopping-bag', 'label': '购物中心'},
            'restaurant': {'icon': 'fa-utensils', 'label': '餐厅'},
            'school': {'icon': 'fa-school', 'label': '学校'},
            'hospital': {'icon': 'fa-hospital', 'label': '医院'},
            'library': {'icon': 'fa-book', 'label': '图书馆'},
            'park': {'icon': 'fa-tree', 'label': '公园'},
            'gym': {'icon': 'fa-dumbbell', 'label': '健身房'},
            'cinema': {'icon': 'fa-film', 'label': '电影院'}
        }

        # 添加选中的周边环境
        for surrounding in selected_surroundings:
            if surrounding in surroundings_mapping:
                surroundings_list.append(surroundings_mapping[surrounding])

        # 处理自定义周边环境
        custom_surroundings = request.form.get('custom_surroundings', '').strip()
        if custom_surroundings:
            for custom in custom_surroundings.split(','):
                custom = custom.strip()
                if custom:
                    surroundings_list.append({'icon': 'fa-map-marker-alt', 'label': custom})

        if surroundings_list:
            extra['surroundings'] = surroundings_list

        # 处理其他JSON字段
        for k in ['desc']:
            val = request.form.get(k)
            if val:
                try:
                    extra[k] = json.loads(val)
                except Exception:
                    pass
        for k in ['map','video']:
            val = request.form.get(k)
            if val:
                extra[k] = val
        if extra:
            property.extra_info = json.dumps(extra, ensure_ascii=False)
        # 处理图片上传
        images_uploaded = 0
        for image in request.files.getlist('images'):
            if image.filename:  # 确保文件不为空
                file_path = save_file(image)
                if file_path:
                    property_image = PropertyImage(path=file_path, property_id=property.id)
                    db.session.add(property_image)
                    images_uploaded += 1

        # 处理视频上传
        videos_uploaded = 0
        for video in request.files.getlist('videos'):
            if video.filename:  # 确保文件不为空
                file_path = save_file(video)
                if file_path:
                    property_video = PropertyVideo(path=file_path, property_id=property.id)
                    db.session.add(property_video)
                    videos_uploaded += 1

        db.session.commit()

        # 提供详细的成功信息
        success_msg = f'房源更新成功！'
        if images_uploaded > 0:
            success_msg += f' 新增了 {images_uploaded} 张图片。'
        if videos_uploaded > 0:
            success_msg += f' 新增了 {videos_uploaded} 个视频。'

        flash(success_msg, 'success')
        return redirect(url_for('admin_properties'))
    return render_template('admin/property_form.html', user=user, property=property)

@app.route('/admin/property/delete/<int:id>', methods=['POST'])
def admin_property_delete(id):
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))
    
    property = Property.query.get_or_404(id)
    
    # 安全删除房源和相关文件
    # 定义受保护的系统文件列表
    protected_files = {
        'static/images/icon_lg.png',
        '/static/images/icon_lg.png',
        'static/images/hero_bg.jpg',
        '/static/images/hero_bg.jpg',
        'static/images/favicon.ico',
        '/static/images/favicon.ico',
        'static/images/ic_e_a.png',
        '/static/images/ic_e_a.png',
        'static/images/ic_e_b.png',
        '/static/images/ic_e_b.png',
        'static/images/ic_e_c.png',
        '/static/images/ic_e_c.png',
        'static/images/ic_e_g.png',
        '/static/images/ic_e_g.png',
        'static/images/ic_e_h.png',
        '/static/images/ic_e_h.png'
    }

    # 分别处理图片和视频，只删除用户上传的文件和记录
    images_to_delete = []
    videos_to_delete = []

    # 检查图片文件
    for image in property.images:
        try:
            if image.path in protected_files:
                # 系统文件不删除记录，其他房源可能还在使用
                continue
            else:
                # 用户上传的文件，可以安全删除
                images_to_delete.append(image)
                if os.path.exists(image.path):
                    os.remove(image.path)
        except Exception as e:
            # 即使文件删除失败，也删除数据库记录
            images_to_delete.append(image)

    # 检查视频文件
    for video in property.videos:
        try:
            if video.path in protected_files:
                continue
            else:
                # 用户上传的文件，可以安全删除
                videos_to_delete.append(video)
                if os.path.exists(video.path):
                    os.remove(video.path)
        except Exception as e:
            # 即使文件删除失败，也删除数据库记录
            videos_to_delete.append(video)

    # 删除用户上传的文件记录
    for image in images_to_delete:
        db.session.delete(image)

    for video in videos_to_delete:
        db.session.delete(video)

    # 最后删除房源记录
    db.session.delete(property)
    db.session.commit()
    
    flash('Property deleted successfully', 'success')
    return jsonify({'success': True, 'message': 'Property deleted successfully'})

@app.route('/admin/property/toggle_status/<int:id>', methods=['POST'])
def admin_property_toggle_status(id):
    if 'user_id' not in session:
        return redirect(url_for('admin_login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.is_admin:
        return redirect(url_for('admin_login'))
    
    property = Property.query.get_or_404(id)
    
    if property.status == 'active':
        property.status = 'inactive'
    else:
        property.status = 'active'
    
    db.session.commit()
    
    return jsonify({'status': property.status})

@app.route('/api/properties')
def api_properties():
    """获取房源列表API - 支持筛选和排序"""
    try:
        # 获取筛选参数
        location = request.args.get('location')
        property_type = request.args.get('property_type')
        min_price = request.args.get('min_price', type=float)
        max_price = request.args.get('max_price', type=float)
        currency = request.args.get('currency')
        country = request.args.get('country')
        status = request.args.get('status', 'active')  # 默认只显示活跃房源
        sort_by = request.args.get('sort_by', 'created_at')  # 排序字段
        sort_order = request.args.get('sort_order', 'desc')  # 排序方向
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)

        # 构建基础查询
        query = Property.query

        # 状态筛选
        if status and status != 'all':
            query = query.filter_by(status=status)

        # 位置筛选
        if location and location != '全部':
            query = query.filter_by(location=location)

        # 房屋类型筛选
        if property_type and property_type != '全部':
            query = query.filter_by(property_type=property_type)

        # 国家筛选
        if country and country != '全部':
            query = query.filter_by(country=country)

        # 价格筛选
        if min_price is not None or max_price is not None or currency:
            if currency:
                query = query.filter_by(currency=currency)
            if min_price is not None:
                query = query.filter(Property.price >= min_price)
            if max_price is not None and max_price < 999999:  # 999999表示无上限
                query = query.filter(Property.price <= max_price)

        # 排序
        if sort_by == 'price':
            if sort_order == 'asc':
                query = query.order_by(Property.price.asc())
            else:
                query = query.order_by(Property.price.desc())
        elif sort_by == 'created_at':
            if sort_order == 'asc':
                query = query.order_by(Property.created_at.asc())
            else:
                query = query.order_by(Property.created_at.desc())
        elif sort_by == 'name':
            if sort_order == 'asc':
                query = query.order_by(Property.name.asc())
            else:
                query = query.order_by(Property.name.desc())
        else:
            # 默认按创建时间倒序
            query = query.order_by(Property.created_at.desc())

        # 分页
        if per_page > 100:  # 限制每页最大数量
            per_page = 100

        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        properties = pagination.items

        # 确保owner信息被加载（用于详情页联系信息）
        for prop in properties:
            if prop.owner:
                _ = prop.owner.phone
                _ = prop.owner.wechat
                _ = prop.owner.email
                _ = prop.owner.display_name
                _ = prop.owner.avatar

        return jsonify({
            'success': True,
            'data': [p.to_dict() for p in properties],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next
            },
            'filters': {
                'location': location,
                'property_type': property_type,
                'min_price': min_price,
                'max_price': max_price,
                'currency': currency,
                'country': country,
                'status': status,
                'sort_by': sort_by,
                'sort_order': sort_order
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/property/<int:id>')
def api_property(id):
    # 确保加载 owner 关系
    property = Property.query.get_or_404(id)
    # 显式访问owner属性以触发加载
    if property.owner:
        _ = property.owner.phone
        _ = property.owner.wechat
        _ = property.owner.email
        _ = property.owner.display_name
        _ = property.owner.avatar
    return jsonify(property.to_dict())

@app.route('/api/stats')
def api_stats():
    properties_count = Property.query.count()
    users_count = User.query.count()
    active_properties = Property.query.filter_by(status='active').count()
    pending_properties = Property.query.filter_by(status='pending').count()
    inactive_properties = Property.query.filter_by(status='inactive').count()

    # 计算真实的订单数据（基于房源状态变化）
    orders_count = active_properties + pending_properties  # 简单计算：已上架+待审核的房源数

    # 计算真实的消息数据（基于待审核房源数）
    messages_count = pending_properties  # 待审核房源可视为需要处理的消息

    return jsonify({
        'properties_count': properties_count,
        'users_count': users_count,
        'active_properties': active_properties,
        'pending_properties': pending_properties,
        'inactive_properties': inactive_properties,
        'orders_count': orders_count,
        'messages_count': messages_count
    })

@app.route('/api/send_email_code', methods=['POST'])
def send_email_code():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return jsonify({'success': False, 'msg': '邮箱不能为空'}), 400
    import random
    code = str(random.randint(100000, 999999))
    user = User.query.filter_by(email=email).first()
    if user:
        user.email_code = code
        user.email_code_sent_at = datetime.utcnow()
        db.session.commit()
    else:
        # 临时存储验证码到session
        session[f'email_code_{email}'] = code
        session[f'email_code_time_{email}'] = datetime.utcnow().isoformat()
    try:
        smtp_server = 'smtp.qq.com'
        smtp_port = 465
        sender = '994335223@qq.com'
        password = 'yiavgwqzvjjybdbc'  # 授权码
        msg = MIMEText(f'您的UniHome注册验证码为：{code}，5分钟内有效。', 'plain', 'utf-8')
        msg['From'] = formataddr(('UniHome平台', '994335223@qq.com'))
        msg['To'] = Header(email, 'utf-8')
        msg['Subject'] = Header('UniHome邮箱验证码', 'utf-8')
        server = smtplib.SMTP_SSL(smtp_server, smtp_port)
        server.login(sender, password)
        server.sendmail(sender, [email], msg.as_string())
        server.quit()
        return jsonify({'success': True, 'msg': '验证码已发送'})
    except Exception as e:
        # 静默处理邮件发送异常，不输出到控制台
        return jsonify({'success': False, 'msg': '邮件发送失败，请稍后重试'}), 500

@app.route('/api/register', methods=['POST'])
def api_register():
    data = request.get_json()
    email = data.get('email')
    code = data.get('code')
    password = data.get('password')
    if not all([email, code, password]):
        return jsonify({'success': False, 'msg': '请填写完整信息'}), 400
    user = User.query.filter_by(email=email).first()
    from datetime import timedelta
    if user:
        if not user.email_code or not user.email_code_sent_at:
            return jsonify({'success': False, 'msg': '请先获取验证码'}), 400
        if user.email_code != code or (datetime.utcnow() - user.email_code_sent_at) > timedelta(minutes=5):
            return jsonify({'success': False, 'msg': '验证码错误或已过期'}), 400
        user.set_password(password)
        user.email_verified = True
        user.email_code = None
        user.email_code_sent_at = None
        db.session.commit()
        return jsonify({'success': True, 'msg': '注册成功'})
    else:
        # 校验session中的验证码
        session_code = session.get(f'email_code_{email}')
        session_time = session.get(f'email_code_time_{email}')
        if not session_code or not session_time:
            return jsonify({'success': False, 'msg': '请先获取验证码'}), 400
        from datetime import datetime
        code_time = datetime.fromisoformat(session_time)
        if session_code != code or (datetime.utcnow() - code_time) > timedelta(minutes=5):
            return jsonify({'success': False, 'msg': '验证码错误或已过期'}), 400
        # 创建新用户
        new_user = User(email=email, username=email)
        new_user.set_password(password)
        new_user.email_verified = True
        db.session.add(new_user)
        db.session.commit()
        # 清理session
        session.pop(f'email_code_{email}', None)
        session.pop(f'email_code_time_{email}', None)
        return jsonify({'success': True, 'msg': '注册成功'})

@app.route('/api/login', methods=['POST'])
def api_login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    if not all([email, password]):
        return jsonify({'success': False, 'msg': '请填写邮箱和密码'}), 400
    user = User.query.filter_by(email=email).first()
    if not user or not user.password_hash or not user.check_password(password):
        return jsonify({'success': False, 'msg': '邮箱或密码错误'}), 400
    if not user.email_verified:
        return jsonify({'success': False, 'msg': '邮箱未验证，请先完成注册邮箱验证'}), 400
    session['user_id'] = user.id
    return jsonify({'success': True, 'msg': '登录成功'})

@app.route('/api/current_user')
def api_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'success': False})
    user = User.query.get(user_id)
    if not user:
        return jsonify({'success': False})
    return jsonify({'success': True, 'email': user.email, 'username': user.username})

@app.route('/api/contact_info')
def api_contact_info():
    """获取管理员联系信息用于页脚显示"""
    # 获取第一个管理员用户的联系信息
    admin = User.query.filter_by(is_admin=True).first()
    if admin:
        return jsonify({
            'success': True,
            'contact': {
                'phone': admin.phone or '',
                'email': admin.email or '',
                'address': admin.address or '',
                'display_name': admin.display_name or admin.username
            }
        })
    else:
        # 如果没有管理员，返回默认信息
        return jsonify({
            'success': True,
            'contact': {
                'phone': '',
                'email': 'info@unihome.com',
                'address': '',
                'display_name': 'UniHome'
            }
        })

@app.route('/api/locations')
def api_locations():
    """获取位置列表API"""
    try:
        # 获取查询参数
        country = request.args.get('country')  # 可选：按国家筛选
        active_only = request.args.get('active_only', 'true').lower() == 'true'

        # 构建查询
        query = Location.query

        if active_only:
            query = query.filter_by(is_active=True)

        if country:
            query = query.filter_by(country=country)

        # 按排序顺序和名称排序
        locations = query.order_by(Location.sort_order, Location.name).all()

        # 如果没有指定国家，按国家分组返回
        if not country:
            result = {}
            for location in locations:
                country_key = location.country
                if country_key not in result:
                    result[country_key] = []
                result[country_key].append(location.to_dict())

            return jsonify({
                'success': True,
                'data': result,
                'total': len(locations)
            })
        else:
            # 指定国家，直接返回列表
            return jsonify({
                'success': True,
                'data': [location.to_dict() for location in locations],
                'total': len(locations)
            })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/property_types')
def api_property_types():
    """获取房屋类型列表API"""
    try:
        # 获取查询参数
        active_only = request.args.get('active_only', 'true').lower() == 'true'

        # 构建查询
        query = PropertyType.query

        if active_only:
            query = query.filter_by(is_active=True)

        # 按排序顺序和名称排序
        property_types = query.order_by(PropertyType.sort_order, PropertyType.name).all()

        return jsonify({
            'success': True,
            'data': [ptype.to_dict() for ptype in property_types],
            'total': len(property_types)
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/price_ranges')
def api_price_ranges():
    """获取价格区间API - 根据现有房源动态生成"""
    try:
        # 获取所有活跃房源的价格数据
        properties = Property.query.filter_by(status='active').all()

        if not properties:
            return jsonify({
                'success': True,
                'data': [],
                'message': '暂无房源数据'
            })

        # 按货币分组统计价格
        cad_prices = [p.price for p in properties if p.currency == '$']
        cny_prices = [p.price for p in properties if p.currency == '¥']

        price_ranges = []

        # 生成加拿大元价格区间
        if cad_prices:
            cad_min, cad_max = min(cad_prices), max(cad_prices)
            cad_ranges = generate_price_ranges(cad_min, cad_max, '$')
            price_ranges.extend(cad_ranges)

        # 生成人民币价格区间
        if cny_prices:
            cny_min, cny_max = min(cny_prices), max(cny_prices)
            cny_ranges = generate_price_ranges(cny_min, cny_max, '¥')
            price_ranges.extend(cny_ranges)

        return jsonify({
            'success': True,
            'data': price_ranges,
            'total': len(price_ranges),
            'stats': {
                'cad_count': len(cad_prices),
                'cny_count': len(cny_prices),
                'cad_range': [min(cad_prices), max(cad_prices)] if cad_prices else None,
                'cny_range': [min(cny_prices), max(cny_prices)] if cny_prices else None
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

def generate_price_ranges(min_price, max_price, currency):
    """生成价格区间"""
    ranges = []

    if currency == '$':
        # 加拿大元区间
        if max_price <= 800:
            ranges = [
                {'min': 0, 'max': 500, 'label': f'${currency}0-500', 'currency': currency},
                {'min': 500, 'max': 800, 'label': f'${currency}500-800', 'currency': currency},
            ]
        elif max_price <= 1500:
            ranges = [
                {'min': 0, 'max': 600, 'label': f'${currency}0-600', 'currency': currency},
                {'min': 600, 'max': 1000, 'label': f'${currency}600-1000', 'currency': currency},
                {'min': 1000, 'max': 1500, 'label': f'${currency}1000-1500', 'currency': currency},
            ]
        else:
            ranges = [
                {'min': 0, 'max': 800, 'label': f'${currency}0-800', 'currency': currency},
                {'min': 800, 'max': 1500, 'label': f'${currency}800-1500', 'currency': currency},
                {'min': 1500, 'max': 999999, 'label': f'${currency}1500+', 'currency': currency},
            ]
    else:  # ¥
        # 人民币区间
        if max_price <= 5000:
            ranges = [
                {'min': 0, 'max': 2000, 'label': f'{currency}0-2000', 'currency': currency},
                {'min': 2000, 'max': 3500, 'label': f'{currency}2000-3500', 'currency': currency},
                {'min': 3500, 'max': 5000, 'label': f'{currency}3500-5000', 'currency': currency},
            ]
        elif max_price <= 8000:
            ranges = [
                {'min': 0, 'max': 3000, 'label': f'{currency}0-3000', 'currency': currency},
                {'min': 3000, 'max': 5000, 'label': f'{currency}3000-5000', 'currency': currency},
                {'min': 5000, 'max': 8000, 'label': f'{currency}5000-8000', 'currency': currency},
            ]
        else:
            ranges = [
                {'min': 0, 'max': 4000, 'label': f'{currency}0-4000', 'currency': currency},
                {'min': 4000, 'max': 8000, 'label': f'{currency}4000-8000', 'currency': currency},
                {'min': 8000, 'max': 999999, 'label': f'{currency}8000+', 'currency': currency},
            ]

    return ranges

# 初始化数据库和创建管理员用户
def create_tables_and_admin():
    with app.app_context():
        db.create_all()
        # 如果没有管理员用户，创建一个
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(username='admin', email='admin@unihome.com', is_admin=True)
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
        # 自动添加演示房源（仅当没有房源时）
        if Property.query.count() == 0:
            demo_properties = [
            {
                'property': Property(
                    name='现代学生公寓',
                    description='位于多伦多市中心，步行5分钟到多伦多大学，设施齐全，安全舒适。',
                    location='多伦多',
                    country='Canada',
                    address='多伦多市中心，距离多伦多大学5分钟',
                    price=750,
                    currency='$',
                    bedrooms=2,
                    bathrooms=1,
                    area=60,
                    property_type='整套公寓',
                    status='active',
                    user_id=admin.id,
                    rent=750,
                    deposit=750,
                    utility='包含',
                    min_term='4个月'
                ),
                'image': 'ic_e_a.png',
                'landlord': {
                    'name': 'UniHome 管理员',
                    'avatar': 'static/images/icon_lg.png',
                    'phone': '+1 (123) 456-7890',
                    'email': 'admin@unihome.com',
                    'wechat': 'UniHome_Admin'
                },
                'desc': [
                    '这套现代化的学生公寓位于多伦多市中心，步行5分钟即可到达多伦多大学主校区。公寓内部装修精美，采光充足，设施齐全，是留学生理想的住所选择。',
                    '公寓共有2个卧室，1个卫生间，开放式厨房和宽敞的客厅区域。每个卧室均配有舒适的床垫、书桌、衣柜和床头柜。客厅配有沙发、电视和用餐区域。厨房配备了冰箱、烤箱、微波炉和洗碗机等现代化电器。',
                    '公寓楼设有24小时安保系统，健身房，公共学习区域和洗衣房。周围交通便利，有多条公交线路和地铁站，同时步行范围内有多家超市、餐厅和咖啡馆。'
                ],
                'facilities': [
                    {'icon': 'fa-wifi', 'label': '免费WiFi'},
                    {'icon': 'fa-temperature-low', 'label': '空调'},
                    {'icon': 'fa-utensils', 'label': '设备齐全的厨房'},
                    {'icon': 'fa-tv', 'label': '电视'},
                    {'icon': 'fa-washing-machine', 'label': '洗衣机'},
                    {'icon': 'fa-dumbbell', 'label': '健身房'},
                    {'icon': 'fa-shield-alt', 'label': '24小时安保'},
                    {'icon': 'fa-desktop', 'label': '公共学习区'},
                    {'icon': 'fa-parking', 'label': '停车位'}
                ],
                'traffic': [
                    {'icon': 'fa-subway', 'label': "最近地铁站：Queen's Park Station (步行3分钟)"},
                    {'icon': 'fa-bus', 'label': '公交站：College Street at University Avenue (步行2分钟)'},
                    {'icon': 'fa-bicycle', 'label': '自行车共享站：College Street (步行1分钟)'}
                ],
                'surroundings': [
                    {'icon': 'fa-shopping-basket', 'label': '超市：Loblaws (步行7分钟)'},
                    {'icon': 'fa-utensils', 'label': '餐厅：多家餐厅和咖啡馆 (步行5分钟内)'},
                    {'icon': 'fa-book', 'label': '图书馆：Robarts Library (步行8分钟)'},
                    {'icon': 'fa-hospital', 'label': '医院：Toronto General Hospital (步行10分钟)'}
                ],
                'map': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d2886.2008271359426!2d-79.39939548450163!3d43.66098397912126!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x882b34b8a4000001%3A0x50fea143d86f2d30!2sUniversity%20of%20Toronto!5e0!3m2!1sen!2sca!4v1620927112519!5m2!1sen!2sca',
                'video': 'https://www.youtube.com/embed/dQw4w9WgXcQ',
                'images': [
                    'static/images/ic_e_a.png',
                    'static/images/ic_e_b.png',
                    'static/images/ic_e_c.png',
                    'static/images/ic_e_d.png',
                    'static/images/ic_e_e.png',
                    'static/images/ic_e_f.png'
                ]
            },
            {
                'property': Property(
                    name='海淀区豪华学生公寓',
                    description='靠近清华大学，交通便利，配备独立卫浴和厨房。',
                    location='北京',
                    country='China',
                    address='北京海淀区，距离清华大学10分钟',
                    price=3500,
                    currency='¥',
                    bedrooms=1,
                    bathrooms=1,
                    area=35,
                    property_type='学生宿舍',
                    status='active',
                    user_id=admin.id,
                    rent=3500,
                    deposit=3500,
                    utility='包含',
                    min_term='6个月'
                ),
                'image': 'ic_e_b.png',
                'landlord': {
                    'name': '北京管理员',
                    'avatar': 'static/images/icon_lg.png',
                    'phone': '+86 123 4567 8901',
                    'email': 'admin@unihome.com',
                    'wechat': 'Beijing_Admin'
                },
                'desc': [
                    '豪华学生公寓，靠近清华大学，交通便利，生活配套齐全。',
                    '配备独立卫浴、厨房、学习区，适合高端留学生入住。'
                ],
                'facilities': [
                    {'icon': 'fa-wifi', 'label': '免费WiFi'},
                    {'icon': 'fa-temperature-low', 'label': '空调'},
                    {'icon': 'fa-utensils', 'label': '设备齐全的厨房'},
                    {'icon': 'fa-tv', 'label': '电视'},
                    {'icon': 'fa-warehouse', 'label': '洗衣机'},
                    {'icon': 'fa-shield-alt', 'label': '24小时安保'}
                ],
                'traffic': [
                    {'icon': 'fa-subway', 'label': '地铁站：五道口 (步行5分钟)'},
                    {'icon': 'fa-bus', 'label': '公交站：成府路口南 (步行3分钟)'}
                ],
                'surroundings': [
                    {'icon': 'fa-shopping-basket', 'label': '超市：物美 (步行8分钟)'},
                    {'icon': 'fa-utensils', 'label': '餐厅：清华园食堂 (步行6分钟)'}
                ]
            },
            {
                'property': Property(
                    name='市中心现代公寓',
                    description='温哥华市中心，靠近UBC，拎包入住。',
                    location='温哥华',
                    country='Canada',
                    address='温哥华市中心，靠近UBC',
                    price=850,
                    currency='$',
                    bedrooms=1,
                    bathrooms=1,
                    area=40,
                    property_type='整套公寓',
                    status='active',
                    user_id=admin.id,
                    rent=850,
                    deposit=850,
                    utility='包含',
                    min_term='3个月'
                ),
                'image': 'ic_e_c.png',
                'landlord': {
                    'name': '温哥华管理员',
                    'avatar': 'static/images/icon_lg.png',
                    'phone': '+1 (123) 456-7890',
                    'email': 'admin@unihome.com',
                    'wechat': 'Vancouver_Admin'
                },
                'desc': [
                    '现代化公寓，靠近UBC，配套设施齐全，拎包入住。'
                ],
                'facilities': [
                    {'icon': 'fa-wifi', 'label': '免费WiFi'},
                    {'icon': 'fa-tv', 'label': '电视'},
                    {'icon': 'fa-parking', 'label': '停车位'}
                ],
                'traffic': [
                    {'icon': 'fa-bus', 'label': '公交站：UBC Exchange (步行2分钟)'}
                ],
                'surroundings': [
                    {'icon': 'fa-shopping-basket', 'label': '超市：Save-On-Foods (步行10分钟)'}
                ]
            },
            {
                'property': Property(
                    name='浦东新区精品公寓',
                    description='靠近上海交通大学，生活便利，环境优美。',
                    location='上海',
                    country='China',
                    address='上海浦东新区，靠近上海交通大学',
                    price=4200,
                    currency='¥',
                    bedrooms=2,
                    bathrooms=1,
                    area=55,
                    property_type='合租房间',
                    status='active',
                    user_id=admin.id,
                    rent=4200,
                    deposit=4200,
                    utility='包含',
                    min_term='5个月'
                ),
                'image': 'ic_e_d.png',
                'landlord': {
                    'name': '上海管理员',
                    'avatar': 'static/images/icon_lg.png',
                    'phone': '+86 123 4567 8901',
                    'email': 'admin@unihome.com',
                    'wechat': 'Shanghai_Admin'
                },
                'desc': [
                    '精品公寓，靠近上海交通大学，生活便利，环境优美。'
                ],
                'facilities': [
                    {'icon': 'fa-wifi', 'label': '免费WiFi'},
                    {'icon': 'fa-tv', 'label': '电视'},
                    {'icon': 'fa-parking', 'label': '停车位'}
                ],
                'traffic': [
                    {'icon': 'fa-bus', 'label': '公交站：交大站 (步行3分钟)'}
                ],
                'surroundings': [
                    {'icon': 'fa-shopping-basket', 'label': '超市：家乐福 (步行8分钟)'}
                ]
            },
            {
                'property': Property(
                    name='经济型学生宿舍',
                    description='多伦多北约克区，靠近约克大学，适合预算有限的留学生。',
                    location='多伦多',
                    country='Canada',
                    address='多伦多北约克区，靠近约克大学',
                    price=550,
                    currency='$',
                    bedrooms=1,
                    bathrooms=1,
                    area=20,
                    property_type='学生宿舍',
                    status='active',
                    user_id=admin.id,
                    rent=550,
                    deposit=550,
                    utility='包含',
                    min_term='2个月'
                ),
                'image': 'ic_e_e.png',
                'landlord': {
                    'name': '多伦多管理员',
                    'avatar': 'static/images/icon_lg.png',
                    'phone': '+1 (123) 456-7890',
                    'email': 'admin@unihome.com',
                    'wechat': 'Toronto_Admin'
                },
                'desc': [
                    '经济型宿舍，适合预算有限的留学生，交通便利。'
                ],
                'facilities': [
                    {'icon': 'fa-wifi', 'label': '免费WiFi'},
                    {'icon': 'fa-tv', 'label': '电视'},
                    {'icon': 'fa-parking', 'label': '停车位'}
                ],
                'traffic': [
                    {'icon': 'fa-bus', 'label': '公交站：约克大学站 (步行2分钟)'}
                ],
                'surroundings': [
                    {'icon': 'fa-shopping-basket', 'label': '超市：No Frills (步行10分钟)'}
                ]
            },
            {
                'property': Property(
                    name='中关村环绕式公寓',
                    description='北京中关村，靠近北京大学，学习氛围浓厚。',
                    location='北京',
                    country='China',
                    address='北京中关村，靠近北京大学',
                    price=2800,
                    currency='¥',
                    bedrooms=1,
                    bathrooms=1,
                    area=25,
                    property_type='学生宿舍',
                    status='active',
                    user_id=admin.id,
                    rent=2800,
                    deposit=2800,
                    utility='包含',
                    min_term='3个月'
                ),
                'image': 'ic_e_f.png',
                'landlord': {
                    'name': '北京管理员',
                    'avatar': 'static/images/icon_lg.png',
                    'phone': '+86 123 4567 8901',
                    'email': 'admin@unihome.com',
                    'wechat': 'Beijing_Admin'
                },
                'desc': [
                    '环绕式公寓，靠近北京大学，学习氛围浓厚。'
                ],
                'facilities': [
                    {'icon': 'fa-wifi', 'label': '免费WiFi'},
                    'fa-tv',
                    'fa-parking',
                ],
                'traffic': [
                    {'icon': 'fa-bus', 'label': '公交站：北京大学东门 (步行2分钟)'}
                ],
                'surroundings': [
                    {'icon': 'fa-shopping-basket', 'label': '超市：物美 (步行10分钟)'}
                ]
            },
            ]
            for item in demo_properties:
                db.session.add(item['property'])
                db.session.commit()  # 先提交以获得property.id
                property_image = PropertyImage(path=f'static/images/{item["image"]}', property_id=item['property'].id)
                db.session.add(property_image)
                # 将所有演示数据写入 property 的自定义属性，便于 to_dict 返回
                for k in ['landlord','desc','facilities','traffic','surroundings','map','video','images']:
                    setattr(item['property'], f'_demo_{k}', item.get(k, [] if k not in ['landlord','map','video'] else {}))
            db.session.commit()
    # 用户上传图片也统一保存到 static/images 下
    app.config['UPLOAD_FOLDER'] = 'static/images'

# 修改 Property.to_dict 方法，优先返回演示数据并兜底所有字段
Property._origin_to_dict = Property.to_dict

def property_to_dict_with_demo(self):
    d = self._origin_to_dict()

    # 首先从 extra_info 读取实际数据
    extra = {}
    if getattr(self, 'extra_info', None):
        try:
            extra = json.loads(self.extra_info)
        except Exception:
            extra = {}

    # 更新字典中的数据，优先使用 extra_info 中的实际数据
    for k in ['desc','facilities','traffic','surroundings','map','videos']:
        if k in extra and extra[k]:
            d[k] = extra[k]

    # 特殊处理视频字段：优先使用视频URL，如果没有则使用上传的视频文件
    if 'video' in extra and extra['video']:
        d['video'] = extra['video']
    elif d.get('videos') and len(d['videos']) > 0:
        # 如果有上传的视频文件，使用第一个视频文件的路径
        d['video'] = d['videos'][0]
    else:
        d['video'] = ''

    # 处理房东信息：从实际的 owner 关系中获取
    if hasattr(self, 'owner') and self.owner:
        d['landlord'] = {
            'name': self.owner.display_name or self.owner.username,
            'avatar': self.owner.avatar or 'static/images/icon_lg.png',
            'phone': self.owner.phone or '',
            'email': self.owner.email or '',
            'wechat': self.owner.wechat or ''
        }
    else:
        d['landlord'] = {
            'name': '房源管理员',
            'avatar': 'static/images/icon_lg.png',
            'phone': '',
            'email': '',
            'wechat': ''
        }

    # 兜底内容（仅在没有实际数据时使用）
    default_demo = {
        'desc': [
            '本房源暂无详细介绍。欢迎联系房东获取更多信息。'
        ],
        'facilities': [
            {'icon': 'fa-wifi', 'label': '免费WiFi'},
            {'icon': 'fa-tv', 'label': '电视'},
            {'icon': 'fa-parking', 'label': '停车位'}
        ],
        'traffic': [
            {'icon': 'fa-bus', 'label': '附近公交站'}
        ],
        'surroundings': [
            {'icon': 'fa-shopping-basket', 'label': '附近超市'}
        ],
        'map': 'https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d2886.2008271359426!2d-79.39939548450163!3d43.66098397912126!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x882b34b8a4000001%3A0x50fea143d86f2d30!2sUniversity%20of%20Toronto!5e0!3m2!1sen!2sca!4v1620927112519!5m2!1sen!2sca',
        'video': '',
        'images': d.get('images', ['static/images/icon_lg.png'])
    }

    # 对于演示数据，优先使用演示数据（如果存在）
    for k in ['landlord','desc','facilities','traffic','surroundings','map','video','videos','images']:
        demo_value = getattr(self, f'_demo_{k}', None)
        if demo_value is not None and demo_value != [] and demo_value != '':
            # 有演示数据，使用演示数据
            d[k] = demo_value
        elif k not in d or not d[k]:
            # 特殊处理desc字段：如果有description，就不使用默认desc
            if k == 'desc' and d.get('description'):
                d[k] = []  # 有description时，desc为空数组
            else:
                # 没有演示数据且没有实际数据，使用默认兜底数据
                d[k] = default_demo.get(k, [] if k in ['desc','facilities','traffic','surroundings','images','videos'] else ({} if k=='landlord' else ''))

    # 确保所有必要字段都存在
    for key in ['desc','facilities','traffic','surroundings','landlord','map','video','videos','images','rent','deposit','utility','min_term']:
        if key not in d:
            # 特殊处理desc字段：如果有description，就不设置默认desc
            if key == 'desc' and d.get('description'):
                d[key] = []
            else:
                d[key] = [] if key in ['desc','facilities','traffic','surroundings','images','videos'] else ({} if key=='landlord' else '')

    # 处理字段名映射
    d['minTerm'] = d.get('min_term', '')

    return d
Property.to_dict = property_to_dict_with_demo


# 预约看房API
@app.route('/api/appointments', methods=['POST'])
def api_create_appointment():
    """创建预约看房"""
    try:
        data = request.get_json()
        
        # 验证必填字段
        required_fields = ['property_id', 'name', 'phone', 'preferred_date', 'preferred_time']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'缺少必填字段: {field}'
                }), 400
        
        # 验证房源是否存在
        property_obj = Property.query.get(data['property_id'])
        if not property_obj:
            return jsonify({
                'success': False,
                'message': '房源不存在'
            }), 404
        
        # 创建预约
        appointment = Appointment(
            property_id=data['property_id'],
            name=data['name'],
            phone=data['phone'],
            email=data.get('email', ''),
            preferred_date=data['preferred_date'],
            preferred_time=data['preferred_time'],
            message=data.get('message', ''),
            status='pending'
        )
        
        db.session.add(appointment)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': '预约提交成功，我们会尽快联系您',
            'data': appointment.to_dict()
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'预约提交失败: {str(e)}'
        }), 500

@app.route('/api/appointments')
def api_get_appointments():
    """获取预约列表（管理员用）"""
    try:
        # 检查管理员权限
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': '未登录'}), 401
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'success': False, 'message': '权限不足'}), 403
        
        # 获取查询参数
        status = request.args.get('status')
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # 构建查询
        query = Appointment.query
        
        if status and status != 'all':
            query = query.filter_by(status=status)
        
        # 按创建时间倒序排列
        query = query.order_by(Appointment.created_at.desc())
        
        # 分页
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        appointments = pagination.items
        
        return jsonify({
            'success': True,
            'data': [appointment.to_dict() for appointment in appointments],
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/appointments/<int:id>', methods=['PUT'])
def api_update_appointment(id):
    """更新预约状态（管理员用）"""
    try:
        # 检查管理员权限
        if 'user_id' not in session:
            return jsonify({'success': False, 'message': '未登录'}), 401
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return jsonify({'success': False, 'message': '权限不足'}), 403
        
        appointment = Appointment.query.get_or_404(id)
        data = request.get_json()
        
        # 更新状态
        if 'status' in data:
            valid_statuses = ['pending', 'confirmed', 'cancelled', 'completed']
            if data['status'] in valid_statuses:
                appointment.status = data['status']
                appointment.updated_at = datetime.utcnow()
                
                db.session.commit()
                
                return jsonify({
                    'success': True,
                    'message': '预约状态更新成功',
                    'data': appointment.to_dict()
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '无效的状态值'
                }), 400
        else:
            return jsonify({
                'success': False,
                'message': '缺少状态字段'
            }), 400
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# 收藏功能API
@app.route('/api/favorites', methods=['POST'])
def api_add_favorite():
    """添加收藏"""
    try:
        # 检查用户是否登录
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'message': '请先登录',
                'need_login': True
            }), 401

        data = request.get_json()
        property_id = data.get('property_id')

        if not property_id:
            return jsonify({
                'success': False,
                'message': '缺少房源ID'
            }), 400

        # 检查房源是否存在
        property_obj = Property.query.get(property_id)
        if not property_obj:
            return jsonify({
                'success': False,
                'message': '房源不存在'
            }), 404

        user_id = session['user_id']

        # 检查是否已经收藏
        existing_favorite = Favorite.query.filter_by(
            user_id=user_id,
            property_id=property_id
        ).first()

        if existing_favorite:
            return jsonify({
                'success': False,
                'message': '已经收藏过此房源'
            }), 400

        # 创建收藏记录
        favorite = Favorite(
            user_id=user_id,
            property_id=property_id
        )

        db.session.add(favorite)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '收藏成功',
            'data': favorite.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'收藏失败: {str(e)}'
        }), 500

@app.route('/api/favorites/<int:property_id>', methods=['DELETE'])
def api_remove_favorite(property_id):
    """取消收藏"""
    try:
        # 检查用户是否登录
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'message': '请先登录',
                'need_login': True
            }), 401

        user_id = session['user_id']

        # 查找收藏记录
        favorite = Favorite.query.filter_by(
            user_id=user_id,
            property_id=property_id
        ).first()

        if not favorite:
            return jsonify({
                'success': False,
                'message': '未收藏此房源'
            }), 404

        # 删除收藏记录
        db.session.delete(favorite)
        db.session.commit()

        return jsonify({
            'success': True,
            'message': '取消收藏成功'
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'success': False,
            'message': f'取消收藏失败: {str(e)}'
        }), 500

@app.route('/api/favorites')
def api_get_favorites():
    """获取用户收藏列表"""
    try:
        # 检查用户是否登录
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'message': '请先登录',
                'need_login': True
            }), 401

        user_id = session['user_id']

        # 获取用户的收藏列表
        favorites = Favorite.query.filter_by(user_id=user_id)\
                                 .order_by(Favorite.created_at.desc())\
                                 .all()

        return jsonify({
            'success': True,
            'data': [favorite.to_dict() for favorite in favorites]
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取收藏列表失败: {str(e)}'
        }), 500

@app.route('/api/favorites/check/<int:property_id>')
def api_check_favorite(property_id):
    """检查房源是否已收藏"""
    try:
        # 检查用户是否登录
        if 'user_id' not in session:
            return jsonify({
                'success': True,
                'is_favorited': False,
                'need_login': True
            })

        user_id = session['user_id']

        # 检查是否已收藏
        favorite = Favorite.query.filter_by(
            user_id=user_id,
            property_id=property_id
        ).first()

        return jsonify({
            'success': True,
            'is_favorited': favorite is not None,
            'need_login': False
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'检查收藏状态失败: {str(e)}'
        }), 500

# 管理端客户收藏管理API
@app.route('/api/admin/customer_favorites')
def api_admin_customer_favorites():
    """管理端获取客户收藏列表"""
    try:
        # 检查管理员权限
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401

        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return jsonify({
                'success': False,
                'message': '权限不足'
            }), 403

        # 获取查询参数
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '').strip()
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        property_id = request.args.get('property_id', type=int)
        user_id = request.args.get('user_id', type=int)

        # 构建查询
        query = db.session.query(Favorite)\
                          .join(User, Favorite.user_id == User.id)\
                          .join(Property, Favorite.property_id == Property.id)

        # 搜索过滤
        if search:
            query = query.filter(
                db.or_(
                    User.username.contains(search),
                    User.email.contains(search),
                    Property.name.contains(search),
                    Property.location.contains(search)
                )
            )

        # 时间范围过滤
        if date_from:
            try:
                from datetime import datetime as dt
                from_date = dt.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Favorite.created_at >= from_date)
            except ValueError:
                pass

        if date_to:
            try:
                from datetime import datetime as dt
                to_date = dt.strptime(date_to, '%Y-%m-%d')
                # 包含整天，所以加1天
                to_date = to_date.replace(hour=23, minute=59, second=59)
                query = query.filter(Favorite.created_at <= to_date)
            except ValueError:
                pass

        # 房源过滤
        if property_id:
            query = query.filter(Favorite.property_id == property_id)

        # 用户过滤
        if user_id:
            query = query.filter(Favorite.user_id == user_id)

        # 排序
        query = query.order_by(Favorite.created_at.desc())

        # 分页
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )

        favorites = pagination.items

        # 构建返回数据
        data = []
        for favorite in favorites:
            data.append({
                'id': favorite.id,
                'user': {
                    'id': favorite.user.id,
                    'username': favorite.user.username,
                    'email': favorite.user.email,
                    'created_at': favorite.user.created_at.isoformat() if favorite.user.created_at else None
                },
                'property': {
                    'id': favorite.property.id,
                    'name': favorite.property.name,
                    'location': favorite.property.location,
                    'price': favorite.property.price,
                    'currency': favorite.property.currency,
                    'price_unit': favorite.property.price_unit,
                    'images': favorite.property.images[:1] if favorite.property.images else []  # 只返回第一张图片
                },
                'created_at': favorite.created_at.isoformat() if favorite.created_at else None
            })

        return jsonify({
            'success': True,
            'data': data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': pagination.total,
                'pages': pagination.pages,
                'has_prev': pagination.has_prev,
                'has_next': pagination.has_next
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取客户收藏列表失败: {str(e)}'
        }), 500

@app.route('/api/admin/customer_favorites/stats')
def api_admin_customer_favorites_stats():
    """管理端获取客户收藏统计数据"""
    try:
        # 检查管理员权限
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401

        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return jsonify({
                'success': False,
                'message': '权限不足'
            }), 403

        # 总收藏数
        total_favorites = Favorite.query.count()

        # 今日新增收藏
        from datetime import datetime as dt
        today = dt.now().date()
        today_favorites = Favorite.query.filter(
            db.func.date(Favorite.created_at) == today
        ).count()

        # 本周新增收藏
        from datetime import timedelta
        week_ago = dt.now() - timedelta(days=7)
        week_favorites = Favorite.query.filter(
            Favorite.created_at >= week_ago
        ).count()

        # 热门房源TOP5
        popular_properties = db.session.query(
            Property.id,
            Property.name,
            Property.location,
            db.func.count(Favorite.id).label('favorite_count')
        ).join(Favorite, Property.id == Favorite.property_id)\
         .group_by(Property.id)\
         .order_by(db.func.count(Favorite.id).desc())\
         .limit(5).all()

        # 活跃客户TOP5
        active_users = db.session.query(
            User.id,
            User.username,
            User.email,
            db.func.count(Favorite.id).label('favorite_count')
        ).join(Favorite, User.id == Favorite.user_id)\
         .group_by(User.id)\
         .order_by(db.func.count(Favorite.id).desc())\
         .limit(5).all()

        return jsonify({
            'success': True,
            'data': {
                'total_favorites': total_favorites,
                'today_favorites': today_favorites,
                'week_favorites': week_favorites,
                'popular_properties': [
                    {
                        'id': prop.id,
                        'name': prop.name,
                        'location': prop.location,
                        'favorite_count': prop.favorite_count
                    } for prop in popular_properties
                ],
                'active_users': [
                    {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'favorite_count': user.favorite_count
                    } for user in active_users
                ]
            }
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取统计数据失败: {str(e)}'
        }), 500

@app.route('/api/admin/customer_favorites/export')
def api_admin_customer_favorites_export():
    """管理端导出客户收藏数据为Excel"""
    try:
        # 检查管理员权限
        if 'user_id' not in session:
            return jsonify({
                'success': False,
                'message': '请先登录'
            }), 401

        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return jsonify({
                'success': False,
                'message': '权限不足'
            }), 403

        # 获取查询参数
        search = request.args.get('search', '').strip()
        date_from = request.args.get('date_from', '')
        date_to = request.args.get('date_to', '')
        property_id = request.args.get('property_id', type=int)
        user_id = request.args.get('user_id', type=int)

        # 构建查询（不分页，获取所有数据）
        query = db.session.query(Favorite)\
                          .join(User, Favorite.user_id == User.id)\
                          .join(Property, Favorite.property_id == Property.id)

        # 应用筛选条件
        if search:
            query = query.filter(
                db.or_(
                    User.username.contains(search),
                    User.email.contains(search),
                    Property.name.contains(search),
                    Property.location.contains(search)
                )
            )

        if date_from:
            try:
                from datetime import datetime as dt
                from_date = dt.strptime(date_from, '%Y-%m-%d')
                query = query.filter(Favorite.created_at >= from_date)
            except ValueError:
                pass

        if date_to:
            try:
                from datetime import datetime as dt
                to_date = dt.strptime(date_to, '%Y-%m-%d')
                to_date = to_date.replace(hour=23, minute=59, second=59)
                query = query.filter(Favorite.created_at <= to_date)
            except ValueError:
                pass

        if property_id:
            query = query.filter(Favorite.property_id == property_id)

        if user_id:
            query = query.filter(Favorite.user_id == user_id)

        # 排序
        query = query.order_by(Favorite.created_at.desc())

        favorites = query.all()

        # 创建CSV内容
        import io
        import csv
        from datetime import datetime as dt

        output = io.StringIO()
        writer = csv.writer(output)

        # 写入表头
        writer.writerow([
            '收藏ID',
            '客户姓名',
            '客户邮箱',
            '客户注册时间',
            '房源名称',
            '房源位置',
            '房源价格',
            '货币',
            '价格单位',
            '收藏时间'
        ])

        # 写入数据
        for favorite in favorites:
            writer.writerow([
                favorite.id,
                favorite.user.username,
                favorite.user.email,
                favorite.user.created_at.strftime('%Y-%m-%d %H:%M:%S') if favorite.user.created_at else '',
                favorite.property.name,
                favorite.property.location,
                favorite.property.price,
                favorite.property.currency,
                favorite.property.price_unit,
                favorite.created_at.strftime('%Y-%m-%d %H:%M:%S') if favorite.created_at else ''
            ])

        # 准备响应
        output.seek(0)
        csv_content = output.getvalue()
        output.close()

        # 生成文件名
        timestamp = dt.now().strftime('%Y%m%d_%H%M%S')
        filename = f'客户收藏数据_{timestamp}.csv'

        # 返回CSV文件
        from flask import make_response
        response = make_response(csv_content)
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'导出失败: {str(e)}'
        }), 500

if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    # 初始化数据库和管理员用户
    create_tables_and_admin()

    # 获取端口号（支持云平台部署）
    port = int(os.environ.get('PORT', 5000))
    host = os.environ.get('HOST', '127.0.0.1')
    debug = os.environ.get('DEBUG', 'True').lower() == 'true'

    # 云平台部署时使用0.0.0.0监听所有接口
    if 'PORT' in os.environ:
        host = '0.0.0.0'
        debug = False

    # 生产模式运行，关闭调试信息
    print("🏠 UniHome 租房平台启动成功!")
    print(f"📱 前台访问: http://{host}:{port}")
    print(f"🔧 管理后台: http://{host}:{port}/admin/login")
    print("👤 管理员账号: admin / admin123")
    print("=" * 50)

    app.run(debug=debug, host=host, port=port)