-- =====================================================================
-- Dados de exemplo: um sistema transacional simulado de uma lojinha
-- online. Este é o "sistema fonte" que o Airflow vai extrair para a
-- camada bronze. Roda no banco padrão (${POSTGRES_DB} / database).
--
-- Tudo vive num schema próprio chamado "schema" (em vez do "public"
-- padrão) de propósito: assim o dbeaver-web e o lakehouse_lab já abrem
-- direto num único schema com só as 4 tabelas da aula, sem o aluno
-- precisar entender o que é "public" ou navegar pelos schemas de
-- sistema do Postgres. "SCHEMA" é uma palavra reservada em vários
-- outros bancos, mas não no Postgres nem no Trino — testado que
-- funciona sem aspas (`CREATE SCHEMA schema`, `SELECT ... FROM
-- schema.customers`) em ambos.
-- =====================================================================

CREATE SCHEMA schema;
SET search_path TO schema;

CREATE TABLE customers (
    customer_id   SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    email         TEXT NOT NULL,
    city          TEXT NOT NULL,
    state         TEXT NOT NULL,
    created_at    TIMESTAMP NOT NULL DEFAULT now()
);

CREATE TABLE products (
    product_id    SERIAL PRIMARY KEY,
    name          TEXT NOT NULL,
    category      TEXT NOT NULL,
    price         NUMERIC(10,2) NOT NULL
);

CREATE TABLE orders (
    order_id      SERIAL PRIMARY KEY,
    customer_id   INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date    DATE NOT NULL,
    status        TEXT NOT NULL
);

CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id      INTEGER NOT NULL REFERENCES orders(order_id),
    product_id    INTEGER NOT NULL REFERENCES products(product_id),
    quantity      INTEGER NOT NULL,
    unit_price    NUMERIC(10,2) NOT NULL
);

-- ---- clientes ----
INSERT INTO customers (name, email, city, state) VALUES
('Ana Beatriz Souza',  'ana.souza@example.com',      'São Paulo',       'SP'),
('Bruno Carvalho',     'bruno.carvalho@example.com', 'Rio de Janeiro',  'RJ'),
('Camila Ferreira',    'camila.ferreira@example.com','Belo Horizonte',  'MG'),
('Diego Martins',      'diego.martins@example.com',  'Curitiba',        'PR'),
('Elisa Rocha',        'elisa.rocha@example.com',    'Porto Alegre',    'RS'),
('Felipe Nogueira',    'felipe.nogueira@example.com','Salvador',        'BA'),
('Gabriela Lima',      'gabriela.lima@example.com',  'Recife',          'PE'),
('Henrique Alves',     'henrique.alves@example.com', 'Fortaleza',       'CE'),
('Isabela Ramos',      'isabela.ramos@example.com',  'Brasília',        'DF'),
('João Pedro Dias',    'joao.dias@example.com',      'Manaus',          'AM'),
('Karina Barbosa',     'karina.barbosa@example.com', 'São Paulo',       'SP'),
('Lucas Teixeira',     'lucas.teixeira@example.com', 'Rio de Janeiro',  'RJ'),
('Mariana Gomes',      'mariana.gomes@example.com',  'Belo Horizonte',  'MG'),
('Nicolas Pereira',    'nicolas.pereira@example.com','Curitiba',        'PR'),
('Olivia Cardoso',     'olivia.cardoso@example.com', 'Porto Alegre',    'RS');

-- ---- produtos ----
INSERT INTO products (name, category, price) VALUES
('Fone de Ouvido Bluetooth', 'Eletrônicos', 129.90),
('Teclado Mecânico',         'Eletrônicos', 249.90),
('Mouse Sem Fio',            'Eletrônicos',  79.90),
('Monitor 24"',              'Eletrônicos', 899.00),
('Cadeira de Escritório',    'Móveis',      649.00),
('Mesa Ajustável',           'Móveis',      899.90),
('Garrafa Térmica',          'Casa',         59.90),
('Luminária de Mesa',        'Casa',         89.90),
('Caderno Inteligente',      'Papelaria',    69.90),
('Caneta Premium',           'Papelaria',    39.90),
('Mochila para Notebook',    'Acessórios',  199.90),
('Suporte para Notebook',    'Acessórios',   99.90);

