from flask import Flask, render_template, redirect, url_for, flash, request, jsonify, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_bcrypt import Bcrypt
from models import db, User, Product, Bid, Transaction, DailyReport, MarketUpdate, PartialTransaction, CategoryPriceLimit
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import os
import json
from functools import wraps
import json
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from io import BytesIO
from flask import send_file
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
from market_price_service import market_price_service


app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-production'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize extensions
db.init_app(app)
bcrypt = Bcrypt(app)
socketio = SocketIO(app, cors_allowed_origins="*")
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

# Category price limits configuration
# Update this in app.py (around line 45)
CATEGORY_PRICE_LIMITS = {
    'Vegetables': {'min': 20, 'max': 150, 'unit': 'kg'},
    'Fruits': {'min': 50, 'max': 200, 'unit': 'kg'},
    'Grains': {'min': 30, 'max': 100, 'unit': 'kg'},
    'Pulses': {'min': 60, 'max': 150, 'unit': 'kg'},
    'Spices': {'min': 100, 'max': 500, 'unit': 'kg'},
    'Oilseeds': {'min': 40, 'max': 120, 'unit': 'kg'},
    'Dairy': {'min': 40, 'max': 120, 'unit': 'liter'},
    'Others': {'min': 10, 'max': 1000, 'unit': 'kg'}
}

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.user_type != 'admin':
            flash('Admin access required', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated_function

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Add context processor for current datetime
@app.context_processor
def utility_processor():
    return {
        'now': datetime.now,
        'utcnow': datetime.utcnow,
        'today': datetime.today,
        'category_limits': CATEGORY_PRICE_LIMITS
    }

# Add custom filters
@app.template_filter('is_expired')
def is_expired_filter(auction_end):
    return datetime.now() > auction_end

@app.template_filter('format_datetime')
def format_datetime_filter(value, format='%Y-%m-%d %H:%M'):
    """Format datetime for display"""
    if value is None:
        return ""
    return value.strftime(format)

@app.template_filter('format_date')
def format_date_filter(value, format='%Y-%m-%d'):
    """Format date only"""
    if value is None:
        return ""
    return value.strftime(format)

@app.template_filter('from_json')
def from_json_filter(value):
    """Parse JSON string to Python object"""
    import json
    if not value:
        return {}
    try:
        return json.loads(value)
    except:
        return {}
# Add this to app.py after your existing filters

@app.template_filter('format_datetime')
def format_datetime_filter(value, format='%Y-%m-%d %H:%M'):
    """Format datetime for display"""
    if value is None:
        return ""
    return value.strftime(format)

@app.template_filter('time_remaining')
def time_remaining_filter(auction_end):
    if datetime.now() > auction_end:
        return "Expired"
    
    diff = auction_end - datetime.now()
    hours = diff.seconds // 3600
    minutes = (diff.seconds % 3600) // 60
    
    if diff.days > 0:
        return f"{diff.days}d {hours}h remaining"
    elif hours > 0:
        return f"{hours}h {minutes}m remaining"
    else:
        return f"{minutes}m remaining"

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
# Add after your existing generate_daily_report() function

def generate_daily_pdf_report(report_date=None):
    """Generate a PDF report for daily activities"""
    if report_date is None:
        report_date = datetime.now()
    
    # Set date range for the report day
    start_date = report_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_date = start_date + timedelta(days=1)
    
    # Get data for the report
    products_added = Product.query.filter(
        Product.created_at >= start_date,
        Product.created_at < end_date
    ).all()
    
    # Get completed transactions (products purchased)
    transactions = Transaction.query.filter(
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date < end_date
    ).all()
    
    # Get partial purchases
    partial_purchases = PartialTransaction.query.filter(
        PartialTransaction.created_at >= start_date,
        PartialTransaction.created_at < end_date
    ).all()
    
    # Calculate statistics
    total_products_added = len(products_added)
    total_products_sold = len(transactions)
    total_partial_purchases = len(partial_purchases)
    total_revenue = sum(t.final_price * t.quantity for t in transactions)
    total_partial_revenue = sum(p.total_amount for p in partial_purchases)
    
    # Category breakdown for added products
    category_added = {}
    for product in products_added:
        category_added[product.category] = category_added.get(product.category, 0) + 1
    
    # Category breakdown for purchased products
    category_sold = {}
    for trans in transactions:
        category_sold[trans.product.category] = category_sold.get(trans.product.category, 0) + 1
    
    # Create PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2e7d32'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#1b5e20'),
        spaceAfter=12,
        spaceBefore=20
    )
    
    # Title
    story.append(Paragraph(f"Daily Market Report", title_style))
    story.append(Paragraph(f"{report_date.strftime('%B %d, %Y')}", styles['Heading3']))
    story.append(Spacer(1, 20))
    
    # Summary Section
    story.append(Paragraph("Executive Summary", heading_style))
    
    summary_data = [
        ["Metric", "Value"],
        ["Products Added Today", str(total_products_added)],
        ["Products Sold (Full)", str(total_products_sold)],
        ["Partial Purchases", str(total_partial_purchases)],
        ["Total Revenue from Full Sales", f"₹{total_revenue:,.2f}"],
        ["Total Revenue from Partial Sales", f"₹{total_partial_revenue:,.2f}"],
        ["Combined Total Revenue", f"₹{total_revenue + total_partial_revenue:,.2f}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[200, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e7d32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TOPPADDING', (0, 1), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 20))
    
    # Products Added Section
    story.append(Paragraph("Products Added Today", heading_style))
    
    if products_added:
        products_data = [["ID", "Product Name", "Category", "Quantity", "Base Price", "Farmer"]]
        for product in products_added[:20]:  # Limit to 20 for PDF
            products_data.append([
                str(product.id),
                product.name[:30],
                product.category,
                f"{product.total_quantity} {product.unit}",
                f"₹{product.base_price:,.2f}",
                product.farmer.username[:20]
            ])
        
        if len(products_added) > 20:
            products_data.append(["", f"... and {len(products_added) - 20} more products", "", "", "", ""])
        
        products_table = Table(products_data, colWidths=[40, 120, 70, 70, 70, 80])
        products_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#388e3c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (3, 1), (4, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ]))
        story.append(products_table)
        
        # Category breakdown chart (text-based)
        if category_added:
            story.append(Spacer(1, 12))
            story.append(Paragraph("Category Breakdown (Products Added):", styles['Heading4']))
            for cat, count in sorted(category_added.items(), key=lambda x: x[1], reverse=True):
                story.append(Paragraph(f"• {cat}: {count} product(s)", styles['Normal']))
    else:
        story.append(Paragraph("No products were added today.", styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    # Products Purchased Section
    story.append(Paragraph("Products Purchased Today", heading_style))
    
    if transactions:
        purchased_data = [["Product", "Buyer", "Quantity", "Final Price", "Total Amount"]]
        for trans in transactions[:20]:
            purchased_data.append([
                trans.product.name[:25],
                trans.buyer.username[:15],
                f"{trans.quantity} {trans.product.unit}",
                f"₹{trans.final_price:,.2f}",
                f"₹{trans.final_price * trans.quantity:,.2f}"
            ])
        
        if len(transactions) > 20:
            purchased_data.append(["", f"... and {len(transactions) - 20} more purchases", "", "", ""])
        
        purchased_table = Table(purchased_data, colWidths=[120, 80, 70, 80, 80])
        purchased_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f57c00')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 1), (4, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        story.append(purchased_table)
        
        if category_sold:
            story.append(Spacer(1, 12))
            story.append(Paragraph("Category Breakdown (Products Sold):", styles['Heading4']))
            for cat, count in sorted(category_sold.items(), key=lambda x: x[1], reverse=True):
                story.append(Paragraph(f"• {cat}: {count} sale(s)", styles['Normal']))
    else:
        story.append(Paragraph("No products were purchased today.", styles['Normal']))
    
    story.append(Spacer(1, 20))
    
    # Partial Purchases Section
    if partial_purchases:
        story.append(Paragraph("Partial/Bulk Purchases", heading_style))
        
        partial_data = [["Product", "Buyer", "Quantity", "Price/Unit", "Total"]]
        for purchase in partial_purchases[:15]:
            partial_data.append([
                purchase.product.name[:25],
                purchase.buyer.username[:15],
                f"{purchase.quantity} {purchase.product.unit}",
                f"₹{purchase.price_per_unit:,.2f}",
                f"₹{purchase.total_amount:,.2f}"
            ])
        
        partial_table = Table(partial_data, colWidths=[120, 80, 70, 70, 80])
        partial_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#9c27b0')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('ALIGN', (2, 1), (4, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
        ]))
        story.append(partial_table)
    
    story.append(Spacer(1, 20))
    
    # Footer
    story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#2e7d32')))
    story.append(Spacer(1, 10))
    footer_text = f"Report generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | AgroMarket Platform"
    story.append(Paragraph(footer_text, styles['Normal']))
    
    # Build PDF
    doc.build(story)
    buffer.seek(0)
    
    return buffer

@app.route('/api/market-price/<commodity>')
def get_market_price_api(commodity):
    """API endpoint to get real-time market price for a commodity"""
    market_data = market_price_service.get_market_price(commodity)
    return jsonify(market_data)


@app.route('/api/market-prices/batch')
def get_batch_market_prices():
    """Get market prices for multiple commodities"""
    commodities = request.args.get('commodities', '').split(',')
    if commodities and commodities[0]:
        prices = market_price_service.get_multiple_prices(commodities)
        return jsonify(prices)
    return jsonify({'error': 'No commodities specified'}), 400


@app.route('/api/compare-price/<int:product_id>')
def compare_product_price(product_id):
    """Compare product price with market price"""
    product = Product.query.get_or_404(product_id)
    comparison = market_price_service.compare_with_market(product.current_price, product.category)
    
    if comparison:
        return jsonify({
            'product_id': product.id,
            'product_name': product.name,
            'product_price': product.current_price,
            'market_price': comparison['market_price'],
            'difference': comparison['difference'],
            'percent_diff': comparison['percent_diff'],
            'recommendation': comparison['recommendation'],
            'status': comparison['status'],
            'market_trend': comparison['trend']
        })
    
    return jsonify({'error': 'Could not fetch market data'}), 404


@app.route('/market-insights')
@login_required
def market_insights():
    """Market insights dashboard"""
    # Get market prices for all categories
    categories = ['Vegetables', 'Fruits', 'Grains', 'Pulses', 'Spices', 'Oilseeds', 'Dairy']
    market_prices = {}
    
    for category in categories:
        market_prices[category] = market_price_service.get_price_for_category(category)
    
    # Get trending commodities
    trending_commodities = [
        {'name': 'Tomato', 'price': market_price_service.get_market_price('Tomato')},
        {'name': 'Onion', 'price': market_price_service.get_market_price('Onion')},
        {'name': 'Wheat', 'price': market_price_service.get_market_price('Wheat')},
        {'name': 'Apple', 'price': market_price_service.get_market_price('Apple')},
    ]
    
    return render_template('market_insights.html', 
                         market_prices=market_prices,
                         trending_commodities=trending_commodities)


@app.route('/api/market-trends')
def market_trends():
    """Get market trends data for charts"""
    categories = ['Vegetables', 'Fruits', 'Grains', 'Pulses', 'Spices', 'Oilseeds', 'Dairy']
    trends = []
    
    for category in categories:
        data = market_price_service.get_price_for_category(category)
        trends.append({
            'category': category,
            'price': data['price'],
            'trend': data['trend']
        })
    
    return jsonify(trends)
@app.route('/admin/reports/daily-pdf')
@login_required
@admin_required
def daily_pdf_report():
    """Generate and download daily PDF report"""
    date_str = request.args.get('date', datetime.now().strftime('%Y-%m-%d'))
    try:
        report_date = datetime.strptime(date_str, '%Y-%m-%d')
    except ValueError:
        report_date = datetime.now()
    
    pdf_buffer = generate_daily_pdf_report(report_date)
    
    filename = f"daily_report_{report_date.strftime('%Y%m%d')}.pdf"
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )


