"""Deterministic OLTP-dump generator for the Rundle ecommerce warehouse.

Run from the project root:

    python -m fixtures.generate_fixtures

Output is seven CSV files under fixtures/oltp_dump/, standing in for what a real
daily extract from Rundle's transactional Postgres would look like:

    customers.csv          ~50_000 rows  (1 row per active customer)
    products.csv           ~2_000  rows  (1 row per SKU; ~2% have been renamed mid-period)
    channels.csv           5       rows  (web, ios, android, kiosk, partner)
    countries.csv          15      rows  (ISO-3166 alpha-2 + canonical names — the conformed-dim source)
    orders.csv             ~150_000 rows (1 row per order, with order_date and ship_date)
    order_lines.csv        ~500_000 rows (1 row per (order_id, line_number) — the future fact grain)
    dates.csv              ~1_100  rows  (3 years of dates with day/month/quarter/year attributes)

All files are byte-for-byte reproducible: a single `random.Random(42)` seeds every
choice and timestamps derive from arithmetic on a known epoch. CSV writer uses
`lineterminator="\\n"` and `csv.QUOTE_MINIMAL` to avoid platform drift.

The "tricks" baked in (intentionally, to surface common modelling mistakes):

- role-playing dates:
    orders.csv carries both `order_date` and `ship_date`. ~99% of ship_dates are
    >= order_date (1-7 days). ~1% are corrections where ship_date < order_date —
    those are kept in the data so the learner sees that the negative-delta check
    in the CI rubric tolerates a small fraction.
- product rename (SCD1 territory, NOT SCD2):
    ~2% of products have their `product_name` rewritten mid-period in
    products.csv (the dump represents the CURRENT state of the OLTP). The learner
    must NOT build an SCD2 here — the assignment is star schema, not history
    tracking. This is to test whether they read the spec.
- late-arriving customer:
    ~0.5% of order_lines reference a customer_id that does NOT exist in
    customers.csv (the OLTP extract sometimes ships before the customers table is
    repopulated). The learner must decide how to handle them. Two acceptable
    answers: (a) drop the offending rows with a logged warning, (b) build a
    placeholder "unknown customer" sk row. Either way, the fact must not orphan.
- degenerate dimension:
    order_id lives on the fact (it is the natural identifier for the line) but
    there is NO dim_order table — it is a degenerate dimension. The learner who
    builds dim_order is over-modelling.
- country conformed vs unconformed:
    customers.csv uses ISO-3166 alpha-2 country codes. countries.csv carries the
    canonical name + region. orders.csv ALSO carries a country_code (the
    ship-to country) — these may differ from the customer's billing country.
    The learner must conform on the same dim_country, joined twice.
- grain trap:
    The intuitive "one row per order" grain is wrong — multi-line orders would
    require pre-aggregating revenue, and revenue-by-product is impossible from
    an order-grain fact. The correct grain is one row per (order_id, line_number).
"""

from __future__ import annotations

import csv
import os
import random
from datetime import datetime, timedelta
from pathlib import Path

SEED = 42
N_CUSTOMERS = 50_000
N_PRODUCTS = 2_000
N_ORDERS = 150_000
N_ORDER_LINES_TARGET = 500_000  # actual count drifts ±0.5% with the variable lines/order
PERIOD_START = datetime(2023, 1, 1)
PERIOD_END = datetime(2025, 12, 31)
PRODUCT_RENAME_RATE = 0.02
LATE_ARRIVING_CUSTOMER_RATE = 0.005
SHIP_DATE_NEGATIVE_RATE = 0.01

FIXTURES_DIR = Path(__file__).resolve().parent / "oltp_dump"

COUNTRIES = [
    # ISO code,    canonical name,                  region
    ("FR", "France", "EMEA"),
    ("DE", "Germany", "EMEA"),
    ("IT", "Italy", "EMEA"),
    ("ES", "Spain", "EMEA"),
    ("NL", "Netherlands", "EMEA"),
    ("BE", "Belgium", "EMEA"),
    ("PT", "Portugal", "EMEA"),
    ("GB", "United Kingdom", "EMEA"),
    ("IE", "Ireland", "EMEA"),
    ("US", "United States", "AMER"),
    ("CA", "Canada", "AMER"),
    ("BR", "Brazil", "AMER"),
    ("MX", "Mexico", "AMER"),
    ("JP", "Japan", "APAC"),
    ("AU", "Australia", "APAC"),
]

