"""
다온 클래스 - 단일 파일 버전
실행: python main.py
"""

import os
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template_string, request, redirect, url_for,
    session, flash, send_file, abort
)
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

# ==================== 설정 ====================
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "daon-class-secret-key-change-me")

database_url = os.environ.get("DATABASE_URL", "sqlite:///daon.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

db = SQLAlchemy(app)

BANK_NAME = os.environ.get("BANK_NAME", "카카오뱅크")
BANK_ACCOUNT = os.environ.get("BANK_ACCOUNT", "7777-03-0806539")
BANK_HOLDER = os.environ.get("BANK_HOLDER", "김시우")


# ==================== 모델 ====================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120))
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Integer, nullable=False)
    pdf_filename = db.Column(db.String(300))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.String(64), unique=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("product.id"), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)

    user = db.relationship("User", backref="orders")
    product = db.relationship("Product", backref="orders")

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.order_id:
            self.order_id = f"DAON-{datetime.now().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("로그인이 필요합니다.", "error")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        user = User.query.get(session["user_id"])
        if not user or not user.is_admin:
            flash("관리자만 접근 가능합니다.", "error")
            return redirect(url_for("index"))
        return f(*args, **kwargs)
    return decorated


def current_user():
    if "user_id" in session:
        return User.query.get(session["user_id"])
    return None


BASE_HTML = """
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}다온 클래스{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">
    <nav class="bg-white shadow-sm border-b">
        <div class="max-w-5xl mx-auto px-4 py-3 flex justify-between items-center">
            <a href="/" class="text-xl font-bold text-indigo-600">다온 클래스</a>
            <div class="flex gap-4 items-center text-sm">
                {% if user %}
                    <a href="/my-courses" class="text-gray-600 hover:text-indigo-600 font-medium">내 강의</a>
                    <a href="/my-orders" class="text-gray-600 hover:text-indigo-600">주문내역</a>
                    {% if user.is_admin %}
                        <a href="/admin" class="text-red-600 hover:text-red-700 font-medium">관리자</a>
                    {% endif %}
                    <a href="/logout" class="text-gray-500">로그아웃</a>
                {% else %}
                    <a href="/login" class="text-gray-600 hover:text-indigo-600">로그인</a>
                    <a href="/signup" class="bg-indigo-600 text-white px-4 py-1.5 rounded-lg hover:bg-indigo-700">회원가입</a>
                {% endif %}
            </div>
        </div>
    </nav>
    <main class="max-w-5xl mx-auto px-4 py-8">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="mb-4 p-4 rounded-lg {{ 'bg-red-100 text-red-700' if category == 'error' else 'bg-green-100 text-green-700' }}">
                        {{ message }}
                    </div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        {% block content %}{% endblock %}
    </main>
    <footer class="border-t mt-12 py-6 text-center text-gray-500 text-sm">© 2026 다온 클래스</footer>
</body>
</html>
"""


@app.route("/")
def index():
    products = Product.query.filter_by(is_active=True).order_by(Product.created_at.desc()).all()
    return render_template_string(BASE_HTML + """
    {% block content %}
    <h1 class="text-3xl font-bold mb-8">강의 목록</h1>
    <div class="grid md:grid-cols-2 gap-6">
        {% for p in products %}
        <div class="bg-white rounded-xl border shadow-sm p-6">
            <h2 class="text-xl font-semibold mb-2">{{ p.title }}</h2>
            <p class="text-gray-600 text-sm mb-4">{{ p.description[:80] }}{% if p.description|length > 80 %}...{% endif %}</p>
            <div class="flex justify-between items-center">
                <span class="text-indigo-600 font-bold text-lg">{{ "{:,}".format(p.price) }}원</span>
                <a href="/product/{{ p.id }}" class="bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm">상세보기</a>
            </div>
        </div>
        {% else %}
        <p class="text-gray-500">등록된 강의가 없습니다.</p>
        {% endfor %}
    </div>
    {% endblock %}
    """, products=products, user=current_user())


