"""
etl-service — оркестратор конвейера и витрина аналитики поверх DWH.

Эндпоинты:
  GET  /health
  POST /etl/run                  — запустить конвейер (Extract→Transform→Load)
  GET  /dwh/stats                — число строк в каждой таблице DWH
  GET  /reports/sales-by-category
  GET  /reports/sales-by-month
  GET  /reports/top-customers
  (лаба) GET /reports/returns-by-category
"""
from fastapi import FastAPI
from sqlalchemy import func

import db
import etl

app = FastAPI(title="etl-service (DWH)")


@app.on_event("startup")
def _startup():
    db.init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "etl"}


@app.post("/etl/run")
def etl_run():
    """Запускает полный прогон ETL и возвращает счётчики загруженных строк."""
    counts = etl.run()
    return {"status": "OK", "loaded": counts}


@app.get("/dwh/stats")
def dwh_stats():
    """Число строк в каждой таблице витрины (включая добавленные в лабе)."""
    s = db.SessionLocal()
    try:
        out = {}
        for name, table in db.Base.metadata.tables.items():
            out[name] = s.query(func.count()).select_from(table).scalar()
        return out
    finally:
        s.close()


@app.get("/reports/sales-by-category")
def sales_by_category():
    """Выручка по категориям товаров."""
    s = db.SessionLocal()
    try:
        rows = (
            s.query(db.DimProduct.category, func.sum(db.FactSales.amount))
            .join(db.FactSales, db.FactSales.product_key == db.DimProduct.product_key)
            .group_by(db.DimProduct.category)
            .all()
        )
        return {cat: float(total) for cat, total in rows}
    finally:
        s.close()


@app.get("/reports/sales-by-month")
def sales_by_month():
    """Выручка по месяцам (год-месяц)."""
    s = db.SessionLocal()
    try:
        rows = (
            s.query(db.DimDate.year, db.DimDate.month, func.sum(db.FactSales.amount))
            .join(db.FactSales, db.FactSales.date_key == db.DimDate.date_key)
            .group_by(db.DimDate.year, db.DimDate.month)
            .order_by(db.DimDate.year, db.DimDate.month)
            .all()
        )
        return {f"{y}-{m:02d}": float(total) for y, m, total in rows}
    finally:
        s.close()


@app.get("/reports/top-customers")
def top_customers():
    """Клиенты по сумме покупок (по убыванию)."""
    s = db.SessionLocal()
    try:
        rows = (
            s.query(db.DimCustomer.name, func.sum(db.FactSales.amount))
            .join(db.FactSales, db.FactSales.customer_key == db.DimCustomer.customer_key)
            .group_by(db.DimCustomer.name)
            .order_by(func.sum(db.FactSales.amount).desc())
            .all()
        )
        return {name: float(total) for name, total in rows}
    finally:
        s.close()


# ---------------------------------------------------------------------------
# ЛАБОРАТОРНАЯ РАБОТА: добавьте отчёт по возвратам.
#
# @app.get("/reports/returns-by-category")
# def returns_by_category():
#     """Сумма возвратов по категориям товаров."""
#     ...
#     Должен возвращать словарь {категория: сумма_возвратов}.
# ---------------------------------------------------------------------------