@app.route('/admin/reports/summary')
@login_required
@admin_required
def reports_summary():
    """View reports summary page with PDF generation option"""
    # Get date range for filtering
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    
    if start_date_str and end_date_str:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
        reports = DailyReport.query.filter(
            DailyReport.report_date >= start_date,
            DailyReport.report_date < end_date
        ).order_by(DailyReport.report_date.desc()).all()
        selected_start = start_date_str
        selected_end = end_date_str
    else:
        reports = DailyReport.query.order_by(DailyReport.report_date.desc()).limit(30).all()
        selected_start = None
        selected_end = None
    
    # Get daily stats for charts
    daily_stats = []
    for report in reports[:7]:  # Last 7 days
        daily_stats.append({
            'date': report.report_date.strftime('%Y-%m-%d'),
            'products_added': report.total_products_listed,
            'products_sold': report.total_products_sold,
            'revenue': report.total_revenue
        })
    
    return render_template('admin/reports_summary.html', 
                         reports=reports,
                         daily_stats=daily_stats,
                         selected_start=selected_start,
                         selected_end=selected_end)


@app.route('/admin/reports/generate-pdf-range', methods=['POST'])
@login_required
@admin_required
def generate_pdf_range():
    """Generate PDF report for a date range"""
    start_date_str = request.form.get('start_date')
    end_date_str = request.form.get('end_date')
    
    if not start_date_str or not end_date_str:
        flash('Please select both start and end dates', 'danger')
        return redirect(url_for('reports_summary'))
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
    
    # Get data for date range
    products_added = Product.query.filter(
        Product.created_at >= start_date,
        Product.created_at < end_date
    ).all()
    
    transactions = Transaction.query.filter(
        Transaction.transaction_date >= start_date,
        Transaction.transaction_date < end_date
    ).all()
    
    partial_purchases = PartialTransaction.query.filter(
        PartialTransaction.created_at >= start_date,
        PartialTransaction.created_at < end_date
    ).all()
    
    # Create comprehensive PDF
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)
    styles = getSampleStyleSheet()
    story = []
    
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2e7d32'),
        spaceAfter=30,
        alignment=TA_CENTER
    )
    
    story.append(Paragraph(f"Market Report", title_style))
    story.append(Paragraph(f"{start_date.strftime('%B %d, %Y')} - {end_date.strftime('%B %d, %Y')}", styles['Heading3']))
    story.append(Spacer(1, 20))
    
    # Summary
    total_products_added = len(products_added)
    total_products_sold = len(transactions)
    total_revenue = sum(t.final_price * t.quantity for t in transactions)
    total_partial_revenue = sum(p.total_amount for p in partial_purchases)
    
    summary_data = [
        ["Metric", "Value"],
        ["Total Products Added", str(total_products_added)],
        ["Total Products Sold", str(total_products_sold)],
        ["Total Partial Purchases", str(len(partial_purchases))],
        ["Total Revenue from Full Sales", f"₹{total_revenue:,.2f}"],
        ["Total Revenue from Partial Sales", f"₹{total_partial_revenue:,.2f}"],
        ["Combined Total Revenue", f"₹{total_revenue + total_partial_revenue:,.2f}"],
    ]
    
    summary_table = Table(summary_data, colWidths=[200, 150])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2e7d32')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(summary_table)
    
    doc.build(story)
    buffer.seek(0)
    
    filename = f"market_report_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}.pdf"
    return send_file(
        buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=filename
    )
