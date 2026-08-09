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
from decimal import Decimal

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
# bronze/<tabela>/<tabela>.parquet.

TABELAS_FONTE = ["customers", "products", "orders", "order_items"]

engine = lh.postgres()

for tabela in TABELAS_FONTE:
    df = pd.read_sql_table(tabela, engine)

    # Colunas NUMERIC do Postgres chegam como Decimal. O Parquet gravaria
    # isso como DECIMAL de precisão fixa, mas as tabelas bronze abaixo
    # esperam DOUBLE — então convertemos aqui. É um tipo de "atrito" bem
    # real de lakehouse: os tipos precisam bater em cada camada.
    for coluna in df.columns:
        if df[coluna].map(type).eq(Decimal).any():
            df[coluna] = df[coluna].astype(float)

    # O mesmo atrito acontece com DATE: o pandas guarda como datetime64
    # (timestamp completo), e o Parquet gravaria como TIMESTAMP — mas
    # declaramos DATE lá embaixo. Convertendo para date "puro" aqui, o
    # Parquet grava o tipo DATE de verdade.
    for coluna in df.columns:
        if coluna.endswith("_date") and pd.api.types.is_datetime64_any_dtype(df[coluna]):
            df[coluna] = df[coluna].dt.date

    destino = lh.bronze_path(tabela)
    df.to_parquet(destino, storage_options=lh.s3_storage_options(), index=False)
    print(f"[bronze] {tabela}: {len(df)} linhas -> {destino}")

# ---------------------------------------------------------------
# 3. Registrando a bronze no catálogo do Trino
# ---------------------------------------------------------------
# Os arquivos já estão no MinIO, mas o Trino ainda não sabe que eles
# existem. O Hive Metastore precisa de um CREATE TABLE dizendo onde
# estão os arquivos e qual o schema de cada coluna.

BRONZE_SCHEMAS = {
    "customers": "customer_id INTEGER, name VARCHAR, email VARCHAR, city VARCHAR, state VARCHAR, created_at TIMESTAMP",
    "products": "product_id INTEGER, name VARCHAR, category VARCHAR, price DOUBLE",
    "orders": "order_id INTEGER, customer_id INTEGER, order_date DATE, status VARCHAR",
    "order_items": "order_item_id INTEGER, order_id INTEGER, product_id INTEGER, quantity INTEGER, unit_price DOUBLE",
}

lh.run_sql(f"CREATE SCHEMA IF NOT EXISTS lakehouse.bronze WITH (location = 's3://{lh.bucket()}/bronze/')")

for tabela, colunas in BRONZE_SCHEMAS.items():
    location = f"s3://{lh.bucket()}/bronze/{tabela}/"
    lh.run_sql(
        f"DROP TABLE IF EXISTS lakehouse.bronze.{tabela}",
        f"CREATE TABLE lakehouse.bronze.{tabela} ({colunas}) WITH (external_location = '{location}', format = 'PARQUET')",
    )
    print(f"[bronze] tabela registrada: lakehouse.bronze.{tabela}")

# ---------------------------------------------------------------
# 4. Camada Silver — join limpo
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
# 5. Camada Gold — agregados prontos para consumo
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