@app.route("/product/<int:pid>")
def product_detail(pid):
    product = Product.query.get_or_404(pid)
    return render_template_string(BASE_HTML + """
    {% block content %}
    <div class="bg-white rounded-xl border p-8">
        <h1 class="text-3xl font-bold mb-4">{{ product.title }}</h1>
        <p class="text-2xl text-indigo-600 font-bold mb-6">{{ "{:,}".format(product.price) }}원</p>
        <div class="text-gray-700 whitespace-pre-line mb-8">{{ product.description }}</div>
        {% if user %}
            <a href="/order/{{ product.id }}" class="inline-block bg-indigo-600 text-white px-8 py-3 rounded-lg">구매하기</a>
        {% else %}
            <a href="/login" class="inline-block bg-indigo-600 text-white px-8 py-3 rounded-lg">로그인 후 구매하기</a>
        {% endif %}
    </div>
    {% endblock %}
    """, product=product, user=current_user())


@app.route("/signup", methods=["GET", "POST"])
def signup():
    if current_user():
        return redirect("/")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        if not username or not password:
            flash("아이디와 비밀번호를 입력하세요.", "error")
        elif User.query.filter_by(username=username).first():
            flash("이미 존재하는 아이디입니다.", "error")
        else:
            user = User(username=username, email=email)
            user.set_password(password)
            if User.query.count() == 0:
                user.is_admin = True
            db.session.add(user)
            db.session.commit()
            session["user_id"] = user.id
            flash("회원가입 완료!", "success")
            return redirect("/")
    return render_template_string(BASE_HTML + """
    {% block content %}
    <div class="max-w-md mx-auto bg-white rounded-xl border p-8">
        <h1 class="text-2xl font-bold mb-6 text-center">회원가입</h1>
        <form method="post" class="space-y-4">
            <input type="text" name="username" placeholder="아이디" required class="w-full border rounded-lg px-4 py-2">
            <input type="email" name="email" placeholder="이메일 (선택)" class="w-full border rounded-lg px-4 py-2">
            <input type="password" name="password" placeholder="비밀번호" required class="w-full border rounded-lg px-4 py-2">
            <button type="submit" class="w-full bg-indigo-600 text-white py-3 rounded-lg">가입하기</button>
        </form>
        <p class="text-center mt-4 text-sm">이미 계정이 있으신가요? <a href="/login" class="text-indigo-600">로그인</a></p>
    </div>
    {% endblock %}
    """, user=None)


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user():
        return redirect("/")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session["user_id"] = user.id
            flash(f"{user.username}님 환영합니다!", "success")
            return redirect("/")
        flash("아이디 또는 비밀번호가 틀렸습니다.", "error")
    return render_template_string(BASE_HTML + """
    {% block content %}
    <div class="max-w-md mx-auto bg-white rounded-xl border p-8">
        <h1 class="text-2xl font-bold mb-6 text-center">로그인</h1>
        <form method="post" class="space-y-4">
            <input type="text" name="username" placeholder="아이디" required class="w-full border rounded-lg px-4 py-2">
            <input type="password" name="password" placeholder="비밀번호" required class="w-full border rounded-lg px-4 py-2">
            <button type="submit" class="w-full bg-indigo-600 text-white py-3 rounded-lg">로그인</button>
        </form>
        <p class="text-center mt-4 text-sm">계정이 없으신가요? <a href="/signup" class="text-indigo-600">회원가입</a></p>
    </div>
    {% endblock %}
    """, user=None)


@app.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("로그아웃되었습니다.", "success")
    return redirect("/")


@app.route("/order/<int:pid>")
@login_required
def create_order(pid):
    product = Product.query.get_or_404(pid)
    user = current_user()
    paid = Order.query.filter_by(user_id=user.id, product_id=product.id, status="paid").first()
    if paid:
        flash("이미 구매한 강의입니다.", "success")
        return redirect("/my-courses")
    order = Order.query.filter_by(user_id=user.id, product_id=product.id, status="pending").first()
    if not order:
        order = Order(user_id=user.id, product_id=product.id, amount=product.price)
        db.session.add(order)
        db.session.commit()
    return render_template_string(BASE_HTML + """
    {% block content %}
    <div class="max-w-lg mx-auto bg-white rounded-xl border p-8">
        <div class="text-center mb-6">
            <div class="text-5xl mb-3">🏦</div>
            <h1 class="text-2xl font-bold">입금 안내</h1>
        </div>
        <div class="bg-indigo-50 rounded-lg p-5 mb-6 space-y-3">
            <div class="flex justify-between"><span class="text-gray-600">강의</span><span class="font-medium">{{ product.title }}</span></div>
            <div class="flex justify-between"><span class="text-gray-600">입금 금액</span><span class="font-bold text-indigo-600 text-lg">{{ "{:,}".format(order.amount) }}원</span></div>
            <hr>
            <div class="flex justify-between"><span class="text-gray-600">은행</span><span class="font-medium">{{ bank_name }}</span></div>
            <div class="flex justify-between"><span class="text-gray-600">계좌번호</span><span class="font-mono font-bold text-lg">{{ bank_account }}</span></div>
            <div class="flex justify-between"><span class="text-gray-600">예금주</span><span class="font-medium">{{ bank_holder }}</span></div>
        </div>
        <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-sm text-yellow-800 mb-6">
            금액을 정확히 입금해 주세요. 확인 후 <strong>내 강의</strong>에서 PDF를 받을 수 있습니다.
        </div>
        <div class="text-center">
            <a href="/my-orders" class="text-indigo-600">주문 내역 보기</a>
            <p class="text-xs text-gray-400 mt-2">주문번호: {{ order.order_id }}</p>
        </div>
    </div>
    {% endblock %}
    """, product=product, order=order, user=user,
       bank_name=BANK_NAME, bank_account=BANK_ACCOUNT, bank_holder=BANK_HOLDER)


