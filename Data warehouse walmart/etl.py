import os
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

# =====================================================
# CONFIGURACION
# =====================================================

RUTA_CSV_ORIGINAL = r"C:\Users\leand\OneDrive\Desktop\Facu\bd2\Data Warehouse y BI\retail_bi\data\Walmart_sales.csv"
CONEXION_URL = "postgresql://postgres.nzwkvmjhzhujmsqcnbhb:mK7rS1kILfgXopo2@aws-1-us-west-2.pooler.supabase.com:5432/postgres"

engine = create_engine(
    CONEXION_URL,
    poolclass=NullPool,
    client_encoding="utf8"
)

# =====================================================
# FUNCIONES AUXILIARES
# =====================================================

def clasificar_clima(temp):
    # MEJORA 3: Lógica de clima actualizada
    if temp < 32:
        return "Muy Frio"
    elif temp < 50:
        return "Frio"
    elif temp <= 75:
        return "Templado"
    else:
        return "Caluroso"

def clasificar_por_percentiles(valor, p33, p66):
    if valor <= p33:
        return "Bajo"
    elif valor <= p66:
        return "Medio"
    else:
        return "Alto"

# =====================================================
# CREACION DE TABLAS
# =====================================================

def crear_tablas():
    with engine.connect() as conn:
        
        # Eliminamos las tablas viejas para forzar la nueva estructura
        conn.execute(text("""
            DROP TABLE IF EXISTS fact_ventas CASCADE;
            DROP TABLE IF EXISTS dim_clima CASCADE;
            DROP TABLE IF EXISTS dim_combustible CASCADE;
            DROP TABLE IF EXISTS dim_cpi CASCADE;
            DROP TABLE IF EXISTS dim_desempleo CASCADE;
            DROP TABLE IF EXISTS dim_tienda CASCADE;
            DROP TABLE IF EXISTS dim_tiempo CASCADE;
        """))
        conn.commit()

        # MEJORA 2: Se agregó "semestre"
        conn.execute(text("""
        CREATE TABLE dim_tiempo(
            id_tiempo INTEGER PRIMARY KEY,
            date DATE,
            semana INTEGER,
            mes INTEGER,
            nombre_mes VARCHAR(20),
            trimestre INTEGER,
            semestre INTEGER,
            anio INTEGER,
            holiday_flag BOOLEAN
        );
        """))

        # MEJORA 1: Se agregaron las columnas de resiliencia
        conn.execute(text("""
        CREATE TABLE dim_tienda(
            id_tienda INTEGER PRIMARY KEY,
            store INTEGER,
            ventas_promedio NUMERIC(15,2),
            categoria_rendimiento VARCHAR(30),
            indice_resiliencia NUMERIC(15,2),
            categoria_resiliencia VARCHAR(30)
        );
        """))

        conn.execute(text("""
        CREATE TABLE dim_clima(
            id_clima INTEGER PRIMARY KEY,
            categoria_clima VARCHAR(20)
        );
        """))

        conn.execute(text("""
        CREATE TABLE dim_combustible(
            id_combustible INTEGER PRIMARY KEY,
            categoria_combustible VARCHAR(20)
        );
        """))

        conn.execute(text("""
        CREATE TABLE dim_cpi(
            id_cpi INTEGER PRIMARY KEY,
            nivel_cpi VARCHAR(20)
        );
        """))

        conn.execute(text("""
        CREATE TABLE dim_desempleo(
            id_desempleo INTEGER PRIMARY KEY,
            nivel_desempleo VARCHAR(20)
        );
        """))

        conn.execute(text("""
        CREATE TABLE fact_ventas(
            id_venta SERIAL PRIMARY KEY,
            id_tiempo INTEGER REFERENCES dim_tiempo(id_tiempo),
            id_tienda INTEGER REFERENCES dim_tienda(id_tienda),
            id_clima INTEGER REFERENCES dim_clima(id_clima),
            id_combustible INTEGER REFERENCES dim_combustible(id_combustible),
            id_cpi INTEGER REFERENCES dim_cpi(id_cpi),
            id_desempleo INTEGER REFERENCES dim_desempleo(id_desempleo),
            weekly_sales NUMERIC(15,2),
            fuel_price NUMERIC(10,3),
            temperature NUMERIC(10,2),
            cpi NUMERIC(10,3),
            unemployment NUMERIC(10,3)
        );
        """))
        conn.commit()
        print("Tablas creadas correctamente.")

