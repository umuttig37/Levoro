
from app import app
from models.order import order_model
import json

with app.app_context():
    # Force fresh fetch
    print("Fetching orders...")
    orders, total = order_model.get_orders_with_driver_info_paginated(page=1, per_page=10)
    
    print(f"Found {total} total orders. Inspecting first 5:")
    for order in orders[:5]:
        c_name = order.get('customer_name')
        u_name = order.get('user_name')
        print(f"Order #{order.get('id')}:")
        print(f"  customer_name raw: {repr(c_name)}")
        print(f"  user_name raw:     {repr(u_name)}")
        print("-" * 20)
