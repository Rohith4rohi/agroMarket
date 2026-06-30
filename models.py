# models.py
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    __tablename__ = 'user'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    user_type = db.Column(db.String(20), nullable=False)  # 'farmer', 'buyer', 'admin'
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships with unique backref names
    products = db.relationship('Product', backref='farmer', lazy=True, foreign_keys='Product.farmer_id')
    bids = db.relationship('Bid', backref='bidder', lazy=True, foreign_keys='Bid.buyer_id')
    transactions_as_buyer = db.relationship('Transaction', backref='buyer', lazy=True, foreign_keys='Transaction.buyer_id')
    transactions_as_farmer = db.relationship('Transaction', backref='seller', lazy=True, foreign_keys='Transaction.farmer_id')
    partial_purchases = db.relationship('PartialTransaction', backref='buyer', lazy=True, foreign_keys='PartialTransaction.buyer_id')
    partial_sales = db.relationship('PartialTransaction', backref='seller', lazy=True, foreign_keys='PartialTransaction.farmer_id')
    
    def __repr__(self):
        return f'<User {self.username}>'


class Product(db.Model):
    __tablename__ = 'product'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    total_quantity = db.Column(db.Float, nullable=False)
    available_quantity = db.Column(db.Float, nullable=False, default=0)
    unit = db.Column(db.String(20), nullable=False)
    base_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, nullable=False)
    max_price_limit = db.Column(db.Float, nullable=False, default=1000)
    min_price_limit = db.Column(db.Float, nullable=False, default=10)
    description = db.Column(db.Text, nullable=False)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    auction_end = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='active')  # 'active', 'closed', 'sold', 'partial'
    image_filename = db.Column(db.String(200), nullable=True)
    is_bulk_sale = db.Column(db.Boolean, default=False)
    min_purchase_quantity = db.Column(db.Float, default=0)
    
    # Relationships
    bids = db.relationship('Bid', backref='product', lazy=True, foreign_keys='Bid.product_id')
    transaction = db.relationship('Transaction', backref='product', uselist=False, foreign_keys='Transaction.product_id')
    partial_transactions = db.relationship('PartialTransaction', backref='product', lazy=True, foreign_keys='PartialTransaction.product_id')
    
    def __repr__(self):
        return f'<Product {self.name}>'


class Bid(db.Model):
    __tablename__ = 'bid'
    
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    quantity_requested = db.Column(db.Float, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_winning = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(20), default='active')  # 'active', 'won', 'lost'
    
    def __repr__(self):
        return f'<Bid {self.amount} by User {self.buyer_id}>'


class Transaction(db.Model):
    __tablename__ = 'transaction'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    final_price = db.Column(db.Float, nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    transaction_date = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # 'pending', 'completed', 'cancelled'
    
    def __repr__(self):
        return f'<Transaction {self.id}>'


class PartialTransaction(db.Model):
    __tablename__ = 'partial_transaction'
    
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    farmer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    quantity = db.Column(db.Float, nullable=False)
    price_per_unit = db.Column(db.Float, nullable=False)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='completed')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<PartialTransaction {self.id}>'


class DailyReport(db.Model):
    __tablename__ = 'daily_report'
    
    id = db.Column(db.Integer, primary_key=True)
    report_date = db.Column(db.DateTime, nullable=False)
    total_products_listed = db.Column(db.Integer, default=0)
    total_products_sold = db.Column(db.Integer, default=0)
    total_revenue = db.Column(db.Float, default=0)
    total_buyers = db.Column(db.Integer, default=0)
    total_farmers = db.Column(db.Integer, default=0)
    category_wise_sales = db.Column(db.Text, default='{}')  # JSON string
    top_products = db.Column(db.Text, default='[]')  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DailyReport {self.report_date}>'


class MarketUpdate(db.Model):
    __tablename__ = 'market_update'
    
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(100), nullable=True)
    commodity = db.Column(db.String(100), nullable=True)
    price = db.Column(db.Float, nullable=True)
    trend = db.Column(db.String(20), nullable=True)  # 'up', 'down', 'stable'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<MarketUpdate {self.title}>'


class CategoryPriceLimit(db.Model):
    __tablename__ = 'category_price_limit'
    
    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50), unique=True, nullable=False)
    min_price = db.Column(db.Float, nullable=False)
    max_price = db.Column(db.Float, nullable=False)
    unit = db.Column(db.String(20), default='kg')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<CategoryPriceLimit {self.category}>'