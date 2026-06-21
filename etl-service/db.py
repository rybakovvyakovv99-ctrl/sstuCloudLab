"""
Хранилище данных (DWH) — схема «звезда».

DWH — отдельная БД, оптимизированная под аналитику (а не под транзакции, как
OLTP-источник). Здесь данные денормализованы в звезду:

  - таблицы-ИЗМЕРЕНИЯ (dimensions) — справочники, по которым «режут» аналитику:
    кто (клиент), что (товар), когда (дата);
  - таблица-ФАКТ (fact) — числовые показатели бизнес-события (продажа): сколько
    штук, на какую сумму, со ссылками (foreign key) на измерения.

Суррогатные ключи (..._key) — собственные ключи DWH, независимые от ключей
источника (..._id, natural key). Это позволяет хранилищу жить своей жизнью:
менять источник, версионировать измерения и т.д.

   dim_customer ┐
   dim_product  ├──< fact_sales
   dim_date     ┘

Принцип «database per service»: у DWH своя БД (отдельный SQLite-файл). В проде
это Postgres/ClickHouse/Snowflake/BigQuery — меняется строкой DATABASE_URL.
"""
import os

from sqlalchemy import Column, Date, Float, ForeignKey, Integer, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./dwh.db")

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


class DimCustomer(Base):
    __tablename__ = "dim_customer"
    customer_key = Column(Integer, primary_key=True, autoincrement=True)  # суррогатный
    customer_id = Column(Integer, nullable=False, unique=True)            # natural key
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    country = Column(String, nullable=False)


class DimProduct(Base):
    __tablename__ = "dim_product"
    product_key = Column(Integer, primary_key=True, autoincrement=True)   # суррогатный
    product_id = Column(Integer, nullable=False, unique=True)             # natural key
    name = Column(String, nullable=False)
    category = Column(String, nullable=False)


class DimDate(Base):
    __tablename__ = "dim_date"
    date_key = Column(Integer, primary_key=True)  # формат YYYYMMDD
    full_date = Column(Date, nullable=False)
    day = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    quarter = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)


class FactSales(Base):
    __tablename__ = "fact_sales"
    sale_id = Column(Integer, primary_key=True)            # = order_item_id источника
    date_key = Column(Integer, ForeignKey("dim_date.date_key"), nullable=False)
    customer_key = Column(Integer, ForeignKey("dim_customer.customer_key"), nullable=False)
    product_key = Column(Integer, ForeignKey("dim_product.product_key"), nullable=False)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Float, nullable=False)
    amount = Column(Float, nullable=False)  # quantity * unit_price (предрасчёт меры)


# ---------------------------------------------------------------------------
# ЛАБОРАТОРНАЯ РАБОТА: здесь нужно объявить таблицу-факт FactReturns.
# Подсказка по структуре — в lab/LAB.md. После объявления модели она
# автоматически попадёт в Base.metadata и в /dwh/stats.
#
# class FactReturns(Base):
#     __tablename__ = "fact_returns"
#     ...
# ---------------------------------------------------------------------------


def init_db():
    Base.metadata.create_all(engine)


def reset_db():
    """Полная перезагрузка витрины: дропаем и создаём заново (full reload)."""
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
