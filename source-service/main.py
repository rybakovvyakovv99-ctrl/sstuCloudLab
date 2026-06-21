"""
source-service — операционная система (OLTP) интернет-магазина.

Это ИСТОЧНИК данных для ETL. Сервис владеет своей БД и наружу отдаёт данные
только через API — никто не лезет в его таблицы напрямую. Шаг Extract
конвейера читает именно эти эндпоинты.

Эндпоинты:
  GET /health
  GET /customers   — справочник клиентов
  GET /products    — справочник товаров
  GET /sales       — позиции заказов (плоский поток для загрузки продаж)
  GET /returns     — возвраты (используются в лабораторной работе)
"""
from fastapi import FastAPI

from db import Customer, Order, OrderItem, Product, Return, SessionLocal, init_db

app = FastAPI(title="source-service (OLTP)")


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok", "service": "source"}


@app.get("/customers")
def customers():
    s = SessionLocal()
    try:
        rows = s.query(Customer).all()
        return [
            dict(id=c.id, name=c.name, city=c.city, country=c.country)
            for c in rows
        ]
    finally:
        s.close()


@app.get("/products")
def products():
    s = SessionLocal()
    try:
        rows = s.query(Product).all()
        return [
            dict(id=p.id, name=p.name, category=p.category, price=p.price)
            for p in rows
        ]
    finally:
        s.close()


@app.get("/sales")
def sales():
    """Плоский поток позиций заказов: одна строка = одна проданная позиция."""
    s = SessionLocal()
    try:
        q = (
            s.query(OrderItem, Order)
            .join(Order, OrderItem.order_id == Order.id)
            .all()
        )
        return [
            dict(
                order_item_id=item.id,
                order_id=order.id,
                created_at=order.created_at.isoformat(),
                status=order.status,
                customer_id=order.customer_id,
                product_id=item.product_id,
                quantity=item.quantity,
                unit_price=item.unit_price,
            )
            for item, order in q
        ]
    finally:
        s.close()


@app.get("/returns")
def returns():
    """Возвраты по позициям заказов (для лабораторной работы)."""
    s = SessionLocal()
    try:
        rows = s.query(Return).all()
        return [
            dict(
                return_id=r.id,
                order_item_id=r.order_item_id,
                quantity=r.quantity,
                reason=r.reason,
                created_at=r.created_at.isoformat(),
            )
            for r in rows
        ]
    finally:
        s.close()
