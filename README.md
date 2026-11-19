# Data Warehouse y BI para retail

Solución de inteligencia de negocios sobre las ventas semanales de una cadena de retail (dataset público de ventas de Walmart): un data warehouse en PostgreSQL con modelo estrella, un proceso ETL en Python y tableros en Power BI.

Trabajo práctico de Bases de Datos II (IUA, 2026), hecho con la metodología Hefesto.

**Stack:** PostgreSQL · Python (pandas, SQLAlchemy) · Power BI

## Modelo estrella

La tabla de hechos `fact_ventas` (ventas semanales por tienda) se cruza con seis dimensiones:

| Dimensión | Qué agrega |
| --- | --- |
| `dim_tiempo` | semana, mes, trimestre, semestre, año y si la semana tuvo feriado |
| `dim_tienda` | ventas promedio, categoría de rendimiento e índice de resiliencia de cada tienda |
| `dim_clima` | temperatura clasificada en categorías (muy frío, frío, templado, caluroso) |
| `dim_combustible` | precio del combustible en niveles bajo, medio y alto |
| `dim_cpi` | índice de precios al consumidor en niveles bajo, medio y alto |
| `dim_desempleo` | tasa de desempleo en niveles bajo, medio y alto |

## ETL

`etl.py` hace las tres etapas:

1. **Extracción:** lee `data/raw/Walmart_sales.csv`.
2. **Transformación:** limpia los datos, arma las dimensiones (incluidas las categorías por percentiles) y calcula los indicadores de cada tienda.
3. **Carga:** crea las tablas en PostgreSQL, carga dimensiones y hechos, y deja una copia de cada tabla en `data/dw/`.

## Cómo correrlo

```bash
pip install -r requirements.txt
# definir DATABASE_URL (ver .env.example)
python etl.py
```

Las tablas ya procesadas están en `data/dw/` por si se quieren cargar directamente en Power BI sin correr el ETL.

## Estructura

```
etl.py          proceso ETL completo
data/raw/       dataset original
data/dw/        dimensiones y tabla de hechos generadas
```