@app.route("/my-orders")
@login_required
def my_orders():
    orders = Order.query.filter_by(user_id=session["user_id"]).order_by(Order.created_at.desc()).all()
    return render_template_string(BASE_HTML + """
    {% block content %}
    <h1 class="text-2xl font-bold mb-6">내 주문 내역</h1>
    <div class="space-y-4">
        {% for o in orders %}
        <div class="bg-white rounded-xl border p-5 flex justify-between items-center">
            <div>
                <h3 class="font-semibold">{{ o.product.title }}</h3>
                <p class="text-sm text-gray-500">{{ o.created_at.strftime('%Y-%m-%d %H:%M') }} · {{ "{:,}".format(o.amount) }}원</p>
            </div>
            <span class="px-3 py-1 rounded-full text-sm {{ 'bg-green-100 text-green-700' if o.status == 'paid' else 'bg-yellow-100 text-yellow-700' }}">
                {{ '결제 완료' if o.status == 'paid' else '입금 대기' }}
            </span>
        </div>
        {% else %}
        <p class="text-gray-500">주문 내역이 없습니다.</p>
        {% endfor %}
    </div>
    {% endblock %}
    """, orders=orders, user=current_user())


@app.route("/my-courses")
@login_required
def my_courses():
    orders = Order.query.filter_by(user_id=session["user_id"], status="paid").all()
    return render_template_string(BASE_HTML + """
    {% block content %}
    <h1 class="text-2xl font-bold mb-6">내 강의</h1>
    <div class="space-y-4">
        {% for o in orders %}
        <div class="bg-white rounded-xl border p-5 flex justify-between items-center">
            <div>
                <h3 class="font-semibold text-lg">{{ o.product.title }}</h3>
            </div>
            {% if o.product.pdf_filename %}
                <a href="/download/{{ o.id }}" class="bg-indigo-600 text-white px-5 py-2.5 rounded-lg text-sm">PDF 다운로드</a>
            {% else %}
                <span class="text-sm text-gray-400">PDF 준비 중</span>
            {% endif %}
        </div>
        {% else %}
        <p class="text-gray-500">아직 구매한 강의가 없습니다. <a href="/" class="text-indigo-600">강의 보러가기</a></p>
        {% endfor %}
    </div>
    {% endblock %}
    """, orders=orders, user=current_user())


@app.route("/download/<int:oid>")
@login_required
def download(oid):
    order = Order.query.get_or_404(oid)
    if order.user_id != session["user_id"] or order.status != "paid":
        abort(403)
    if not order.product.pdf_filename:
        flash("PDF가 아직 없습니다.", "error")
        return redirect("/my-courses")
    path = os.path.join(app.config["UPLOAD_FOLDER"], order.product.pdf_filename)
    if not os.path.exists(path):
        flash("파일을 찾을 수 없습니다.", "error")
        return redirect("/my-courses")
    return send_file(path, as_attachment=True)


