"""
Локальная БД операционной системы (OLTP) интернет-магазина.

Это «источник» для ETL: нормализованные таблицы, как в обычном
бизнес-приложении. У сервиса своя БД (SQLite-файл), доступ к данным —
только через его API (см. main.py). Принцип «database per service».

В проде SQLite меняется на свой PostgreSQL/MySQL правкой одной строки
DATABASE_URL — код не трогаем (благодаря SQLAlchemy).
"""
import os
from datetime import date

from sqlalchemy import (
    Column, Date, Float, ForeignKey, Integer, String, create_engine
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./source.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    country = Column(String, nullable=False)


class Product(Base):
    __tablename__ = "products"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)
    price = Column(Float, nullable=False)


class Order(Base):
    __tablename__ = "orders"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), nullable=False)
    created_at = Column(Date, nullable=False)
    status = Column(String, nullable=False, default="PAID")
    items = relationship("OrderItem", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"
    id = Column(Integer, primary_key=True)
    order_id = Column(Integer, ForeignKey("orders.id"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    order = relationship("Order", back_populates="items")


class Return(Base):
    """Возврат товара по конкретной позиции заказа."""
    __tablename__ = "returns"
    id = Column(Integer, primary_key=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id"), nullable=False)
    quantity = Column(Integer, nullable=False)
    reason = Column(String, nullable=False)
    created_at = Column(Date, nullable=False)


# --- Сид: немного детерминированных данных, чтобы числа в отчётах сходились ---

SEED_CUSTOMERS = [
    dict(id=1, name="Иван",  city="Москва", country="RU"),
    dict(id=2, name="Олег",  city="Казань", country="RU"),
    dict(id=3, name="Anna",  city="Berlin", country="DE"),
    dict(id=4, name="John",  city="London", country="GB"),
]

SEED_PRODUCTS = [
    dict(id=1, name="Ноутбук", category="Электроника", price=60000),
    dict(id=2, name="Мышь",    category="Электроника", price=1500),
    dict(id=3, name="Книга",   category="Книги",       price=800),
    dict(id=4, name="Кофе",    category="Продукты",    price=500),
]

SEED_ORDERS = [
    dict(id=1, customer_id=1, created_at=date(2024, 1, 15)),
    dict(id=2, customer_id=2, created_at=date(2024, 1, 20)),
    dict(id=3, customer_id=3, created_at=date(2024, 2, 5)),
    dict(id=4, customer_id=1, created_at=date(2024, 2, 18)),
    dict(id=5, customer_id=4, created_at=date(2024, 3, 2)),
]

SEED_ITEMS = [
    dict(id=1, order_id=1, product_id=1, quantity=1,  unit_price=60000),
    dict(id=2, order_id=1, product_id=2, quantity=2,  unit_price=1500),
    dict(id=3, order_id=2, product_id=3, quantity=3,  unit_price=800),
    dict(id=4, order_id=3, product_id=2, quantity=1,  unit_price=1500),
    dict(id=5, order_id=3, product_id=4, quantity=10, unit_price=500),
    dict(id=6, order_id=4, product_id=1, quantity=1,  unit_price=60000),
    dict(id=7, order_id=5, product_id=3, quantity=1,  unit_price=800),
    dict(id=8, order_id=5, product_id=4, quantity=4,  unit_price=500),
]

SEED_RETURNS = [
    dict(id=1, order_item_id=2, quantity=1, reason="брак",       created_at=date(2024, 1, 25)),
    dict(id=2, order_item_id=5, quantity=2, reason="не подошло", created_at=date(2024, 2, 10)),
    dict(id=3, order_item_id=7, quantity=1, reason="брак",       created_at=date(2024, 3, 5)),
]


def init_db():
    """Создаёт таблицы и наполняет их сид-данными, если БД пустая."""
    Base.metadata.create_all(engine)
    s = SessionLocal()
    try:
        if s.query(Customer).count() > 0:
            return
        s.add_all([Customer(**r) for r in SEED_CUSTOMERS])
        s.add_all([Product(**r) for r in SEED_PRODUCTS])
        s.add_all([Order(**r) for r in SEED_ORDERS])
        s.add_all([OrderItem(**r) for r in SEED_ITEMS])
        s.add_all([Return(**r) for r in SEED_RETURNS])
        s.commit()
    finally:
        s.close()