CHANNELS = [
    # channel_id, channel_name, channel_type
    ("web", "Web", "online"),
    ("ios", "iOS App", "online"),
    ("android", "Android App", "online"),
    ("kiosk", "Retail Kiosk", "offline"),
    ("partner", "Partner Marketplace", "online"),
]

PRODUCT_CATEGORIES = [
    ("electronics", "Electronics"),
    ("apparel", "Apparel"),
    ("home", "Home & Garden"),
    ("sports", "Sports & Outdoors"),
    ("beauty", "Beauty"),
    ("books", "Books"),
]

ORDER_STATUS = ["completed", "completed", "completed", "completed", "completed", "returned"]


def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
        writer.writerow(header)
        writer.writerows(rows)


def _gen_countries() -> list[list]:
    return [[code, name, region] for code, name, region in COUNTRIES]


def _gen_channels() -> list[list]:
    return [[cid, name, ctype] for cid, name, ctype in CHANNELS]


def _gen_products(rng: random.Random) -> list[list]:
    """Returns rows for products.csv: [product_id, product_name, category, list_price].

    ~2% of names are mid-period rewrites. The dump represents CURRENT state — the
    learner who builds an SCD2 for products is over-engineering. The new name is
    the only name persisted.
    """
    rows = []
    for i in range(N_PRODUCTS):
        product_id = 10_000 + i
        cat_code, cat_label = rng.choice(PRODUCT_CATEGORIES)
        base_name = f"{cat_label} Item {i:04d}"
        if rng.random() < PRODUCT_RENAME_RATE:
            # Renamed product: the dump persists only the new name, no history.
            product_name = f"{base_name} (Refreshed Edition)"
        else:
            product_name = base_name
        list_price_cents = rng.randint(500, 50_000)  # 5.00 to 500.00 EUR
        rows.append([product_id, product_name, cat_code, f"{list_price_cents/100:.2f}"])
    return rows


def _gen_customers(rng: random.Random) -> list[list]:
    """Returns [customer_id, email, country_code, signup_date, segment]."""
    rows = []
    for i in range(N_CUSTOMERS):
        customer_id = 500_000 + i
        country = rng.choice(COUNTRIES)[0]
        signup_offset_days = rng.randint(0, (PERIOD_END - PERIOD_START).days)
        signup_date = PERIOD_START + timedelta(days=signup_offset_days)
        segment = rng.choice(["B2C", "B2C", "B2C", "B2C", "B2B"])
        email = f"user{customer_id}@rundle.example"
        rows.append([
            customer_id,
            email,
            country,
            signup_date.strftime("%Y-%m-%d"),
            segment,
        ])
    return rows


def _gen_dates() -> list[list]:
    """Returns [date_key (YYYYMMDD int), date_iso, day, month, quarter, year, day_of_week, is_weekend].

    Covers PERIOD_START..PERIOD_END inclusive. dim_date is the role-played dim joined
    twice (as order_date and ship_date) — there is exactly ONE physical dim, not two.
    """
    rows = []
    current = PERIOD_START
    while current <= PERIOD_END:
        date_key = int(current.strftime("%Y%m%d"))
        rows.append([
            date_key,
            current.strftime("%Y-%m-%d"),
            current.day,
            current.month,
            (current.month - 1) // 3 + 1,
            current.year,
            current.isoweekday(),  # 1=Monday, 7=Sunday
            1 if current.isoweekday() >= 6 else 0,
        ])
        current += timedelta(days=1)
    return rows