# =====================================================
# ETL
# =====================================================

def ejecutar_etl():
    print("=" * 60)
    print("INICIANDO ETL")
    print("=" * 60)

    if not os.path.exists(RUTA_CSV_ORIGINAL):
        print("Archivo no encontrado")
        return

    # --- EXTRACCION ---
    df = pd.read_csv(RUTA_CSV_ORIGINAL)
    print(f"Filas originales extraídas: {len(df)}")

    # --- LIMPIEZA ---
    df.columns = df.columns.str.lower()
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
    df.drop_duplicates(inplace=True)
    df.dropna(inplace=True)
    df["holiday_flag"] = df["holiday_flag"].replace({0: False, 1: True}).astype(bool)

    # --- TIEMPO ---
    df["semana"] = df["date"].dt.isocalendar().week
    df["mes"] = df["date"].dt.month
    df["nombre_mes"] = df["date"].dt.month_name()
    df["trimestre"] = df["date"].dt.quarter
    # MEJORA 2: Cálculo de semestre
    df["semestre"] = ((df["mes"] - 1) // 6) + 1
    df["anio"] = df["date"].dt.year

    # --- CLIMA ---
    df["categoria_clima"] = df["temperature"].apply(clasificar_clima)

    # --- COMBUSTIBLE ---
    fuel_p33 = df["fuel_price"].quantile(0.33)
    fuel_p66 = df["fuel_price"].quantile(0.66)
    df["categoria_combustible"] = df["fuel_price"].apply(
        lambda x: clasificar_por_percentiles(x, fuel_p33, fuel_p66)
    )

    # --- CPI ---
    cpi_p33 = df["cpi"].quantile(0.33)
    cpi_p66 = df["cpi"].quantile(0.66)
    df["nivel_cpi"] = df["cpi"].apply(
        lambda x: clasificar_por_percentiles(x, cpi_p33, cpi_p66)
    )

    # --- DESEMPLEO ---
    des_p33 = df["unemployment"].quantile(0.33)
    des_p66 = df["unemployment"].quantile(0.66)
    df["nivel_desempleo"] = df["unemployment"].apply(
        lambda x: clasificar_por_percentiles(x, des_p33, des_p66)
    )

    # --- DIMENSION TIENDA ---
    ventas_tienda = df.groupby("store")["weekly_sales"].mean().reset_index()
    ventas_p33 = ventas_tienda["weekly_sales"].quantile(0.33)
    ventas_p66 = ventas_tienda["weekly_sales"].quantile(0.66)
    ventas_tienda["categoria_rendimiento"] = ventas_tienda["weekly_sales"].apply(
        lambda x: clasificar_por_percentiles(x, ventas_p33, ventas_p66)
    )
    ventas_tienda.rename(columns={"weekly_sales": "ventas_promedio"}, inplace=True)

    # MEJORA 1: Resiliencia
    resiliencia = (
        df.groupby("store")
        .agg({
            "weekly_sales": "mean",
            "unemployment": "mean",
            "cpi": "mean"
        })
        .reset_index()
    )

    resiliencia["indice_resiliencia"] = (
        resiliencia["weekly_sales"] /
        (resiliencia["unemployment"] * resiliencia["cpi"])
    )

    r33 = resiliencia["indice_resiliencia"].quantile(0.33)
    r66 = resiliencia["indice_resiliencia"].quantile(0.66)

    resiliencia["categoria_resiliencia"] = (
        resiliencia["indice_resiliencia"].apply(
            lambda x: clasificar_por_percentiles(x, r33, r66)
        )
    )

    # =================================================
    # DIMENSIONES Y CLAVES SUBROGADAS
    # =================================================
    
    # MEJORA 2: Asegúrate de incluir el semestre en dim_tiempo
    dim_tiempo = df[[
        "date", "semana", "mes", "nombre_mes", "trimestre", "semestre", "anio", "holiday_flag"
    ]].drop_duplicates().reset_index(drop=True)
    dim_tiempo["id_tiempo"] = range(1, len(dim_tiempo) + 1)

    # MEJORA 1: Unión de tienda y resiliencia
    dim_tienda = ventas_tienda.merge(
        resiliencia[["store", "indice_resiliencia", "categoria_resiliencia"]],
        on="store"
    )
    dim_tienda["id_tienda"] = range(1, len(dim_tienda) + 1)

    dim_clima = df[["categoria_clima"]].drop_duplicates().reset_index(drop=True)
    dim_clima["id_clima"] = range(1, len(dim_clima) + 1)

    dim_combustible = df[["categoria_combustible"]].drop_duplicates().reset_index(drop=True)
    dim_combustible["id_combustible"] = range(1, len(dim_combustible) + 1)

    dim_cpi = df[["nivel_cpi"]].drop_duplicates().reset_index(drop=True)
    dim_cpi["id_cpi"] = range(1, len(dim_cpi) + 1)

    dim_desempleo = df[["nivel_desempleo"]].drop_duplicates().reset_index(drop=True)
    dim_desempleo["id_desempleo"] = range(1, len(dim_desempleo) + 1)

    # =================================================
    # FACT TABLE
    # =================================================
    fact = df.copy()
    
    # MEJORA 2: Hay que cruzar considerando el semestre también
    fact = fact.merge(
        dim_tiempo, 
        on=["date", "semana", "mes", "nombre_mes", "trimestre", "semestre", "anio", "holiday_flag"]
    )
    
    fact = fact.merge(dim_tienda[["store", "id_tienda"]], on="store")
    fact = fact.merge(dim_clima, on="categoria_clima")
    fact = fact.merge(dim_combustible, on="categoria_combustible")
    fact = fact.merge(dim_cpi, on="nivel_cpi")
    fact = fact.merge(dim_desempleo, on="nivel_desempleo")

    fact_ventas = fact[[
        "id_tiempo", "id_tienda", "id_clima", "id_combustible", 
        "id_cpi", "id_desempleo", "weekly_sales", "fuel_price", 
        "temperature", "cpi", "unemployment"
    ]]

    # =================================================
    # EXPORTAR CSV
    # =================================================
    dim_tiempo.to_csv("dim_tiempo.csv", index=False)
    dim_tienda.to_csv("dim_tienda.csv", index=False)
    dim_clima.to_csv("dim_clima.csv", index=False)
    dim_combustible.to_csv("dim_combustible.csv", index=False)
    dim_cpi.to_csv("dim_cpi.csv", index=False)
    dim_desempleo.to_csv("dim_desempleo.csv", index=False)
    fact_ventas.to_csv("fact_ventas.csv", index=False)
    print("CSV exportados correctamente")

    # =================================================
    # CARGA
    # =================================================
    crear_tablas()

    print("Cargando datos en Supabase...")
    dim_tiempo.to_sql("dim_tiempo", engine, if_exists="append", index=False)
    dim_tienda.to_sql("dim_tienda", engine, if_exists="append", index=False)
    dim_clima.to_sql("dim_clima", engine, if_exists="append", index=False)
    dim_combustible.to_sql("dim_combustible", engine, if_exists="append", index=False)
    dim_cpi.to_sql("dim_cpi", engine, if_exists="append", index=False)
    dim_desempleo.to_sql("dim_desempleo", engine, if_exists="append", index=False)
    fact_ventas.to_sql("fact_ventas", engine, if_exists="append", index=False)

    print("Datos cargados correctamente en Supabase")
    print("ETL FINALIZADO CORRECTAMENTE")

# =====================================================
# MAIN
# =====================================================
if __name__ == "__main__":
    ejecutar_etl()