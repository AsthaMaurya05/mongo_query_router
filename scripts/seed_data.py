

import itertools
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from itertools import accumulate

from bson import ObjectId
from faker import Faker
from pymongo.errors import BulkWriteError

from app.db import get_db

# ---------------------------------------------------------------------------
# Settings (change these numbers to scale the dataset up or down)
# ---------------------------------------------------------------------------
SEED = 42                       # same seed -> same data every run
N_USERS = 2000
N_ORDERS = 50000
N_REVIEWS = 5000
BATCH_SIZE = 5000               # documents per insert_many call

ORDERS_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
ORDERS_END = datetime(2026, 10, 15, 23, 59, 59, tzinfo=timezone.utc)
USERS_JOIN_START = datetime(2025, 1, 1, tzinfo=timezone.utc)
USERS_JOIN_END = datetime(2025, 12, 31, tzinfo=timezone.utc)   # all users join before orders start

# The planted story: in September, Electronics gets picked less often.
STORY_MONTH = 9
STORY_CATEGORY = "Electronics"
STORY_FACTOR = 0.6

COLLECTIONS = ["reviews", "orders", "products", "users", "categories"]

CITIES = [
    "Delhi", "Mumbai", "Bengaluru", "Hyderabad", "Chennai", "Pune",
    "Kolkata", "Jaipur", "Chandigarh", "Ahmedabad", "Lucknow", "Indore",
]

SUFFIXES = ["Classic", "Premium", "Select", "Deluxe", "Essential", "Plus", "Lite", "Pro"]

# weight = how popular the category is; n_products must add up to 200
CATEGORY_CONFIG = [
    {"name": "Electronics", "price": (500, 15000), "weight": 30, "n_products": 40,
     "nouns": ["Wireless Mouse", "Bluetooth Speaker", "Power Bank", "USB-C Cable", "Smart Watch",
               "Earbuds", "Webcam", "Keyboard", "Phone Charger", "LED Monitor"]},
    {"name": "Home & Kitchen", "price": (200, 5000), "weight": 18, "n_products": 30,
     "nouns": ["Mixer Grinder", "Non-stick Pan", "Water Bottle", "Dinner Set", "Air Fryer",
               "Storage Jar Set", "Bedsheet", "Table Lamp", "Cutlery Set", "Vacuum Cleaner"]},
    {"name": "Books", "price": (100, 800), "weight": 12, "n_products": 25,
     "nouns": ["Python Programming", "Data Structures", "Machine Learning Basics", "Indian History",
               "Startup Stories", "Productivity Guide", "Mystery Novel", "Cookbook",
               "Poetry Collection", "Science Encyclopedia"]},
    {"name": "Fashion", "price": (300, 3000), "weight": 14, "n_products": 30,
     "nouns": ["Cotton T-Shirt", "Denim Jeans", "Running Shoes", "Backpack", "Hoodie",
               "Sunglasses", "Wrist Watch", "Kurta", "Sneakers", "Jacket"]},
    {"name": "Sports & Fitness", "price": (300, 6000), "weight": 8, "n_products": 20,
     "nouns": ["Yoga Mat", "Dumbbell Set", "Cricket Bat", "Football", "Skipping Rope",
               "Resistance Bands", "Badminton Racket", "Gym Gloves", "Protein Shaker", "Fitness Tracker"]},
    {"name": "Beauty & Personal Care", "price": (150, 2500), "weight": 8, "n_products": 20,
     "nouns": ["Face Wash", "Moisturizer", "Shampoo", "Sunscreen", "Hair Oil",
               "Body Lotion", "Perfume", "Lip Balm", "Beard Trimmer", "Face Serum"]},
    {"name": "Toys & Games", "price": (150, 2500), "weight": 6, "n_products": 20,
     "nouns": ["Board Game", "Puzzle Set", "RC Car", "Building Blocks", "Doll House",
               "Chess Set", "Art Kit", "Plush Toy", "Card Game", "Science Kit"]},
    {"name": "Grocery", "price": (50, 800), "weight": 4, "n_products": 15,
     "nouns": ["Basmati Rice", "Olive Oil", "Green Tea", "Almonds", "Peanut Butter",
               "Oats", "Honey", "Masala Mix", "Dark Chocolate", "Coffee Powder"]},
]

# Rating weights for [1, 2, 3, 4, 5] stars, depending on how good a product is
RATING_WEIGHTS = {
    "good":    [2, 3, 10, 40, 45],
    "average": [5, 10, 30, 35, 20],
    "poor":    [25, 30, 25, 15, 5],
}

COMMENTS = {
    1: ["Very disappointed", "Stopped working quickly", "Not as described"],
    2: ["Below expectations", "Quality could be better", "Not worth the price"],
    3: ["It is okay", "Average product", "Does the job"],
    4: ["Good value for money", "Works well", "Happy with this purchase"],
    5: ["Excellent quality", "Highly recommended", "Exceeded my expectations"],
}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def random_datetime(start, end):
    """Random moment between start and end (both timezone-aware datetimes)."""
    span = int((end - start).total_seconds())
    return start + timedelta(seconds=random.randint(0, span))


