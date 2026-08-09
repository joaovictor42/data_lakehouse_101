#!/usr/bin/env python3
"""
Constrói o pipeline bronze -> silver -> gold do zero.

Isso já foi um notebook (`01_construir_pipeline.ipynb`), rodado célula a
célula pelo aluno. Virou script de infraestrutura, no mesmo espírito de
`postgres/init/*.sql`: código que prepara o ambiente antes da aula, não
algo que o aluno edita ou reexecuta célula a célula. Roda sozinho, uma
vez, via o serviço `pipeline-init` do docker-compose.yml, assim que
Postgres/MinIO/Trino ficam prontos — ver README, "Por que o pipeline
roda sozinho".

Idempotente: pode rodar quantas vezes quiser — cada tabela é sempre
recriada do zero (DROP + CREATE), então é seguro repetir depois de
inserir dados novos no Postgres.

Pra rodar de novo na mão (ex: depois de inserir uma linha nova em
orders/order_items via `lh.postgres()` e querer atualizar o lakehouse
sem esperar o próximo `docker compose up`), de dentro do Jupyter — este
arquivo está montado lá em /home/jovyan/trino-init/ (oculto do
navegador de arquivos do JupyterLab de propósito, mas acessível
normalmente por comandos, já que isso é feito pelo lado do kernel/SO,
não pela API de arquivos do Jupyter — ver README):
    - Terminal do JupyterLab: python /home/jovyan/trino-init/construir_pipeline.py
    - Célula de notebook:     !python /home/jovyan/trino-init/construir_pipeline.py
"""
import lakehouse_kit as lh
import pandas as pd

# ---------------------------------------------------------------
# 1. A fonte: um sistema transacional simulado
# ---------------------------------------------------------------
# O Postgres tem 4 tabelas de uma lojinha (customers, products, orders,
# order_items), já populadas com dados de exemplo. É daqui que tudo
# começa.

# ---------------------------------------------------------------
# 2. Camada Bronze — extração crua
# ---------------------------------------------------------------
# Bronze não transforma nada: é uma cópia fiel do que existe na fonte,
# em Parquet, dentro do MinIO. Cada tabela vira um arquivo em
# bronze/<tabela>/<tabela>.parquet, e fica cadastrada no Trino em
# lakehouse.bronze.<tabela> — tudo isso é o que `lh.write_table` faz
# (ver jupyter/notebooks/lakehouse_kit/__init__.py); aqui só declaramos
# o schema de cada tabela na mão (`colunas_sql`) em vez de deixar
# `write_table` adivinhar os tipos, pra ter DATE de verdade em vez de
# TIMESTAMP (ver conversão de `order_date` abaixo) e não depender de
# inferência automática numa tabela que faz parte da infraestrutura.

TABELAS_FONTE = ["customers", "products", "orders", "order_items"]

BRONZE_SCHEMAS = {
    "customers": "customer_id INTEGER, name VARCHAR, email VARCHAR, city VARCHAR, state VARCHAR, created_at TIMESTAMP",
    "products": "product_id INTEGER, name VARCHAR, category VARCHAR, price DOUBLE",
    "orders": "order_id INTEGER, customer_id INTEGER, order_date DATE, status VARCHAR",
    "order_items": "order_item_id INTEGER, order_id INTEGER, product_id INTEGER, quantity INTEGER, unit_price DOUBLE",
}

engine = lh.postgres()

for tabela in TABELAS_FONTE:
    df = pd.read_sql_table(tabela, engine)

    # `write_table` já converte Decimal -> float sozinho (Postgres NUMERIC
    # chega como Decimal, e o Parquet não lida bem com isso), mas o
    # atrito de DATE não dá pra automatizar: o pandas guarda datas como
    # datetime64 (timestamp completo), e o Parquet gravaria como
    # TIMESTAMP — só convertendo pra date "puro" aqui é que o Parquet
    # grava DATE de verdade, batendo com o schema declarado acima.
    for coluna in df.columns:
        if coluna.endswith("_date") and pd.api.types.is_datetime64_any_dtype(df[coluna]):
            df[coluna] = df[coluna].dt.date

    lh.write_table(df, "bronze", tabela, colunas_sql=BRONZE_SCHEMAS[tabela])
    print(f"[bronze] {tabela}: {len(df)} linhas -> lakehouse.bronze.{tabela}")

# ---------------------------------------------------------------
# 3. Camada Silver — join limpo
# ---------------------------------------------------------------
# Um único modelo de vendas, juntando pedidos + itens + produtos +
# clientes. A partir daqui, ninguém mais precisa saber que existem 4
# tabelas separadas na fonte.

lh.run_sql(f"CREATE SCHEMA IF NOT EXISTS lakehouse.silver WITH (location = 's3://{lh.bucket()}/silver/')")
lh.run_sql("DROP TABLE IF EXISTS lakehouse.silver.sales")
lh.run_sql(
    """
    CREATE TABLE lakehouse.silver.sales
    WITH (format = 'PARQUET')
    AS SELECT
        o.order_id,
        o.order_date,
        o.status,
        c.customer_id,
        c.name        AS customer_name,
        c.city        AS customer_city,
        c.state       AS customer_state,
        p.product_id,
        p.name        AS product_name,
        p.category    AS product_category,
        oi.quantity,
        oi.unit_price,
        oi.quantity * oi.unit_price AS item_total
    FROM lakehouse.bronze.order_items oi
    JOIN lakehouse.bronze.orders o     ON oi.order_id = o.order_id
    JOIN lakehouse.bronze.products p   ON oi.product_id = p.product_id
    JOIN lakehouse.bronze.customers c  ON o.customer_id = c.customer_id
    WHERE o.status = 'concluido'
    """
)
print("[silver] lakehouse.silver.sales construída")

# ---------------------------------------------------------------
# 4. Camada Gold — agregados prontos para consumo
# ---------------------------------------------------------------

lh.run_sql(f"CREATE SCHEMA IF NOT EXISTS lakehouse.gold WITH (location = 's3://{lh.bucket()}/gold/')")

lh.run_sql("DROP TABLE IF EXISTS lakehouse.gold.sales_by_day")
lh.run_sql(
    """
    CREATE TABLE lakehouse.gold.sales_by_day
    WITH (format = 'PARQUET')
    AS SELECT
        order_date,
        COUNT(DISTINCT order_id) AS num_pedidos,
        SUM(item_total)          AS receita
    FROM lakehouse.silver.sales
    GROUP BY order_date
    ORDER BY order_date
    """
)
print("[gold] lakehouse.gold.sales_by_day construída")

lh.run_sql("DROP TABLE IF EXISTS lakehouse.gold.sales_by_category")
lh.run_sql(
    """
    CREATE TABLE lakehouse.gold.sales_by_category
    WITH (format = 'PARQUET')
    AS SELECT
        product_category,
        SUM(quantity)    AS unidades_vendidas,
        SUM(item_total)  AS receita
    FROM lakehouse.silver.sales
    GROUP BY product_category
    ORDER BY receita DESC
    """
)
print("[gold] lakehouse.gold.sales_by_category construída")

print("Pipeline concluído: bronze, silver e gold prontos em lakehouse.*")
