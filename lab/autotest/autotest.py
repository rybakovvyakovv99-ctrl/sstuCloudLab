#!/usr/bin/env python3
"""
Самопроверяемый автотест лабораторной.

Гоняет ETL по HTTP и проверяет витрину:
  - БАЗОВЫЕ проверки (продажи) проходят сразу, «из коробки»;
  - проверки по ВОЗВРАТАМ проходят только после выполнения лабы.

Запуск (сервисы должны быть подняты, см. autotest/README.md):
    python autotest.py
    # или другой адрес:
    ETL_URL=http://localhost:8000 python autotest.py
"""
import os
import sys

import httpx

ETL_URL = os.getenv("ETL_URL", "http://localhost:8000")
TIMEOUT = float(os.getenv("HTTP_TIMEOUT", "10.0"))

passed, failed = 0, 0


def check(name, ok, detail=""):
    global passed, failed
    mark = "PASS" if ok else "FAIL"
    print(f"[{mark}] {name}" + (f" — {detail}" if detail and not ok else ""))
    if ok:
        passed += 1
    else:
        failed += 1


def approx(a, b, eps=1e-6):
    return a is not None and abs(float(a) - float(b)) < eps


def main():
    c = httpx.Client(base_url=ETL_URL, timeout=TIMEOUT)

    # health
    try:
        r = c.get("/health")
        check("etl /health доступен", r.status_code == 200, f"status={r.status_code}")
    except Exception as e:
        check("etl /health доступен", False, str(e))
        print("\nСервис недоступен. Подними стек (docker compose up) и повтори.")
        sys.exit(1)

    # запускаем конвейер
    r = c.post("/etl/run")
    check("POST /etl/run возвращает 200", r.status_code == 200, f"status={r.status_code}")

    stats = c.get("/dwh/stats").json()

    # ---------- БАЗОВЫЕ проверки (продажи) ----------
    print("\n--- Базовые проверки (продажи) ---")
    check("dim_customer = 4", stats.get("dim_customer") == 4, f"={stats.get('dim_customer')}")
    check("dim_product = 4", stats.get("dim_product") == 4, f"={stats.get('dim_product')}")
    check("fact_sales = 8", stats.get("fact_sales") == 8, f"={stats.get('fact_sales')}")

    sbc = c.get("/reports/sales-by-category").json()
    check("выручка Электроника = 124500", approx(sbc.get("Электроника"), 124500), f"={sbc.get('Электроника')}")
    check("выручка Книги = 3200", approx(sbc.get("Книги"), 3200), f"={sbc.get('Книги')}")
    check("выручка Продукты = 7000", approx(sbc.get("Продукты"), 7000), f"={sbc.get('Продукты')}")

    # ---------- Проверки ЛАБЫ (возвраты) ----------
    print("\n--- Проверки лабы (возвраты) ---")

    check("dim_date = 8 (даты заказов + возвратов)", stats.get("dim_date") == 8,
          f"={stats.get('dim_date')} (без дат возвратов будет 5)")
    check("в DWH есть таблица fact_returns", "fact_returns" in stats,
          "объяви модель FactReturns в db.py")
    check("fact_returns = 3", stats.get("fact_returns") == 3, f"={stats.get('fact_returns')}")

    r = c.get("/reports/returns-by-category")
    if r.status_code != 200:
        check("GET /reports/returns-by-category доступен", False, f"status={r.status_code}")
    else:
        check("GET /reports/returns-by-category доступен", True)
        rbc = r.json()
        check("возвраты Электроника = 1500", approx(rbc.get("Электроника"), 1500), f"={rbc.get('Электроника')}")
        check("возвраты Продукты = 1000", approx(rbc.get("Продукты"), 1000), f"={rbc.get('Продукты')}")
        check("возвраты Книги = 800", approx(rbc.get("Книги"), 800), f"={rbc.get('Книги')}")

    print(f"\nИтог: {passed} passed, {failed} failed")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
