"""
lakehouse_kit — conexões pré-configuradas para o laboratório de Data Lakehouse.

Este é o código-fonte real do pacote, exposto de propósito dentro de
`notebooks/` (em vez de instalado "escondido" em outro lugar da imagem):
o aluno pode abrir, ler e editar `lakehouse_kit/__init__.py` no próprio
JupyterLab — mudou algo aqui, é só rodar de novo a célula com o
`import` (ou reiniciar o kernel) para pegar a mudança.

Uso básico:

    import lakehouse_kit as lh

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

Duas formas bem diferentes de "ler dado", que não devem ser confundidas:

    lh.query("SELECT ...")          # via Trino: só enxerga o que já foi CATALOGADO
    lh.read_table("bronze", "x")    # via pandas direto no MinIO: lê o Parquet cru,
                                     # mesmo que ninguém tenha registrado tabela nenhuma

E o par que fecha o ciclo — construir uma camada da arquitetura medalhão
"na mão", sem precisar saber a sintaxe de `CREATE TABLE ... WITH
(external_location = ...)` do Trino:

    df = lh.postgres() ... # ou um CSV, uma API, outra tabela via lh.query(...)
    lh.write_table(df, "bronze", "minha_tabela")   # grava Parquet no MinIO
                                                    # + cadastra no Trino
    lh.query("SELECT * FROM lakehouse.bronze.minha_tabela")  # já funciona
    lh.drop_table("bronze", "minha_tabela")        # desfaz (tabela + arquivos)

Não é preciso configurar host, porta, usuário ou senha de nada — tudo
já vem das variáveis de ambiente definidas no docker-compose.
"""
import os
from datetime import date, datetime
from decimal import Decimal

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


def trino_connection():
    """Conexão DBAPI crua com o Trino, já no catálogo "lakehouse" (o único que existe —
    o Trino deste laboratório não enxerga o Postgres "fonte", de propósito).
    """
    return trino.dbapi.connect(host=_TRINO_HOST, port=_TRINO_PORT, user="student", catalog="lakehouse")


def query(sql: str) -> pd.DataFrame:
    """Executa um SQL no Trino (catálogo "lakehouse") e devolve o resultado como DataFrame do pandas."""
    conn = trino_connection()
    cur = conn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    columns = [c[0] for c in cur.description]
    return pd.DataFrame(rows, columns=columns)


def run_sql(*statements: str) -> None:
    """Executa um ou mais comandos SQL no Trino (catálogo "lakehouse") sem se importar com o retorno.

    Útil para DDL (CREATE SCHEMA/TABLE, DROP TABLE) e para CTAS
    (CREATE TABLE ... AS SELECT) — o jeito como as camadas silver e
    gold são construídas neste laboratório.
    """
    conn = trino_connection()
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


# ---------------------------------------------------------------------
# Ler/escrever tabelas inteiras, direto no MinIO — o par que fecha o
# ciclo da arquitetura medalhão sem precisar escrever `CREATE TABLE ...
# WITH (external_location = ...)` na mão. `lh.query(...)` (lá em cima)
# é outra coisa: passa pelo Trino, então só enxerga o que já foi
# cadastrado no catálogo por um `write_table` (ou pelo pipeline).
# ---------------------------------------------------------------------


def read_table(layer: str, tabela: str) -> pd.DataFrame:
    """Lê o Parquet de uma tabela direto do MinIO com pandas — sem passar pelo Trino.

    Diferença pra `lh.query("SELECT * FROM lakehouse.<layer>.<tabela>")`:
    aqui não importa se a tabela já foi cadastrada no catálogo do Trino
    ou não, só se o arquivo existe no MinIO. Serve pra inspecionar o
    resultado de um `write_table` antes/depois de cadastrar, ou só pra
    comparar as duas formas de ler o mesmo dado.
    """
    return pd.read_parquet(_layer_path(layer, tabela), storage_options=s3_storage_options())


