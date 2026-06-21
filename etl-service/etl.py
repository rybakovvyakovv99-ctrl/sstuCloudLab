"""
Сам ETL-конвейер: Extract → Transform → Load.

  Extract   — выгружаем сырые данные из источника (source-service) по HTTP.
  Transform — чистим/обогащаем, строим измерения, считаем меры, проставляем
              суррогатные ключи.
  Load      — записываем измерения и факт в DWH.

Стратегия загрузки — full reload: на каждом прогоне витрину пересобираем
с нуля. Просто и идемпотентно — удобно для учебного демо. В проде чаще
используют инкрементальную загрузку и upsert.
"""
import os
from datetime import date

import httpx

import db

SOURCE_URL = os.getenv("SOURCE_URL", "http://source:8000")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10.0"))


# ----------------------------- EXTRACT -------------------------------------

def extract():
    """Тянем сырьё из операционной системы через её API."""
    with httpx.Client(base_url=SOURCE_URL, timeout=HTTP_TIMEOUT) as c:
        customers = c.get("/customers").json()
        products = c.get("/products").json()
        sales = c.get("/sales").json()
    return customers, products, sales


def _date_key(d: date) -> int:
    return d.year * 10000 + d.month * 100 + d.day


def _parse(d: str) -> date:
    return date.fromisoformat(d)


# ------------------------- TRANSFORM + LOAD --------------------------------

def run() -> dict:
    """Полный прогон конвейера. Возвращает счётчики загруженных строк."""
    customers, products, sales = extract()

    db.reset_db()
    s = db.SessionLocal()
    try:
        # --- измерение: клиенты (natural id -> surrogate key) ---
        cust_key = {}
        for c in customers:
            row = db.DimCustomer(
                customer_id=c["id"], name=c["name"],
                city=c["city"], country=c["country"],
            )
            s.add(row)
            s.flush()                       # получаем сгенерированный surrogate key
            cust_key[c["id"]] = row.customer_key

        # --- измерение: товары ---
        prod_key = {}
        for p in products:
            row = db.DimProduct(
                product_id=p["id"], name=p["name"], category=p["category"],
            )
            s.add(row)
            s.flush()
            prod_key[p["id"]] = row.product_key

        # --- измерение: даты (собираем уникальные даты из фактов) ---
        date_keys = set()

        def ensure_date(d: date):
            dk = _date_key(d)
            if dk not in date_keys:
                q = (d.month - 1) // 3 + 1
                s.add(db.DimDate(
                    date_key=dk, full_date=d, day=d.day,
                    month=d.month, quarter=q, year=d.year,
                ))
                date_keys.add(dk)
            return dk

        # --- факт: продажи ---
        n_sales = 0
        for r in sales:
            d = _parse(r["created_at"])
            dk = ensure_date(d)
            amount = r["quantity"] * r["unit_price"]
            s.add(db.FactSales(
                sale_id=r["order_item_id"],
                date_key=dk,
                customer_key=cust_key[r["customer_id"]],
                product_key=prod_key[r["product_id"]],
                quantity=r["quantity"],
                unit_price=r["unit_price"],
                amount=amount,
            ))
            n_sales += 1

        # -------------------------------------------------------------------
        # ЛАБОРАТОРНАЯ РАБОТА: добавьте сюда обработку возвратов.
        #  1) extract: дотяните GET /returns из source-service;
        #  2) transform: по order_item_id найдите товар/клиента/цену
        #     (можно построить индекс по `sales`), посчитайте amount;
        #     не забудьте ensure_date(дата возврата) — даты возвратов
        #     тоже должны попасть в dim_date;
        #  3) load: запишите строки в db.FactReturns.
        # Верните количество в счётчиках ниже (ключ "fact_returns").
        # -------------------------------------------------------------------

        s.commit()
        return {
            "dim_customer": len(cust_key),
            "dim_product": len(prod_key),
            "dim_date": len(date_keys),
            "fact_sales": n_sales,
        }
    finally:
        s.close()