def insert_in_batches(collection, docs):
    """insert_many in chunks. ordered=False lets MongoDB keep going if one doc fails."""
    for i in range(0, len(docs), BATCH_SIZE):
        collection.insert_many(docs[i:i + BATCH_SIZE], ordered=False)
    return len(docs)


def pick_status(created_at):
    """Old orders are finished (delivered or cancelled); only recent ones can be in progress."""
    age_days = (ORDERS_END - created_at).days
    if age_days > 14:
        return random.choices(["delivered", "cancelled"], weights=[85, 15])[0]
    return random.choices(["delivered", "shipped", "placed", "cancelled"],
                          weights=[35, 30, 25, 10])[0]


# ---------------------------------------------------------------------------
# One function per collection
# We create the ObjectIds ourselves so other collections can reference them.
# ---------------------------------------------------------------------------
def make_categories(db):
    docs = [{"_id": ObjectId(), "name": cfg["name"]} for cfg in CATEGORY_CONFIG]
    db.categories.insert_many(docs)
    return docs


def make_users(db, fake):
    docs = []
    for _ in range(N_USERS):
        docs.append({
            "_id": ObjectId(),
            "name": fake.name(),
            "email": fake.unique.email(),
            "city": random.choice(CITIES),
            "joined_at": random_datetime(USERS_JOIN_START, USERS_JOIN_END),
        })
    insert_in_batches(db.users, docs)
    return docs


def make_products(db, categories):
    """Returns (product docs, list of category names aligned with the product docs)."""
    docs = []
    category_names = []
    for cfg, category in zip(CATEGORY_CONFIG, categories):
        combos = [f"{noun} {suffix}" for noun, suffix in itertools.product(cfg["nouns"], SUFFIXES)]
        random.shuffle(combos)
        low, high = cfg["price"]
        for name in combos[:cfg["n_products"]]:
            docs.append({
                "_id": ObjectId(),
                "name": name,
                "category_id": category["_id"],
                "price": float(random.randint(low, high)),
                "stock": random.randint(20, 500),
                "tags": [cfg["name"].lower().replace(" & ", "-").replace(" ", "-"),
                         name.split()[-1].lower()],
            })
            category_names.append(cfg["name"])

    # Make 12 products low on stock so the low_stock_alert pipeline finds something
    for doc in random.sample(docs, 12):
        doc["stock"] = random.randint(0, 9)

    insert_in_batches(db.products, docs)
    return docs, category_names


def build_product_weights(products, category_names):
    """
    How likely each product is to be picked for an order item.
    weight = category weight x product popularity / total popularity of its category,
    so each category's total share matches CATEGORY_CONFIG.
    Returns two cumulative-weight lists: normal months, and the story month.
    """
    cat_weight = {cfg["name"]: cfg["weight"] for cfg in CATEGORY_CONFIG}
    popularity = [random.lognormvariate(0, 0.8) for _ in products]

    pop_total = {}
    for pop, cat in zip(popularity, category_names):
        pop_total[cat] = pop_total.get(cat, 0) + pop

    normal = [cat_weight[cat] * pop / pop_total[cat] for pop, cat in zip(popularity, category_names)]
    story = [w * STORY_FACTOR if cat == STORY_CATEGORY else w for w, cat in zip(normal, category_names)]
    return list(accumulate(normal)), list(accumulate(story))


def make_orders(db, users, products, category_names):
    normal_cum, story_cum = build_product_weights(products, category_names)

    # A few heavy buyers, many light ones (lognormal gives a long tail)
    user_cum = list(accumulate(random.lognormvariate(0, 1.0) for _ in users))
    chosen_users = random.choices(users, cum_weights=user_cum, k=N_ORDERS)

    docs = []
    for user in chosen_users:
        created_at = random_datetime(ORDERS_START, ORDERS_END)
        cum = story_cum if created_at.month == STORY_MONTH else normal_cum

        n_items = random.choices([1, 2, 3, 4, 5], weights=[40, 30, 15, 10, 5])[0]
        picks = random.choices(products, cum_weights=cum, k=n_items)

        items = {}   # product _id -> item, so the same product is not listed twice
        for product in picks:
            qty = random.choices([1, 2, 3], weights=[70, 22, 8])[0]
            if product["_id"] in items:
                items[product["_id"]]["qty"] += qty
            else:
                items[product["_id"]] = {
                    "product_id": product["_id"],
                    "name": product["name"],          # snapshot at purchase time
                    "price": product["price"],        # snapshot at purchase time
                    "qty": qty,
                }
        item_list = list(items.values())

        docs.append({
            "_id": ObjectId(),
            "user_id": user["_id"],
            "status": pick_status(created_at),
            "created_at": created_at,
            "items": item_list,
            "total": round(sum(i["price"] * i["qty"] for i in item_list), 2),
        })

    docs.sort(key=lambda d: d["created_at"])
    insert_in_batches(db.orders, docs)
    return docs


