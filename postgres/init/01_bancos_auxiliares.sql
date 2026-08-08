-- Bancos auxiliares usados pela infraestrutura do lab.
-- O banco principal (${POSTGRES_DB}, ex: database) já é criado
-- automaticamente pela imagem oficial do Postgres.

CREATE DATABASE metastore_db;  -- metadados do Hive Metastore (catálogo do Trino)