# Routes
@app.route('/')
def index():
    products = Product.query.filter_by(status='active').order_by(Product.created_at.desc()).limit(6).all()
    market_updates = MarketUpdate.query.filter(
        (MarketUpdate.expires_at > datetime.now()) | (MarketUpdate.expires_at == None)
    ).order_by(MarketUpdate.created_at.desc()).limit(5).all()
    return render_template('index.html', products=products, market_updates=market_updates)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        user_type = request.form.get('user_type')
        
        # Check if user exists
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            flash('Username or email already exists', 'danger')
            return redirect(url_for('register'))
        
        # Hash password and create user
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(username=username, email=email, password=hashed_password, user_type=user_type)
        
        try:
            db.session.add(user)
            db.session.commit()
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('An error occurred. Please try again.', 'danger')
            return redirect(url_for('register'))
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        user = User.query.filter_by(username=username).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            if not user.is_active:
                flash('Account is disabled. Contact admin.', 'danger')
                return redirect(url_for('login'))
            login_user(user)
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password', 'danger')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    if current_user.user_type == 'admin':
        return redirect(url_for('admin_dashboard'))
    
    partial_sales = None
    partial_transactions = None
    
    if current_user.user_type == 'farmer':
        products = Product.query.filter_by(farmer_id=current_user.id).order_by(Product.created_at.desc()).all()
        active_bids = Bid.query.join(Product).filter(Product.farmer_id == current_user.id).all()
        partial_sales = PartialTransaction.query.filter_by(farmer_id=current_user.id).all()
    else:  # buyer
        products = Product.query.filter_by(status='active').order_by(Product.created_at.desc()).all()
        active_bids = Bid.query.filter_by(buyer_id=current_user.id).all()
        partial_transactions = PartialTransaction.query.filter_by(buyer_id=current_user.id).all()
    
    return render_template('dashboard.html', 
                         products=products, 
                         active_bids=active_bids,
                         partial_sales=partial_sales,
                         partial_transactions=partial_transactions)
