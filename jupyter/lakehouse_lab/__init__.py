"""
lakehouse_lab — conexões pré-configuradas para o laboratório de Data Lakehouse.

Uso básico:

    import lakehouse_lab as lh

    lh.query("SELECT * FROM lakehouse.gold.sales_by_day")   # -> DataFrame do pandas
    lh.run_sql("CREATE SCHEMA IF NOT EXISTS lakehouse.bronze ...")  # DDL/CTAS sem retorno
    lh.list_layer("bronze")                                  # lista arquivos da camada
    lh.s3()                                                   # cliente boto3 pronto
    lh.s3_storage_options()                                   # dict p/ pandas.to_parquet(..., storage_options=...)
    lh.bucket()                                                # nome do bucket do lakehouse
    lh.postgres()                                             # engine SQLAlchemy da fonte (já no schema "schema")
    lh.bronze_path("customers")                                # s3://lakehouse/bronze/customers/customers.parquet
    lh.silver_path("sales")                                    # idem, camada silver
    lh.gold_path("sales_by_day")                               # idem, camada gold

Não é preciso configurar host, porta, usuário ou senha de nada — tudo
já vem das variáveis de ambiente definidas no docker-compose.
"""
import os

import boto3
import pandas as pd
import trino
from sqlalchemy import create_engine

_TRINO_HOST = os.environ.get("LAKEHOUSE_TRINO_HOST", "trino")
_TRINO_PORT = int(os.environ.get("LAKEHOUSE_TRINO_PORT", "8080"))

_S3_ENDPOINT = os.environ.get("LAKEHOUSE_S3_ENDPOINT", "http://minio:9000")
_S3_ACCESS_KEY = os.environ.get("LAKEHOUSE_S3_ACCESS_KEY", "trilha")
_S3_SECRET_KEY = os.environ.get("LAKEHOUSE_S3_SECRET_KEY", "trilha123")
_S3_BUCKET = os.environ.get("LAKEHOUSE_S3_BUCKET", "lakehouse")

_PG_HOST = os.environ.get("LAKEHOUSE_PG_HOST", "postgres")
_PG_USER = os.environ.get("LAKEHOUSE_PG_USER", "trilha")
_PG_PASSWORD = os.environ.get("LAKEHOUSE_PG_PASSWORD", "trilha123")
_PG_DB = os.environ.get("LAKEHOUSE_PG_DB", "database")
_PG_SCHEMA = os.environ.get("LAKEHOUSE_PG_SCHEMA", "schema")

BRONZE = "bronze"
SILVER = "silver"
GOLD = "gold"


def trino_connection(catalog: str = "lakehouse"):
    """Conexão DBAPI crua com o Trino. Catalogs disponíveis: 'lakehouse' e 'postgres'."""
    return trino.dbapi.connect(host=_TRINO_HOST, port=_TRINO_PORT, user="student", catalog=catalog)


def query(sql: str, catalog: str = "lakehouse") -> pd.DataFrame:
    """Executa um SQL no Trino e devolve o resultado como DataFrame do pandas."""
    conn = trino_connection(catalog=catalog)
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    columns = [c[0] for c in cur.description]
    return pd.DataFrame(rows, columns=columns)


def run_sql(*statements: str, catalog: str = "lakehouse") -> None:
    """Executa um ou mais comandos SQL no Trino sem se importar com o retorno.

    Útil para DDL (CREATE SCHEMA/TABLE, DROP TABLE) e para CTAS
    (CREATE TABLE ... AS SELECT) — o jeito como as camadas silver e
    gold são construídas neste laboratório.
    """
    conn = trino_connection(catalog=catalog)
    cur = conn.cursor()
    for stmt in statements:
        cur.execute(stmt)
        cur.fetchall()  # Trino é assíncrono; isso garante que o statement termina


def s3():
    """Cliente boto3 já apontado para o MinIO."""
    return boto3.client(
        "s3",
        endpoint_url=_S3_ENDPOINT,
        aws_access_key_id=_S3_ACCESS_KEY,
        aws_secret_access_key=_S3_SECRET_KEY,
    )


def s3_storage_options() -> dict:
    """Dict pronto para `DataFrame.to_parquet(..., storage_options=...)` gravar no MinIO."""
    return {
        "key": _S3_ACCESS_KEY,
        "secret": _S3_SECRET_KEY,
        "client_kwargs": {"endpoint_url": _S3_ENDPOINT},
    }


def bucket() -> str:
    """Nome do bucket S3 usado pelo lakehouse."""
    return _S3_BUCKET


def list_layer(layer: str, prefix: str = "") -> list:
    """Lista os objetos de uma camada do lakehouse (bronze, silver ou gold)."""
    client = s3()
    resp = client.list_objects_v2(Bucket=_S3_BUCKET, Prefix=f"{layer}/{prefix}")
    return [obj["Key"] for obj in resp.get("Contents", [])]


def postgres():
    """Engine SQLAlchemy para o Postgres 'fonte' (sistema transacional simulado).

    Já conecta com o `search_path` apontando para o schema do projeto
    (`schema` por padrão — ver `pg_schema()`), então `pd.read_sql("SELECT
    * FROM orders", ...)` e `pd.read_sql_table("orders", ...)` funcionam
    sem precisar qualificar o schema.
    """
    url = f"postgresql+psycopg2://{_PG_USER}:{_PG_PASSWORD}@{_PG_HOST}:5432/{_PG_DB}"
    return create_engine(url, connect_args={"options": f"-csearch_path={_PG_SCHEMA}"})


def pg_schema() -> str:
    """Nome do schema do Postgres onde vivem as tabelas da fonte (padrão: 'schema')."""
    return _PG_SCHEMA


def _layer_path(layer: str, tabela: str = "") -> str:
    if not tabela:
        return f"s3://{_S3_BUCKET}/{layer}/"
    return f"s3://{_S3_BUCKET}/{layer}/{tabela}/{tabela}.parquet"


def bronze_path(tabela: str = "") -> str:
    """Caminho s3:// pronto pra gravar/ler um Parquet na camada bronze.

    Sem argumento, devolve só o prefixo da camada. Com o nome de uma
    tabela, devolve o caminho completo do arquivo:
    `s3://<bucket>/bronze/<tabela>/<tabela>.parquet`.
    """
    return _layer_path(BRONZE, tabela)


def silver_path(tabela: str = "") -> str:
    """Equivalente a `bronze_path`, para a camada silver."""
    return _layer_path(SILVER, tabela)


def gold_path(tabela: str = "") -> str:
    """Equivalente a `bronze_path`, para a camada gold."""
    return _layer_path(GOLD, tabela)
