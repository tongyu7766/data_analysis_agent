"""Generate sample_data.csv — 200 rows of e-commerce sales data."""

import csv
import random
from datetime import date, timedelta

random.seed(42)

PRODUCTS = {
    "Electronics": {
        "items": ["Laptop", "Headphones", "Tablet", "Smartwatch"],
        "price_range": (50, 1500),
    },
    "Clothing": {
        "items": ["T-Shirt", "Jeans", "Jacket", "Sneakers", "Dress"],
        "price_range": (20, 200),
    },
    "Food": {
        "items": ["Coffee Beans", "Chocolate Box", "Olive Oil", "Tea Set"],
        "price_range": (5, 80),
    },
    "Books": {
        "items": ["Novel", "Cookbook", "Biography", "Textbook"],
        "price_range": (10, 120),
    },
    "Home": {
        "items": ["Desk Lamp", "Cushion", "Blender", "Vacuum Cleaner", "Cookware Set"],
        "price_range": (15, 400),
    },
}

REGIONS = ["North", "East", "South", "Southwest", "Northwest"]
PAYMENT_METHODS = ["WeChat Pay", "Alipay", "Credit Card"]

start = date(2024, 1, 1)

rows = []
for i in range(1, 201):
    category = random.choice(list(PRODUCTS))
    spec = PRODUCTS[category]
    product = random.choice(spec["items"])
    quantity = random.randint(1, 10)
    lo, hi = spec["price_range"]
    unit_price = round(random.uniform(lo, hi), 2)
    rows.append(
        {
            "order_id": f"ORD-{i:04d}",
            "date": (start + timedelta(days=random.randint(0, 365))).isoformat(),
            "product_category": category,
            "product_name": product,
            "quantity": quantity,
            "unit_price": unit_price,
            "total_amount": round(quantity * unit_price, 2),
            "customer_region": random.choice(REGIONS),
            "payment_method": random.choice(PAYMENT_METHODS),
            "is_returned": random.random() < 0.08,
        }
    )

with open("sample_data.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote sample_data.csv with {len(rows)} rows")