-- ---- pedidos (últimos ~45 dias, para dar variação de datas na camada gold) ----
INSERT INTO orders (customer_id, order_date, status) VALUES
(1,  CURRENT_DATE - 44, 'concluido'),
(2,  CURRENT_DATE - 43, 'concluido'),
(3,  CURRENT_DATE - 41, 'concluido'),
(4,  CURRENT_DATE - 40, 'cancelado'),
(5,  CURRENT_DATE - 38, 'concluido'),
(6,  CURRENT_DATE - 37, 'concluido'),
(7,  CURRENT_DATE - 35, 'concluido'),
(8,  CURRENT_DATE - 33, 'concluido'),
(9,  CURRENT_DATE - 31, 'concluido'),
(10, CURRENT_DATE - 30, 'concluido'),
(1,  CURRENT_DATE - 28, 'concluido'),
(2,  CURRENT_DATE - 27, 'concluido'),
(11, CURRENT_DATE - 25, 'concluido'),
(12, CURRENT_DATE - 24, 'cancelado'),
(13, CURRENT_DATE - 22, 'concluido'),
(3,  CURRENT_DATE - 20, 'concluido'),
(14, CURRENT_DATE - 19, 'concluido'),
(15, CURRENT_DATE - 17, 'concluido'),
(4,  CURRENT_DATE - 15, 'concluido'),
(5,  CURRENT_DATE - 14, 'concluido'),
(6,  CURRENT_DATE - 12, 'concluido'),
(7,  CURRENT_DATE - 10, 'concluido'),
(8,  CURRENT_DATE - 9,  'concluido'),
(9,  CURRENT_DATE - 7,  'concluido'),
(10, CURRENT_DATE - 6,  'concluido'),
(11, CURRENT_DATE - 4,  'concluido'),
(12, CURRENT_DATE - 3,  'concluido'),
(13, CURRENT_DATE - 2,  'concluido'),
(14, CURRENT_DATE - 1,  'concluido'),
(15, CURRENT_DATE,      'concluido');

-- ---- itens de pedido (2 a 3 itens por pedido) ----
INSERT INTO order_items (order_id, product_id, quantity, unit_price) VALUES
(1, 1, 1, 129.90), (1, 3, 2, 79.90),
(2, 4, 1, 899.00),
(3, 5, 1, 649.00), (3, 8, 1, 89.90),
(4, 2, 1, 249.90),
(5, 6, 1, 899.90), (5, 7, 2, 59.90),
(6, 9, 3, 69.90),
(7, 11, 1, 199.90), (7, 12, 1, 99.90),
(8, 1, 2, 129.90),
(9, 10, 4, 39.90),
(10, 4, 1, 899.00), (10, 3, 1, 79.90),
(11, 2, 1, 249.90),
(12, 5, 1, 649.00),
(13, 7, 3, 59.90),
(14, 6, 1, 899.90),
(15, 9, 2, 69.90), (15, 10, 2, 39.90),
(16, 1, 1, 129.90),
(17, 12, 2, 99.90),
(18, 11, 1, 199.90),
(19, 4, 1, 899.00),
(20, 8, 2, 89.90),
(21, 3, 3, 79.90),
(22, 2, 1, 249.90), (22, 1, 1, 129.90),
(23, 5, 1, 649.00),
(24, 6, 1, 899.90),
(25, 7, 1, 59.90),
(26, 9, 1, 69.90),
(27, 10, 3, 39.90),
(28, 11, 1, 199.90),
(29, 4, 1, 899.00), (29, 12, 1, 99.90),
(30, 1, 2, 129.90);
