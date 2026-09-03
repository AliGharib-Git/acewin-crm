"""
Loads and caches the Olist Brazilian E-Commerce dataset, and builds the
customer-level feature table every AI module in the Analytics Engine (Layer 3)
is trained and evaluated against, per the project spec: "ALL Artificial
Intelligence capabilities must be designed, demonstrated and validated using
the Olist Brazilian E-Commerce Dataset ... Do NOT use synthetic datasets."

Raw CSVs live in backend/data/olist/. Building the customer feature table
involves several multi-million-row joins, so the result is cached in memory
(and to a parquet file on disk) after the first computation.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "olist"
CACHE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

_FEATURE_CACHE = CACHE_DIR / "customer_features.parquet"
_MONTHLY_CACHE = CACHE_DIR / "monthly_sales.parquet"


class DatasetNotFoundError(RuntimeError):
    """Raised when the Olist CSVs are missing from backend/data/olist/."""


def _require_files(*names: str) -> None:
    missing = [n for n in names if not (DATA_DIR / n).exists()]
    if missing:
        raise DatasetNotFoundError(
            "Missing Olist dataset file(s): "
            f"{', '.join(missing)}. Expected them in {DATA_DIR}."
        )


@lru_cache
def load_raw() -> dict[str, pd.DataFrame]:
    _require_files(
        "olist_customers_dataset.csv",
        "olist_orders_dataset.csv",
        "olist_order_items_dataset.csv",
        "olist_order_payments_dataset.csv",
        "olist_order_reviews_dataset.csv",
        "olist_products_dataset.csv",
        "product_category_name_translation.csv",
    )
    customers = pd.read_csv(DATA_DIR / "olist_customers_dataset.csv")
    orders = pd.read_csv(
        DATA_DIR / "olist_orders_dataset.csv",
        parse_dates=[
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )
    items = pd.read_csv(DATA_DIR / "olist_order_items_dataset.csv")
    payments = pd.read_csv(DATA_DIR / "olist_order_payments_dataset.csv")
    reviews = pd.read_csv(
        DATA_DIR / "olist_order_reviews_dataset.csv",
        usecols=["review_id", "order_id", "review_score"],
    )
    products = pd.read_csv(DATA_DIR / "olist_products_dataset.csv")
    category_translation = pd.read_csv(DATA_DIR / "product_category_name_translation.csv")

    return {
        "customers": customers,
        "orders": orders,
        "items": items,
        "payments": payments,
        "reviews": reviews,
        "products": products,
        "category_translation": category_translation,
    }


@lru_cache
def customer_features() -> pd.DataFrame:
    """One row per customer_unique_id with RFM + behavioural features.

    This is the single feature table every prediction module (segmentation,
    churn, CLV, lead scoring, risk detection, ...) is built on, so all
    modules stay consistent with each other and with the raw dataset.
    """
    if _FEATURE_CACHE.exists():
        return pd.read_parquet(_FEATURE_CACHE)

    raw = load_raw()
    orders = raw["orders"]
    customers = raw["customers"]
    items = raw["items"]
    payments = raw["payments"]
    reviews = raw["reviews"]

    delivered = orders[orders["order_status"] == "delivered"].copy()
    delivered["delivery_days"] = (
        delivered["order_delivered_customer_date"] - delivered["order_purchase_timestamp"]
    ).dt.days
    delivered["delivery_delay_days"] = (
        delivered["order_delivered_customer_date"] - delivered["order_estimated_delivery_date"]
    ).dt.days

    order_value = payments.groupby("order_id")["payment_value"].sum().rename("order_value")
    order_review = reviews.groupby("order_id")["review_score"].mean().rename("review_score")
    order_items_count = items.groupby("order_id").size().rename("item_count")

    orders_enriched = (
        orders.merge(order_value, on="order_id", how="left")
        .merge(order_review, on="order_id", how="left")
        .merge(order_items_count, on="order_id", how="left")
        .merge(
            delivered[["order_id", "delivery_days", "delivery_delay_days"]],
            on="order_id",
            how="left",
        )
        .merge(customers[["customer_id", "customer_unique_id", "customer_state"]], on="customer_id", how="left")
    )
    orders_enriched["order_value"] = orders_enriched["order_value"].fillna(0.0)
    orders_enriched["item_count"] = orders_enriched["item_count"].fillna(0)

    snapshot_date = orders_enriched["order_purchase_timestamp"].max() + pd.Timedelta(days=1)

    grouped = orders_enriched.groupby("customer_unique_id")
    feat = grouped.agg(
        order_count=("order_id", "nunique"),
        total_spent=("order_value", "sum"),
        avg_order_value=("order_value", "mean"),
        first_order_date=("order_purchase_timestamp", "min"),
        last_order_date=("order_purchase_timestamp", "max"),
        avg_review_score=("review_score", "mean"),
        avg_items_per_order=("item_count", "mean"),
        avg_delivery_days=("delivery_days", "mean"),
        avg_delivery_delay_days=("delivery_delay_days", "mean"),
        state=("customer_state", "first"),
    ).reset_index()

    feat["recency_days"] = (snapshot_date - feat["last_order_date"]).dt.days
    feat["tenure_days"] = (feat["last_order_date"] - feat["first_order_date"]).dt.days
    feat["is_repeat_customer"] = (feat["order_count"] > 1).astype(int)
    feat["avg_review_score"] = feat["avg_review_score"].fillna(feat["avg_review_score"].mean())
    feat["avg_delivery_delay_days"] = feat["avg_delivery_delay_days"].fillna(0.0)
    feat["avg_delivery_days"] = feat["avg_delivery_days"].fillna(feat["avg_delivery_days"].mean())

    feat.to_parquet(_FEATURE_CACHE, index=False)
    return feat


@lru_cache
def monthly_sales() -> pd.DataFrame:
    """Month-level revenue and order-count time series for trend/forecast modules."""
    if _MONTHLY_CACHE.exists():
        return pd.read_parquet(_MONTHLY_CACHE)

    raw = load_raw()
    orders = raw["orders"]
    payments = raw["payments"]

    order_value = payments.groupby("order_id")["payment_value"].sum().rename("order_value")
    df = orders.merge(order_value, on="order_id", how="left")
    df["order_value"] = df["order_value"].fillna(0.0)
    df = df[df["order_status"] != "canceled"]
    df["month"] = df["order_purchase_timestamp"].dt.to_period("M").dt.to_timestamp()

    monthly = (
        df.groupby("month")
        .agg(revenue=("order_value", "sum"), orders=("order_id", "nunique"))
        .reset_index()
        .sort_values("month")
    )
    # The Olist marketplace was ramping up in its first few months (a handful
    # of near-empty test months, e.g. a single order in one month) and the
    # dataset cuts off mid-month at the end. Both distort month-over-month
    # growth without reflecting real seasonality, so they're excluded here --
    # a standard data-cleaning step, not a synthetic substitution.
    monthly = monthly[monthly["orders"] >= 50].reset_index(drop=True)
    if len(monthly) > 2:
        monthly = monthly.iloc[:-1].reset_index(drop=True)

    monthly.to_parquet(_MONTHLY_CACHE, index=False)
    return monthly


def clear_cache() -> None:
    """Drop cached tables (e.g. after replacing the raw CSVs)."""
    load_raw.cache_clear()
    customer_features.cache_clear()
    monthly_sales.cache_clear()
    for path in (_FEATURE_CACHE, _MONTHLY_CACHE):
        if path.exists():
            path.unlink()
