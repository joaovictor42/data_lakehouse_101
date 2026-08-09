#!/bin/sh
# Cria o bucket do lakehouse e um marcador em cada pasta (landing,
# bronze, silver, gold) para elas já aparecerem no console do MinIO
# assim que o ambiente sobe, mesmo sem nenhum dado ainda.
#
# "landing" é diferente das outras três: bronze/silver/gold são
# construídas sozinhas pelo pipeline-init (ver trino/init/
# construir_pipeline.py) — landing não. Ninguém escreve nela
# automaticamente; é uma zona de pouso pra arquivo cru que o aluno traz
# de fora (`lh.upload_to_landing(...)`) e depois "captura" pro lakehouse
# na mão (`lh.read_landing(...)` + `lh.write_table(...)`) — ver
# lakehouse_kit. Criada vazia aqui só pra já aparecer no console, do
# mesmo jeito que as outras três.
#
# Sem pasta "warehouse/" aqui de propósito: nenhuma célula dos notebooks
# escreve lá, porque toda CREATE SCHEMA no projeto já define sua própria
# location (bronze/, silver/, gold/). O Hive Metastore continua
# configurado com um HIVE_METASTORE_WAREHOUSE_DIR (no docker-compose.yml)
# como default de segurança para schemas/tabelas criados sem location
# explícita — só não pré-criamos essa pasta vazia, já que ela nunca é
# usada no fluxo normal da aula.
set -e

mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD"
mc mb -p "local/$MINIO_BUCKET"

echo "camada criada pelo laboratório" > /tmp/.keep
for pasta in landing bronze silver gold; do
  mc cp /tmp/.keep "local/$MINIO_BUCKET/$pasta/.keep"
done

echo "MinIO inicializado: bucket '$MINIO_BUCKET' com landing/bronze/silver/gold."