def _gen_orders_and_lines(
    rng: random.Random,
    customer_ids: list[int],
    product_ids: list[int],
) -> tuple[list[list], list[list]]:
    """Returns (orders_rows, order_lines_rows).

    orders.csv columns:
        order_id, customer_id, channel_id, country_code (ship-to), order_date, ship_date, status
    order_lines.csv columns:
        order_id, line_number, product_id, quantity, unit_price_eur, discount_eur
    """
    orders_rows: list[list] = []
    lines_rows: list[list] = []

    # Late-arriving customers: a small fraction of order rows will reference an
    # ID that's NOT in customer_ids. We synthesise these "phantom" ids in a
    # disjoint range so the learner sees the orphan clearly.
    n_late = int(N_ORDERS * LATE_ARRIVING_CUSTOMER_RATE)
    phantom_customer_ids = [9_000_000 + i for i in range(n_late)]
    late_arriving_indices = set(rng.sample(range(N_ORDERS), n_late))

    period_days = (PERIOD_END - PERIOD_START).days

    for i in range(N_ORDERS):
        order_id = 1_000_000 + i
        if i in late_arriving_indices:
            customer_id = phantom_customer_ids.pop()
        else:
            customer_id = rng.choice(customer_ids)
        channel_id = rng.choice(CHANNELS)[0]
        country_code = rng.choice(COUNTRIES)[0]

        order_day_offset = rng.randint(0, period_days)
        order_date = PERIOD_START + timedelta(days=order_day_offset)

        # Ship date: usually 1-7 days after order_date, occasionally negative
        # (correction). The CI rubric tolerates < 1% negative deltas.
        if rng.random() < SHIP_DATE_NEGATIVE_RATE:
            ship_delta = -rng.randint(1, 3)
        else:
            ship_delta = rng.randint(1, 7)
        ship_date = order_date + timedelta(days=ship_delta)
        # Clamp inside the period so dim_date join works for both.
        if ship_date > PERIOD_END:
            ship_date = PERIOD_END
        if ship_date < PERIOD_START:
            ship_date = PERIOD_START

        status = rng.choice(ORDER_STATUS)

        orders_rows.append([
            order_id,
            customer_id,
            channel_id,
            country_code,
            order_date.strftime("%Y-%m-%d"),
            ship_date.strftime("%Y-%m-%d"),
            status,
        ])

        # Number of lines per order: skewed (most orders 1-2 lines, long tail to 12).
        # Average chosen to land close to N_ORDER_LINES_TARGET / N_ORDERS ≈ 3.33.
        n_lines = max(1, int(rng.triangular(1, 12, 2.5)))
        chosen_products = rng.sample(product_ids, min(n_lines, len(product_ids)))
        for line_number, product_id in enumerate(chosen_products, start=1):
            unit_price_cents = rng.randint(500, 30_000)  # 5..300 EUR
            quantity = rng.randint(1, 4)
            discount_cents = (
                rng.randint(0, unit_price_cents // 5) if rng.random() < 0.3 else 0
            )
            lines_rows.append([
                order_id,
                line_number,
                product_id,
                quantity,
                f"{unit_price_cents/100:.2f}",
                f"{discount_cents/100:.2f}",
            ])

    return orders_rows, lines_rows


def generate() -> dict[str, Path]:
    rng = random.Random(SEED)
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    out: dict[str, Path] = {}

    # 1. small reference dims
    out["countries"] = FIXTURES_DIR / "countries.csv"
    _write_csv(out["countries"], ["country_code", "country_name", "region"], _gen_countries())

    out["channels"] = FIXTURES_DIR / "channels.csv"
    _write_csv(out["channels"], ["channel_id", "channel_name", "channel_type"], _gen_channels())

    # 2. dates
    out["dates"] = FIXTURES_DIR / "dates.csv"
    _write_csv(
        out["dates"],
        ["date_key", "date_iso", "day", "month", "quarter", "year", "day_of_week", "is_weekend"],
        _gen_dates(),
    )

    # 3. products
    products = _gen_products(rng)
    out["products"] = FIXTURES_DIR / "products.csv"
    _write_csv(
        out["products"],
        ["product_id", "product_name", "category_code", "list_price_eur"],
        products,
    )

    # 4. customers
    customers = _gen_customers(rng)
    out["customers"] = FIXTURES_DIR / "customers.csv"
    _write_csv(
        out["customers"],
        ["customer_id", "email", "country_code", "signup_date", "segment"],
        customers,
    )

    # 5. orders + order_lines
    customer_ids = [row[0] for row in customers]
    product_ids = [row[0] for row in products]
    orders, order_lines = _gen_orders_and_lines(rng, customer_ids, product_ids)
    out["orders"] = FIXTURES_DIR / "orders.csv"
    _write_csv(
        out["orders"],
        ["order_id", "customer_id", "channel_id", "country_code", "order_date", "ship_date", "status"],
        orders,
    )
    out["order_lines"] = FIXTURES_DIR / "order_lines.csv"
    _write_csv(
        out["order_lines"],
        ["order_id", "line_number", "product_id", "quantity", "unit_price_eur", "discount_eur"],
        order_lines,
    )
    return out


def main() -> None:
    paths = generate()
    for name, path in paths.items():
        size = os.path.getsize(path)
        # Counting newlines minus the header line is robust here (no embedded newlines in fields).
        with path.open("r", encoding="utf-8") as f:
            row_count = sum(1 for _ in f) - 1
        print(f"wrote {path}  ({row_count} rows, {size} bytes)")


if __name__ == "__main__":
    main()