@app.route('/my-products')
@login_required
def my_products():
    """View all products posted by the farmer"""
    if current_user.user_type != 'farmer':
        flash('Access denied. Only farmers can view this page.', 'danger')
        return redirect(url_for('dashboard'))
    
    products = Product.query.filter_by(farmer_id=current_user.id).order_by(Product.created_at.desc()).all()
    
    # Calculate statistics
    total_products = len(products)
    active_products = len([p for p in products if p.status == 'active'])
    sold_products = len([p for p in products if p.status == 'sold' or p.status == 'closed'])
    total_revenue = sum([t.total_amount for t in PartialTransaction.query.filter_by(farmer_id=current_user.id).all()])
    
    # Add transaction revenue
    for product in products:
        if product.transaction:
            total_revenue += product.transaction.final_price * product.transaction.quantity
    
    return render_template('my_products.html', 
                         products=products, 
                         total_products=total_products,
                         active_products=active_products,
                         sold_products=sold_products,
                         total_revenue=total_revenue)

@app.route('/post-product', methods=['GET', 'POST'])
@login_required
def post_product():
    if current_user.user_type != 'farmer':
        flash('Only farmers can post products', 'danger')
        return redirect(url_for('dashboard'))
    
    if request.method == 'POST':
        try:
            # Get form data matching your HTML fields
            name = request.form.get('name')
            category = request.form.get('category')
            
            # Your form uses 'quantity' not 'total_quantity'
            quantity = request.form.get('quantity')
            if not quantity:
                flash('Quantity is required', 'danger')
                return redirect(url_for('post_product'))
            
            total_quantity = float(quantity)
            unit = request.form.get('unit')
            base_price = float(request.form.get('base_price'))
            description = request.form.get('description')
            auction_end_str = request.form.get('auction_end')
            
            # Optional fields from your form
            min_bid_increment = request.form.get('min_bid_increment', 10)
            quality = request.form.get('quality')
            harvest_date = request.form.get('harvest_date')
            location = request.form.get('location')
            
            if not auction_end_str:
                flash('Auction end time is required', 'danger')
                return redirect(url_for('post_product'))
            
            auction_end = datetime.strptime(auction_end_str, '%Y-%m-%dT%H:%M')
            
            # Validate auction end time (must be at least 1 hour from now)
            if auction_end <= datetime.now():
                flash('Auction end time must be in the future', 'danger')
                return redirect(url_for('post_product'))
            
            # Get price limits for category
            price_limits = CATEGORY_PRICE_LIMITS.get(category, {'min': 10, 'max': 1000})
            
            # Validate price against category limits
            if base_price < price_limits['min'] or base_price > price_limits['max']:
                flash(f'Base price must be between ₹{price_limits["min"]} and ₹{price_limits["max"]} for {category}', 'danger')
                return redirect(url_for('post_product'))
            
            # Handle multiple image uploads (store first image as primary)
            image_filename = None
            if 'product_images' in request.files:
                files = request.files.getlist('product_images')
                for file in files:
                    if file and file.filename and allowed_file(file.filename):
                        filename = secure_filename(f"{datetime.now().timestamp()}_{file.filename}")
                        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                        if not image_filename:  # Store only the first image as primary
                            image_filename = filename
                        break  # Only store first image for now (you can modify to store multiple)
            
            # Create product (default: not bulk sale for now)
            product = Product(
                name=name,
                category=category,
                total_quantity=total_quantity,
                available_quantity=total_quantity,
                unit=unit,
                base_price=base_price,
                current_price=base_price,
                max_price_limit=price_limits['max'],
                min_price_limit=price_limits['min'],
                description=description,
                farmer_id=current_user.id,
                auction_end=auction_end,
                image_filename=image_filename,
                is_bulk_sale=False,  # Default to False, you can add a checkbox for this
                min_purchase_quantity=0
            )
            
            db.session.add(product)
            db.session.commit()
            
            # Store additional product details if needed (you can add these fields to Product model)
            # For now, we'll just flash success
            flash('Product posted successfully!', 'success')
            return redirect(url_for('dashboard'))
            
        except ValueError as e:
            flash(f'Invalid input: {str(e)}', 'danger')
            return redirect(url_for('post_product'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error posting product: {str(e)}', 'danger')
            return redirect(url_for('post_product'))
    
    return render_template('post_product.html', category_limits=CATEGORY_PRICE_LIMITS)
@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = Product.query.get_or_404(product_id)
    bids = Bid.query.filter_by(product_id=product_id).order_by(Bid.amount.desc()).all()
    # Check if auction is expired and update status
    if product.status == 'active' and datetime.now() > product.auction_end:
        product.status = 'closed'
        db.session.commit()
    return render_template('product_detail.html', product=product, bids=bids)

@app.route('/place-bid/<int:product_id>', methods=['POST'])
@login_required
def place_bid(product_id):
    if current_user.user_type != 'buyer':
        return jsonify({'error': 'Only buyers can place bids'}), 403
    
    product = Product.query.get_or_404(product_id)
    
    if product.status != 'active':
        return jsonify({'error': 'Auction is closed'}), 400
    
    if datetime.now() > product.auction_end:
        product.status = 'closed'
        db.session.commit()
        return jsonify({'error': 'Auction has ended'}), 400
    
    data = request.get_json()
    bid_amount = float(data.get('amount'))
    
    # Get quantity from request
    quantity_requested = data.get('quantity')
    if quantity_requested:
        quantity_requested = float(quantity_requested)
    else:
        quantity_requested = product.total_quantity
    
    # Validate bid amount against category limits
    if bid_amount < product.min_price_limit:
        return jsonify({'error': f'Minimum bid is ₹{product.min_price_limit}'}), 400
    
    if bid_amount > product.max_price_limit:
        return jsonify({'error': f'Maximum bid limit is ₹{product.max_price_limit} for this category'}), 400
    
    if bid_amount <= product.current_price:
        return jsonify({'error': 'Bid must be higher than current price'}), 400
    
    # Validate quantity for bulk sales or regular sales
    if product.is_bulk_sale:
        if quantity_requested < product.min_purchase_quantity:
            return jsonify({'error': f'Minimum purchase quantity is {product.min_purchase_quantity} {product.unit}'}), 400
        if quantity_requested > product.available_quantity:
            return jsonify({'error': f'Only {product.available_quantity} {product.unit} available'}), 400
    else:
        # For non-bulk sales, quantity must match total available
        if quantity_requested != product.total_quantity:
            return jsonify({'error': f'For this product, you must bid on the full quantity: {product.total_quantity} {product.unit}'}), 400
    
    # Check if buyer already has a higher bid (optional: allow multiple bids)
    existing_bids = Bid.query.filter_by(product_id=product_id, buyer_id=current_user.id).all()
    
    # Create new bid
    bid = Bid(
        amount=bid_amount,
        quantity_requested=quantity_requested,
        product_id=product_id,
        buyer_id=current_user.id,
        is_winning=False  # Will be determined when auction ends
    )
    
    # Update product current price
    product.current_price = bid_amount
    
    try:
        db.session.add(bid)
        db.session.commit()
        
        # Emit real-time update via WebSocket
        socketio.emit('new_bid', {
            'product_id': product_id,
            'bid_amount': bid_amount,
            'quantity': quantity_requested,
            'unit': product.unit,
            'bidder': current_user.username,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }, room=f'product_{product_id}')
        
        return jsonify({'success': True, 'message': f'Bid of ₹{bid_amount} for {quantity_requested} {product.unit} placed successfully!'})
    except Exception as e:
        db.session.rollback()
        print(f"Error placing bid: {str(e)}")
        return jsonify({'error': 'Error placing bid'}), 500

@app.route('/buy-partial/<int:product_id>', methods=['POST'])
@login_required
def buy_partial(product_id):
    if current_user.user_type != 'buyer':
        return jsonify({'error': 'Only buyers can purchase'}), 403
    
    product = Product.query.get_or_404(product_id)
    
    if not product.is_bulk_sale:
        return jsonify({'error': 'Partial purchase not available for this product'}), 400
    
    if product.status != 'active':
        return jsonify({'error': 'Product not available'}), 400
    
    data = request.get_json()
    quantity = float(data.get('quantity'))
    price_per_unit = float(data.get('price'))
    
    if quantity < product.min_purchase_quantity:
        return jsonify({'error': f'Minimum purchase quantity is {product.min_purchase_quantity} {product.unit}'}), 400
    
    if quantity > product.available_quantity:
        return jsonify({'error': f'Only {product.available_quantity} {product.unit} available'}), 400
    
    total_amount = quantity * price_per_unit
    
    # Create partial transaction
    transaction = PartialTransaction(
        product_id=product_id,
        buyer_id=current_user.id,
        farmer_id=product.farmer_id,
        quantity=quantity,
        price_per_unit=price_per_unit,
        total_amount=total_amount,
        status='completed'
    )
    
    # Update available quantity
    product.available_quantity -= quantity
    
    if product.available_quantity <= 0:
        product.status = 'sold'
    elif product.available_quantity < product.total_quantity:
        product.status = 'partial'
    
    try:
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({'success': True, 'message': f'Successfully purchased {quantity} {product.unit}'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': 'Error processing purchase'}), 500

@app.route('/product/<int:product_id>/close', methods=['POST'])
@login_required
def close_auction(product_id):
    product = Product.query.get_or_404(product_id)
    
    if product.farmer_id != current_user.id and current_user.user_type != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    # Stop auction time
    product.auction_end = datetime.now()  # Set to current time to stop
    product.status = 'closed'
    
    # Get winning bid (highest amount)
    winning_bid = Bid.query.filter_by(product_id=product_id).order_by(Bid.amount.desc()).first()
    
    if winning_bid:
        # Determine quantity to be sold
        if winning_bid.quantity_requested:
            quantity_sold = winning_bid.quantity_requested
        else:
            quantity_sold = product.total_quantity
        
        # Calculate total amount
        total_amount = winning_bid.amount * quantity_sold
        
        # Create transaction record
        transaction = Transaction(
            product_id=product_id,
            buyer_id=winning_bid.buyer_id,
            farmer_id=product.farmer_id,
            final_price=winning_bid.amount,
            quantity=quantity_sold,
            total_amount=total_amount,
            status='pending'  # pending, completed, cancelled
        )
        db.session.add(transaction)
        
        # Mark the winning bid
        winning_bid.is_winning = True
        winning_bid.status = 'won'
        
        # Update product available quantity
        if product.is_bulk_sale:
            product.available_quantity -= quantity_sold
            
            # Update product status based on remaining quantity
            if product.available_quantity <= 0:
                product.status = 'sold'
            elif product.available_quantity < product.total_quantity:
                product.status = 'partial'
        else:
            product.status = 'sold'
            product.available_quantity = 0
        
        # Mark all other bids as lost
        other_bids = Bid.query.filter(
            Bid.product_id == product_id,
            Bid.id != winning_bid.id
        ).all()
        for bid in other_bids:
            bid.status = 'lost'
        
        db.session.commit()
        
        # Emit auction closed event with winner info
        socketio.emit('auction_closed', {
            'product_id': product_id,
            'message': f'Auction has been closed. Winner: {winning_bid.buyer.username} with bid of ₹{winning_bid.amount} for {quantity_sold} {product.unit}',
            'winner': winning_bid.buyer.username,
            'winning_bid': winning_bid.amount,
            'quantity': quantity_sold
        }, room=f'product_{product_id}')
        
        return jsonify({
            'success': True, 
            'message': f'Auction closed. Winner: {winning_bid.buyer.username} with bid ₹{winning_bid.amount}'
        })
    else:
        # No bids were placed
        socketio.emit('auction_closed', {
            'product_id': product_id,
            'message': 'Auction closed with no bids'
        }, room=f'product_{product_id}')
        
        return jsonify({'success': True, 'message': 'Auction closed with no bids'})
# Add this function to check and close expired auctions automatically
def check_and_close_expired_auctions():
    """Automatically close auctions that have ended"""
    with app.app_context():
        expired_products = Product.query.filter(
            Product.status == 'active',
            Product.auction_end <= datetime.now()
        ).all()
        
        for product in expired_products:
            print(f"Auto-closing auction for product: {product.name} (ID: {product.id})")
            
            # Close the auction
            product.status = 'closed'
            
            # Get winning bid
            winning_bid = Bid.query.filter_by(product_id=product.id).order_by(Bid.amount.desc()).first()
            
            if winning_bid:
                # Determine quantity to be sold
                if winning_bid.quantity_requested:
                    quantity_sold = winning_bid.quantity_requested
                else:
                    quantity_sold = product.total_quantity
                
                # Create transaction record
                transaction = Transaction(
                    product_id=product.id,
                    buyer_id=winning_bid.buyer_id,
                    farmer_id=product.farmer_id,
                    final_price=winning_bid.amount,
                    quantity=quantity_sold,
                    total_amount=winning_bid.amount * quantity_sold,
                    status='pending'
                )
                db.session.add(transaction)
                
                # Mark winning bid
                winning_bid.is_winning = True
                winning_bid.status = 'won'
                
                # Update product available quantity
                if product.is_bulk_sale:
                    product.available_quantity -= quantity_sold
                    
                    if product.available_quantity <= 0:
                        product.status = 'sold'
                    elif product.available_quantity < product.total_quantity:
                        product.status = 'partial'
                else:
                    product.status = 'sold'
                    product.available_quantity = 0
                
                # Mark other bids as lost
                other_bids = Bid.query.filter(
                    Bid.product_id == product.id,
                    Bid.id != winning_bid.id
                ).all()
                for bid in other_bids:
                    bid.status = 'lost'
            
            db.session.commit()
            
            # Send socket notification
            socketio.emit('auction_closed', {
                'product_id': product.id,
                'message': f'Auction has ended automatically. Winner: {winning_bid.buyer.username if winning_bid else "No bids"}',
                'winner': winning_bid.buyer.username if winning_bid else None,
                'winning_bid': winning_bid.amount if winning_bid else 0
            }, room=f'product_{product.id}')

# Schedule the auction checker to run periodically
import threading
import time

def start_auction_checker():
    """Start background thread to check expired auctions every minute"""
    def check_loop():
        while True:
            try:
                check_and_close_expired_auctions()
            except Exception as e:
                print(f"Error in auction checker: {str(e)}")
            time.sleep(60)  # Check every minute
    
    thread = threading.Thread(target=check_loop, daemon=True)
    thread.start()



@app.route('/admin')
@login_required
@admin_required
def admin_dashboard():
    # Statistics
    total_users = User.query.count()
    total_farmers = User.query.filter_by(user_type='farmer').count()
    total_buyers = User.query.filter_by(user_type='buyer').count()
    total_products = Product.query.count()
    active_products = Product.query.filter_by(status='active').count()
    total_transactions = Transaction.query.count()
    total_revenue = db.session.query(db.func.sum(Transaction.final_price * Transaction.quantity)).scalar() or 0
    
    # Recent activities
    recent_products = Product.query.order_by(Product.created_at.desc()).limit(5).all()
    recent_transactions = Transaction.query.order_by(Transaction.transaction_date.desc()).limit(5).all()
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    # Daily report
    today_report = DailyReport.query.filter(
        db.func.date(DailyReport.report_date) == datetime.now().date()
    ).first()
    
    if not today_report:
        generate_daily_report()
        today_report = DailyReport.query.filter(
            db.func.date(DailyReport.report_date) == datetime.now().date()
        ).first()
    
    return render_template('admin/dashboard.html', 
                         total_users=total_users, total_farmers=total_farmers,
                         total_buyers=total_buyers, total_products=total_products,
                         active_products=active_products, total_transactions=total_transactions,
                         total_revenue=total_revenue, recent_products=recent_products,
                         recent_transactions=recent_transactions, recent_users=recent_users,
                         today_report=today_report)

@app.route('/admin/users')
@login_required
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin/users.html', users=users)

@app.route('/admin/users/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_user_status(user_id):
    user = User.query.get_or_404(user_id)
    if user.id == current_user.id:
        return jsonify({'error': 'Cannot disable yourself'}), 400
    user.is_active = not user.is_active
    db.session.commit()
    return jsonify({'success': True, 'is_active': user.is_active})

@app.route('/admin/market-updates', methods=['GET', 'POST'])
@login_required
@admin_required
def admin_market_updates():
    if request.method == 'POST':
        title = request.form.get('title')
        content = request.form.get('content')
        location = request.form.get('location')
        commodity = request.form.get('commodity')
        price = float(request.form.get('price')) if request.form.get('price') else None
        trend = request.form.get('trend')
        expires_days = int(request.form.get('expires_days', 7))
        
        market_update = MarketUpdate(
            title=title,
            content=content,
            location=location,
            commodity=commodity,
            price=price,
            trend=trend,
            expires_at=datetime.now() + timedelta(days=expires_days)
        )
        
        db.session.add(market_update)
        db.session.commit()
        flash('Market update posted successfully', 'success')
        return redirect(url_for('admin_market_updates'))
    
    updates = MarketUpdate.query.order_by(MarketUpdate.created_at.desc()).all()
    return render_template('admin/market_updates.html', updates=updates)

@app.route('/admin/reports')
@login_required
@admin_required
def admin_reports():
    reports = DailyReport.query.order_by(DailyReport.report_date.desc()).all()
    return render_template('admin/reports.html', reports=reports)

@app.route('/admin/generate-report', methods=['POST'])
@login_required
@admin_required
def generate_report():
    generate_daily_report()
    flash('Daily report generated successfully', 'success')
    return redirect(url_for('admin_reports'))

@app.route('/api/market-updates')
def get_market_updates():
    updates = MarketUpdate.query.filter(
        (MarketUpdate.expires_at > datetime.now()) | (MarketUpdate.expires_at == None)
    ).order_by(MarketUpdate.created_at.desc()).limit(10).all()
    
    return jsonify([{
        'id': u.id,
        'title': u.title,
        'content': u.content,
        'location': u.location,
        'commodity': u.commodity,
        'price': u.price,
        'trend': u.trend,
        'created_at': u.created_at.strftime('%Y-%m-%d %H:%M')
    } for u in updates])

@app.route('/api/search')
def search_products():
    query = request.args.get('q', '')
    products = Product.query.filter(
        Product.status == 'active',
        (Product.name.contains(query) | Product.description.contains(query))
    ).limit(20).all()
    
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description,
        'quantity': p.total_quantity,
        'available_quantity': p.available_quantity,
        'unit': p.unit,
        'current_price': p.current_price,
        'farmer': p.farmer.username,
        'image': p.image_filename
    } for p in products])

def generate_daily_report():
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    
    # Get today's transactions
    transactions = Transaction.query.filter(
        Transaction.transaction_date >= today,
        Transaction.transaction_date < tomorrow
    ).all()
    
    # Calculate stats
    total_products_sold = len(transactions)
    total_revenue = sum(t.final_price * t.quantity for t in transactions)
    
    # Category wise sales
    category_sales = {}
    for trans in transactions:
        category = trans.product.category
        category_sales[category] = category_sales.get(category, 0) + (trans.final_price * trans.quantity)
    
    # Top products
    product_sales = {}
    for trans in transactions:
        product_sales[trans.product.name] = product_sales.get(trans.product.name, 0) + (trans.final_price * trans.quantity)
    
    top_products = sorted(product_sales.items(), key=lambda x: x[1], reverse=True)[:5]
    
    report = DailyReport(
        report_date=datetime.now(),
        total_products_listed=Product.query.filter(Product.created_at >= today, Product.created_at < tomorrow).count(),
        total_products_sold=total_products_sold,
        total_revenue=total_revenue,
        total_buyers=len(set(t.buyer_id for t in transactions)),
        total_farmers=len(set(t.farmer_id for t in transactions)),
        category_wise_sales=json.dumps(category_sales),
        top_products=json.dumps([{'name': name, 'revenue': revenue} for name, revenue in top_products])
    )
    
    db.session.add(report)
    db.session.commit()

# SocketIO events
@socketio.on('join_product')
def handle_join_product(data):
    product_id = data['product_id']
    join_room(f'product_{product_id}')

@socketio.on('leave_product')
def handle_leave_product(data):
    product_id = data['product_id']
    leave_room(f'product_{product_id}')

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        # Create admin user if not exists
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@agromarket.com',
                password=bcrypt.generate_password_hash('admin123').decode('utf-8'),
                user_type='admin',
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            print("Admin user created - Username: admin, Password: admin123")
    # Start the auction checker when the app starts
    # Add this line before socketio.run(app, debug=True)
    start_auction_checker()
    socketio.run(app, 
                host="0.0.0.0",
                port=int(os.environ.get("PORT", 5000)),
                debug=False)