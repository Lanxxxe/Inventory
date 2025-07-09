from flask import Flask, render_template, request, jsonify, redirect, url_for
import sqlite3
from datetime import datetime
import os
import base64
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'alskdlasjda02391023'

# File upload configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Create upload directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database initialization
def init_db():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    # Create inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            brand_name TEXT NOT NULL,
            product_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            supplier TEXT NOT NULL,
            image_data TEXT,
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create returns table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS returns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER,
            product_name TEXT NOT NULL,
            quantity_returned INTEGER NOT NULL,
            reason TEXT NOT NULL,
            return_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY (product_id) REFERENCES inventory (id)
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def dashboard():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    
    # Get dashboard statistics
    cursor.execute('SELECT COUNT(*) FROM inventory')
    total_products = cursor.fetchone()[0]
    
    cursor.execute('SELECT SUM(quantity) FROM inventory')
    total_stock = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT SUM(quantity * price) FROM inventory')
    total_value = cursor.fetchone()[0] or 0
    
    cursor.execute('SELECT COUNT(*) FROM returns WHERE status = "Pending"')
    pending_returns = cursor.fetchone()[0]
    
    # Get low stock items (quantity < 20)
    cursor.execute('SELECT product_name, quantity FROM inventory WHERE quantity < 20 ORDER BY quantity ASC LIMIT 5')
    low_stock_items = cursor.fetchall()
    
    # Get recent activity (last 5 added items)
    cursor.execute('SELECT product_name, date_added FROM inventory ORDER BY date_added DESC LIMIT 5')
    recent_items = cursor.fetchall()
    
    # Get category distribution
    cursor.execute('SELECT brand_name, COUNT(*) FROM inventory GROUP BY brand_name')
    brand_data = cursor.fetchall()
    
    conn.close()
    
    return render_template('dashboard.html', 
                         total_products=total_products,
                         total_stock=total_stock,
                         total_value=total_value,
                         pending_returns=pending_returns,
                         low_stock_items=low_stock_items,
                         recent_items=recent_items,
                         brand_data=brand_data)

@app.route('/inventory')
def inventory():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventory ORDER BY date_added DESC')
    items = cursor.fetchall()
    conn.close()
    return render_template('inventory.html', items=items)

@app.route('/returns')
def returns():
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM returns ORDER BY return_date DESC')
    returns_data = cursor.fetchall()
    
    # Get inventory items for the return form
    cursor.execute('SELECT id, product_name FROM inventory ORDER BY product_name')
    inventory_items = cursor.fetchall()
    
    conn.close()
    return render_template('returns.html', returns=returns_data, inventory_items=inventory_items)

# API Routes for CRUD operations
@app.route('/api/inventory', methods=['POST'])
def add_inventory():
    try:
        # Handle form data instead of JSON for file uploads
        product_name = request.form.get('product_name')
        brand_name = request.form.get('brand_name')
        product_type = request.form.get('product_type')
        quantity = int(request.form.get('quantity'))
        price = float(request.form.get('price'))
        supplier = request.form.get('supplier')
        
        image_data = None
        
        # Handle file upload
        if 'product_image' in request.files:
            file = request.files['product_image']
            if file and file.filename != '' and allowed_file(file.filename):
                # Check file size
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_FILE_SIZE:
                    return jsonify({'success': False, 'message': 'File size too large. Maximum 5MB allowed.'})
                
                # Convert image to base64
                image_data = base64.b64encode(file.read()).decode('utf-8')
        
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO inventory (product_name, brand_name, product_type, quantity, price, supplier, image_data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (product_name, brand_name, product_type, quantity, price, supplier, image_data))

        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Product added successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/inventory/<int:item_id>', methods=['PUT'])
def update_inventory(item_id):
    try:
        product_name = request.form.get('product_name')
        brand_name = request.form.get('brand_name')
        product_type = request.form.get('product_type')
        quantity = int(request.form.get('quantity'))
        price = float(request.form.get('price'))
        supplier = request.form.get('supplier')
        
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        # Check if new image is uploaded
        image_data = None
        update_image = False
        
        if 'product_image' in request.files:
            file = request.files['product_image']
            if file and file.filename != '' and allowed_file(file.filename):
                # Check file size
                file.seek(0, os.SEEK_END)
                file_size = file.tell()
                file.seek(0)
                
                if file_size > MAX_FILE_SIZE:
                    return jsonify({'success': False, 'message': 'File size too large. Maximum 5MB allowed.'})
                
                # Convert image to base64
                image_data = base64.b64encode(file.read()).decode('utf-8')
                update_image = True
        
        if update_image:
            cursor.execute('''
                UPDATE inventory 
                SET product_name=?, brand_name=?, product_type=?, quantity=?, price=?, supplier=?, image_data=?, last_updated=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (product_name, brand_name, product_type, quantity, price, supplier, image_data, item_id))
        else:
            cursor.execute('''
                UPDATE inventory 
                SET product_name=?, brand_name=?, product_type=?, quantity=?, price=?, supplier=?, last_updated=CURRENT_TIMESTAMP
                WHERE id=?
            ''', (product_name, brand_name, product_type, quantity, price, supplier, item_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Product updated successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/inventory/<int:item_id>', methods=['DELETE'])
def delete_inventory(item_id):
    try:
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM inventory WHERE id=?', (item_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Product deleted successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/returns', methods=['POST'])
def add_return():
    try:
        data = request.json
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO returns (product_id, product_name, quantity_returned, reason)
            VALUES (?, ?, ?, ?)
        ''', (data['product_id'], data['product_name'], data['quantity_returned'], data['reason']))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Return request added successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/returns/<int:return_id>/status', methods=['PUT'])
def update_return_status(return_id):
    try:
        data = request.json
        conn = sqlite3.connect('inventory.db')
        cursor = conn.cursor()
        
        cursor.execute('UPDATE returns SET status=? WHERE id=?', (data['status'], return_id))
        
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Return status updated successfully!'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/inventory/<int:item_id>')
def get_inventory_item(item_id):
    conn = sqlite3.connect('inventory.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM inventory WHERE id=?', (item_id,))
    item = cursor.fetchone()
    conn.close()
    
    if item:
        return jsonify({
            'id': item[0],
            'product_name': item[1],
            'brand_name': item[2],
            'product_type': item[3],
            'quantity': item[4],
            'price': item[5],
            'supplier': item[6],
            'image_data': item[7]
        })
    return jsonify({'error': 'Item not found'}), 404

if __name__ == '__main__':
    app.run()
