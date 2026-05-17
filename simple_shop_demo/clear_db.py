import sqlite3

conn = sqlite3.connect("shop.db")
conn.execute("DELETE FROM orders")
conn.execute("DELETE FROM products")
try:
    conn.execute("DELETE FROM sqlite_sequence WHERE name IN ('products', 'orders')")
except sqlite3.OperationalError:
    pass
conn.commit()
print("products:", conn.execute("SELECT COUNT(*) FROM products").fetchone()[0])
print("orders:", conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0])
conn.close()