def _tipo_trino(coluna: pd.Series) -> str:
    """Adivinha o tipo Trino/Hive de uma coluna a partir do dtype do pandas.

    Cobre os casos comuns de um DataFrame "normal": inteiro -> BIGINT,
    float -> DOUBLE, bool -> BOOLEAN, datetime64 -> TIMESTAMP, coluna de
    objetos `datetime.date` (não `datetime.datetime`) -> DATE, e tudo o
    resto -> VARCHAR. Pra qualquer coisa mais específica (DECIMAL,
    tipos exatos), declare a coluna na mão via o parâmetro `colunas_sql`
    de `write_table` — isto aqui é só um atalho pros casos simples.
    """
    if pd.api.types.is_bool_dtype(coluna):
        return "BOOLEAN"
    if pd.api.types.is_integer_dtype(coluna):
        return "BIGINT"
    if pd.api.types.is_float_dtype(coluna):
        return "DOUBLE"
    if pd.api.types.is_datetime64_any_dtype(coluna):
        return "TIMESTAMP"
    if coluna.dtype == object and coluna.notna().any():
        primeiro_valor = coluna.dropna().iloc[0]
        if isinstance(primeiro_valor, date) and not isinstance(primeiro_valor, datetime):
            return "DATE"
    return "VARCHAR"


def _inferir_colunas_sql(df: pd.DataFrame) -> str:
    return ", ".join(f"{coluna} {_tipo_trino(df[coluna])}" for coluna in df.columns)


def write_table(df: pd.DataFrame, layer: str, tabela: str, colunas_sql: str = None) -> None:
    """Grava um DataFrame como Parquet numa camada do lakehouse (MinIO) e
    (re)cadastra a tabela no catálogo do Trino — pronta pra `lh.query(...)`
    logo em seguida.

    É assim que se constrói uma camada da arquitetura medalhão "na mão":
    lê de uma origem qualquer (`lh.postgres()`, um CSV, uma API, outra
    tabela via `lh.query(...)`...), transforma com pandas à vontade, e
    chama:

        lh.write_table(df, "bronze", "minha_tabela")

    `layer` normalmente é "bronze", "silver" ou "gold", mas pode ser
    qualquer nome — vira o schema `lakehouse.<layer>` no Trino e o
    prefixo `s3://<bucket>/<layer>/` no MinIO (criado automaticamente
    se ainda não existir).

    Os tipos das colunas são adivinhados a partir dos dtypes do
    DataFrame (ver `_tipo_trino`). Pra forçar tipos específicos, passe
    `colunas_sql` no mesmo formato de um `CREATE TABLE` do Trino, ex:
    `"id INTEGER, nome VARCHAR, preco DOUBLE"` — é o que o
    `trino/init/construir_pipeline.py` deste projeto faz pra bronze, em
    vez de depender da inferência automática.

    Sempre sobrescreve por completo (DROP + CREATE), mesmo se a tabela
    já existir de uma chamada anterior — mesmo comportamento idempotente
    do resto do pipeline deste projeto, então rodar de novo depois de
    mudar o DataFrame nunca dá erro de "tabela já existe".

    Colunas com valores `Decimal` (comum em leituras do Postgres via
    `lh.postgres()`) são convertidas pra float automaticamente — o
    Parquet não lida bem com o tipo Decimal do pandas.
    """
    df = df.copy()
    for coluna in df.columns:
        if df[coluna].map(type).eq(Decimal).any():
            df[coluna] = df[coluna].astype(float)

    destino = _layer_path(layer, tabela)
    df.to_parquet(destino, storage_options=s3_storage_options(), index=False)

    colunas = colunas_sql or _inferir_colunas_sql(df)
    location = f"s3://{_S3_BUCKET}/{layer}/{tabela}/"
    run_sql(f"CREATE SCHEMA IF NOT EXISTS lakehouse.{layer} WITH (location = 's3://{_S3_BUCKET}/{layer}/')")
    run_sql(
        f"DROP TABLE IF EXISTS lakehouse.{layer}.{tabela}",
        f"CREATE TABLE lakehouse.{layer}.{tabela} ({colunas}) WITH (external_location = '{location}', format = 'PARQUET')",
    )


def drop_table(layer: str, tabela: str, apagar_arquivos: bool = True) -> None:
    """Desfaz um `write_table`: remove a tabela do catálogo do Trino e,
    por padrão, também os arquivos Parquet dela no MinIO
    (`apagar_arquivos=False` pra tirar só do catálogo e manter os
    arquivos). Sem isso, um `DROP TABLE` sozinho deixaria o arquivo
    órfão no MinIO — o Trino esqueceria que ele existe, mas ele
    continuaria ocupando espaço lá.
    """
    run_sql(f"DROP TABLE IF EXISTS lakehouse.{layer}.{tabela}")
    if apagar_arquivos:
        client = s3()
        prefix = f"{layer}/{tabela}/"
        resp = client.list_objects_v2(Bucket=_S3_BUCKET, Prefix=prefix)
        for obj in resp.get("Contents", []):
            client.delete_object(Bucket=_S3_BUCKET, Key=obj["Key"])
