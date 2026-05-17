from flask import Flask, render_template, request, redirect
import sqlite3
from datetime import datetime

app = Flask(__name__)

DB_NAME = 'shop.db'


def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            price REAL NOT NULL,
            stock INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            total_price REAL NOT NULL,
            create_time TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


@app.route('/')
def index():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM products')
    products = cursor.fetchall()

    conn.close()

    return render_template('index.html', products=products)


@app.route('/add_product', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':
        name = request.form['name']
        price = float(request.form['price'])
        stock = int(request.form['stock'])

        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()

        cursor.execute(
            'INSERT INTO products (name, price, stock) VALUES (?, ?, ?)',
            (name, price, stock)
        )
        product_id = cursor.lastrowid

        conn.commit()
        conn.close()

        if request.headers.get('Accept') == 'application/json':
            return {"id": product_id, "name": name, "price": price, "stock": stock}, 201

        return redirect('/')

    return render_template('add_product.html')


@app.route('/order/<int:product_id>', methods=['GET', 'POST'])
def order(product_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM products WHERE id = ?', (product_id,))
    product = cursor.fetchone()

    if request.method == 'POST':
        quantity = int(request.form['quantity'])

        current_stock = product[3]

        if quantity > current_stock:
            conn.close()
            return '库存不足！'

        new_stock = current_stock - quantity

        cursor.execute(
            'UPDATE products SET stock = ? WHERE id = ?',
            (new_stock, product_id)
        )

        total_price = quantity * product[2]

        cursor.execute(
            'INSERT INTO orders (product_name, quantity, total_price, create_time) VALUES (?, ?, ?, ?)',
            (
                product[1],
                quantity,
                total_price,
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            )
        )

        conn.commit()
        conn.close()

        return redirect('/orders')

    conn.close()

    return render_template('order.html', product=product)


@app.route('/orders')
def orders():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM orders ORDER BY id DESC')
    order_list = cursor.fetchall()

    conn.close()

    return render_template('orders.html', orders=order_list)


if __name__ == '__main__':
    init_db()
    app.run(debug=True)