def make_reviews(db, orders):
    """Reviews come from real purchases: a user can only review what they bought in a delivered order."""
    product_quality = {}   # product _id -> "good" / "average" / "poor"
    candidates = []
    seen = set()

    for order in orders:
        if order["status"] != "delivered":
            continue
        for item in order["items"]:
            if random.random() >= 0.10:
                continue
            key = (order["user_id"], item["product_id"])
            if key in seen:               # one review per user per product
                continue
            seen.add(key)
            candidates.append((order, item))

    random.shuffle(candidates)
    docs = []
    for order, item in candidates[:N_REVIEWS]:
        pid = item["product_id"]
        if pid not in product_quality:
            product_quality[pid] = random.choices(["good", "average", "poor"], weights=[60, 30, 10])[0]
        rating = random.choices([1, 2, 3, 4, 5], weights=RATING_WEIGHTS[product_quality[pid]])[0]
        created_at = order["created_at"] + timedelta(days=random.randint(1, 14), hours=random.randint(0, 23))
        docs.append({
            "_id": ObjectId(),
            "user_id": order["user_id"],
            "product_id": pid,
            "rating": rating,
            "comment": random.choice(COMMENTS[rating]),
            "created_at": min(created_at, ORDERS_END),
        })

    insert_in_batches(db.reviews, docs)
    return docs


# ---------------------------------------------------------------------------
# Sanity report: proves the data is correct and the planted story is visible
# ---------------------------------------------------------------------------
def print_report(db):
    print("\n=== Document counts ===")
    for name in ["users", "categories", "products", "orders", "reviews"]:
        print(f"{name:<12}{db[name].count_documents({}):>8,}")

    print("\n=== Spot check: does one order's total match its items? ===")
    order = db.orders.find_one()
    recomputed = round(sum(i["price"] * i["qty"] for i in order["items"]), 2)
    print(f"stored total = {order['total']}, recomputed = {recomputed}, "
          f"{'OK' if order['total'] == recomputed else 'MISMATCH'}")

    print("\n=== Orders by status ===")
    for row in db.orders.aggregate([
        {"$group": {"_id": "$status", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]):
        print(f"{row['_id']:<12}{row['count']:>8,}")

    print("\n=== Delivered revenue by month (October is only half a month) ===")
    rows = list(db.orders.aggregate([
        {"$match": {"status": "delivered"}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                    "revenue": {"$sum": "$total"}}},
        {"$sort": {"_id": 1}},
    ]))
    top = max(r["revenue"] for r in rows)
    for r in rows:
        bar = "#" * int(r["revenue"] / top * 40)
        print(f"{r['_id']}  {r['revenue']:>14,.0f}  {bar}")

    print("\n=== Electronics revenue by month (the planted September dip) ===")
    electronics_id = db.categories.find_one({"name": STORY_CATEGORY})["_id"]
    rows = list(db.orders.aggregate([
        {"$match": {"status": "delivered"}},
        {"$unwind": "$items"},
        {"$lookup": {"from": "products", "localField": "items.product_id",
                     "foreignField": "_id", "as": "product"}},
        {"$unwind": "$product"},
        {"$match": {"product.category_id": electronics_id}},
        {"$group": {"_id": {"$dateToString": {"format": "%Y-%m", "date": "$created_at"}},
                    "revenue": {"$sum": {"$multiply": ["$items.price", "$items.qty"]}}}},
        {"$sort": {"_id": 1}},
    ]))
    top = max(r["revenue"] for r in rows)
    for r in rows:
        bar = "#" * int(r["revenue"] / top * 40)
        print(f"{r['_id']}  {r['revenue']:>14,.0f}  {bar}")


# ---------------------------------------------------------------------------
def main():
    started = time.perf_counter()
    random.seed(SEED)
    Faker.seed(SEED)
    fake = Faker("en_IN")
    db = get_db()

    print("Clearing old data (validators are kept)...")
    for name in COLLECTIONS:
        db[name].delete_many({})

    categories = make_categories(db)
    print(f"categories inserted: {len(categories)}")

    users = make_users(db, fake)
    print(f"users inserted:      {len(users):,}")

    products, category_names = make_products(db, categories)
    print(f"products inserted:   {len(products)}")

    orders = make_orders(db, users, products, category_names)
    print(f"orders inserted:     {len(orders):,}")

    reviews = make_reviews(db, orders)
    print(f"reviews inserted:    {len(reviews):,}")

    print_report(db)
    print(f"\nDone in {time.perf_counter() - started:.1f} seconds.")


if __name__ == "__main__":
    try:
        main()
    except BulkWriteError as error:
        # Raised when a document breaks a $jsonSchema rule
        first = error.details["writeErrors"][0]
        print("\nValidation rejected a document:")
        print(first.get("errmsg"))
        print(first.get("errInfo"))
        print("\nIf a field is listed as not allowed, add it to that collection's validator "
              "in app/schemas/validators.py, then run scripts.setup_collections again.")
        sys.exit(1)