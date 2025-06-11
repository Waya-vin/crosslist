# app.py - Flask Backend
from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
import os
import sqlite3
import requests

app = Flask(__name__)
CORS(app)

# Free SQLite database
DB_PATH = 'products.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS products
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                 title TEXT, description TEXT, price REAL,
                 category TEXT, images TEXT, status TEXT DEFAULT 'draft')''')
    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# Depop API integration (sandbox)
def connect_to_depop(auth_code):
    """Exchange auth code for access token (sandbox mode)"""
    try:
        response = requests.post(
            'https://sandbox.depop.com/oauth/access_token',
            data={
                'client_id': os.getenv('DEPOP_CLIENT_ID'),
                'client_secret': os.getenv('DEPOP_CLIENT_SECRET'),
                'code': auth_code,
                'grant_type': 'authorization_code',
                'redirect_uri': os.getenv('REDIRECT_URI')
            }
        )
        return response.json().get('access_token')
    except Exception as e:
        print(f"Depop connection error: {e}")
        return None

# Vinted integration (reverse-engineered)
def post_to_vinted(product, cookies):
    """Post to Vinted using their internal API"""
    try:
        response = requests.post(
            'https://www.vinted.co.uk/api/v2/items',
            json={
                "title": product['title'],
                "description": product['description'],
                "price": product['price'],
                "category_id": 5,  # Default category ID
                "photos": product['images'].split(',')
            },
            headers={
                "Cookie": cookies,
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        return response.json()
    except Exception as e:
        print(f"Vinted posting error: {e}")
        return None

# API Endpoints
@app.route('/api/products', methods=['GET', 'POST'])
def products():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    if request.method == 'POST':
        product = request.json
        c.execute('''INSERT INTO products (title, description, price, category, images)
                     VALUES (?, ?, ?, ?, ?)''',
                 (product['title'], product['description'], 
                  product['price'], product['category'], product['images']))
        conn.commit()
        product_id = c.lastrowid
        conn.close()
        return jsonify({"id": product_id}), 201
    
    c.execute("SELECT * FROM products")
    products = [dict(zip([column[0] for column in c.description], row)) 
                for row in c.fetchall()]
    conn.close()
    return jsonify(products)

@app.route('/api/list-depop', methods=['POST'])
def list_depop():
    product_id = request.json['product_id']
    auth_code = request.json['auth_code']
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    product = c.fetchone()
    conn.close()
    
    if not product:
        return jsonify({"error": "Product not found"}), 404
        
    access_token = connect_to_depop(auth_code)
    if not access_token:
        return jsonify({"error": "Depop connection failed"}), 400
    
    # Convert to dict
    product_dict = {
        'id': product[0],
        'title': product[1],
        'description': product[2],
        'price': product[3],
        'category': product[4],
        'images': product[5]
    }
    
    # Post to Depop
    response = requests.post(
        'https://sandbox.depop.com/v1/products',
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "name": product_dict['title'],
            "description": product_dict['description'],
            "price": product_dict['price'],
            "category": product_dict['category']
        }
    )
    
    if response.status_code == 201:
        return jsonify({"success": True, "listing": response.json()})
    return jsonify({"error": "Depop listing failed", "details": response.text}), 400

@app.route('/api/list-vinted', methods=['POST'])
def list_vinted():
    product_id = request.json['product_id']
    cookies = request.json['cookies']  # User's session cookies
    
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM products WHERE id=?", (product_id,))
    product = c.fetchone()
    conn.close()
    
    if not product:
        return jsonify({"error": "Product not found"}), 404
        
    # Convert to dict
    product_dict = {
        'id': product[0],
        'title': product[1],
        'description': product[2],
        'price': product[3],
        'category': product[4],
        'images': product[5]
    }
    
    # Post to Vinted
    response = post_to_vinted(product_dict, cookies)
    
    if response and 'id' in response:
        return jsonify({"success": True, "listing": response})
    return jsonify({"error": "Vinted listing failed"}), 400

# Serve frontend
@app.route('/')
def index():
    return render_template('index.html')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
