# update_database.py
import sqlite3
import os

def update_database():
    """Update existing database with new columns"""
    db_path = 'database.db'
    
    if not os.path.exists(db_path):
        print("Database file not found. Creating new database...")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("Updating database schema...")
    
    # Update Product table
    cursor.execute("PRAGMA table_info(product)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'available_quantity' not in columns:
        print("Adding available_quantity to product...")
        cursor.execute("ALTER TABLE product ADD COLUMN available_quantity FLOAT")
        cursor.execute("UPDATE product SET available_quantity = total_quantity WHERE available_quantity IS NULL")
    
    if 'max_price_limit' not in columns:
        print("Adding max_price_limit to product...")
        cursor.execute("ALTER TABLE product ADD COLUMN max_price_limit FLOAT DEFAULT 1000")
    
    if 'min_price_limit' not in columns:
        print("Adding min_price_limit to product...")
        cursor.execute("ALTER TABLE product ADD COLUMN min_price_limit FLOAT DEFAULT 10")
    
    if 'is_bulk_sale' not in columns:
        print("Adding is_bulk_sale to product...")
        cursor.execute("ALTER TABLE product ADD COLUMN is_bulk_sale BOOLEAN DEFAULT 0")
    
    if 'min_purchase_quantity' not in columns:
        print("Adding min_purchase_quantity to product...")
        cursor.execute("ALTER TABLE product ADD COLUMN min_purchase_quantity FLOAT DEFAULT 0")
    
    # Update Bid table
    cursor.execute("PRAGMA table_info(bid)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'is_winning' not in columns:
        print("Adding is_winning to bid...")
        cursor.execute("ALTER TABLE bid ADD COLUMN is_winning BOOLEAN DEFAULT 0")
    
    if 'status' not in columns:
        print("Adding status to bid...")
        cursor.execute("ALTER TABLE bid ADD COLUMN status VARCHAR(20) DEFAULT 'active'")
    
    if 'quantity_requested' not in columns:
        print("Adding quantity_requested to bid...")
        cursor.execute("ALTER TABLE bid ADD COLUMN quantity_requested FLOAT")
    
    # Update Transaction table
    cursor.execute("PRAGMA table_info(transaction)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'status' not in columns:
        print("Adding status to transaction...")
        cursor.execute("ALTER TABLE transaction ADD COLUMN status VARCHAR(20) DEFAULT 'pending'")
    
    if 'total_amount' not in columns:
        print("Adding total_amount to transaction...")
        cursor.execute("ALTER TABLE transaction ADD COLUMN total_amount FLOAT")
        cursor.execute("UPDATE transaction SET total_amount = final_price * quantity WHERE total_amount IS NULL")
    
    # Update PartialTransaction table
    cursor.execute("PRAGMA table_info(partial_transaction)")
    columns = [column[1] for column in cursor.fetchall()]
    
    if 'created_at' not in columns:
        print("Adding created_at to partial_transaction...")
        cursor.execute("ALTER TABLE partial_transaction ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
    
    # Commit changes
    conn.commit()
    
    # Verify updates
    print("\nVerifying updates...")
    
    # Check Product table
    cursor.execute("PRAGMA table_info(product)")
    product_cols = [column[1] for column in cursor.fetchall()]
    print(f"Product table columns: {', '.join(product_cols)}")
    
    # Check Bid table
    cursor.execute("PRAGMA table_info(bid)")
    bid_cols = [column[1] for column in cursor.fetchall()]
    print(f"Bid table columns: {', '.join(bid_cols)}")
    
    # Check Transaction table
    cursor.execute("PRAGMA table_info(transaction)")
    trans_cols = [column[1] for column in cursor.fetchall()]
    print(f"Transaction table columns: {', '.join(trans_cols)}")
    
    # Check PartialTransaction table
    cursor.execute("PRAGMA table_info(partial_transaction)")
    partial_cols = [column[1] for column in cursor.fetchall()]
    print(f"PartialTransaction table columns: {', '.join(partial_cols)}")
    
    conn.close()
    print("\n✅ Database update completed successfully!")

if __name__ == '__main__':
    update_database()