@app.route("/admin")
@admin_required
def admin():
    orders = Order.query.order_by(Order.created_at.desc()).all()
    products = Product.query.all()
    return render_template_string(BASE_HTML + """
    {% block content %}
    <h1 class="text-2xl font-bold mb-6">관리자</h1>
    <h2 class="font-semibold mb-3">주문 관리</h2>
    <div class="space-y-3 mb-10">
        {% for o in orders %}
        <div class="bg-white rounded-xl border p-4 flex justify-between items-center">
            <div>{{ o.user.username }} - {{ o.product.title }} ({{ "{:,}".format(o.amount) }}원)</div>
            <div class="flex gap-2 items-center">
                <span class="text-sm {{ 'text-green-600' if o.status == 'paid' else 'text-yellow-600' }}">{{ '결제완료' if o.status == 'paid' else '입금대기' }}</span>
                {% if o.status == 'pending' %}
                    <a href="/admin/pay/{{ o.id }}" class="bg-green-600 text-white px-3 py-1 rounded text-sm">결제완료 처리</a>
                {% endif %}
            </div>
        </div>
        {% endfor %}
    </div>
    <h2 class="font-semibold mb-3">상품 관리</h2>
    <a href="/admin/product/new" class="inline-block mb-4 bg-indigo-600 text-white px-4 py-2 rounded-lg text-sm">+ 상품 추가</a>
    <div class="space-y-3">
        {% for p in products %}
        <div class="bg-white rounded-xl border p-4 flex justify-between">
            <span>{{ p.title }} - {{ "{:,}".format(p.price) }}원 {% if p.pdf_filename %}<span class="text-green-600 text-xs">PDF</span>{% endif %}</span>
            <a href="/admin/product/{{ p.id }}" class="text-indigo-600 text-sm">수정</a>
        </div>
        {% endfor %}
    </div>
    {% endblock %}
    """, orders=orders, products=products, user=current_user())


@app.route("/admin/pay/<int:oid>")
@admin_required
def admin_pay(oid):
    order = Order.query.get_or_404(oid)
    if order.status == "pending":
        order.status = "paid"
        order.paid_at = datetime.utcnow()
        db.session.commit()
        flash("결제완료 처리했습니다.", "success")
    return redirect("/admin")


@app.route("/admin/product/new", methods=["GET", "POST"])
@app.route("/admin/product/<int:pid>", methods=["GET", "POST"])
@admin_required
def admin_product(pid=None):
    product = Product.query.get(pid) if pid else None
    if request.method == "POST":
        if not product:
            product = Product()
            db.session.add(product)
        product.title = request.form.get("title", "").strip()
        product.description = request.form.get("description", "")
        product.price = int(request.form.get("price", 0))
        product.is_active = True
        if "pdf" in request.files:
            f = request.files["pdf"]
            if f.filename:
                filename = secure_filename(f"{secrets.token_hex(4)}_{f.filename}")
                f.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))
                product.pdf_filename = filename
        db.session.commit()
        flash("저장되었습니다.", "success")
        return redirect("/admin")
    return render_template_string(BASE_HTML + """
    {% block content %}
    <div class="max-w-lg mx-auto bg-white rounded-xl border p-8">
        <h1 class="text-2xl font-bold mb-6">{{ '상품 수정' if product else '상품 추가' }}</h1>
        <form method="post" enctype="multipart/form-data" class="space-y-4">
            <input type="text" name="title" value="{{ product.title if product else '' }}" placeholder="제목" required class="w-full border rounded-lg px-4 py-2">
            <textarea name="description" rows="5" placeholder="설명" class="w-full border rounded-lg px-4 py-2">{{ product.description if product else '' }}</textarea>
            <input type="number" name="price" value="{{ product.price if product else '' }}" placeholder="가격" required class="w-full border rounded-lg px-4 py-2">
            <input type="file" name="pdf" accept=".pdf" class="w-full">
            <button type="submit" class="w-full bg-indigo-600 text-white py-3 rounded-lg">저장</button>
        </form>
    </div>
    {% endblock %}
    """, product=product, user=current_user())


def init_data():
    with app.app_context():
        db.create_all()
        if Product.query.count() == 0:
            samples = [
                ("유튜브 100만 기법", "유튜브 채널을 100만 구독자까지 성장시키는 실전 기법.", 99000),
                ("1달 300 기법", "단 한 달 만에 결과를 만드는 300가지 실전 기법.", 79000),
                ("엑셀 업무 자동화", "반복되는 엑셀 업무를 자동화하는 실무 테크닉.", 59000),
                ("네이버 블로그 자동화", "네이버 블로그 운영을 자동화해서 트래픽과 수익을 만드는 방법.", 69000),
            ]
            for title, desc, price in samples:
                db.session.add(Product(title=title, description=desc, price=price))
            db.session.commit()
            print("샘플 상품 생성 완료")


if __name__ == "__main__":
    init_data()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
