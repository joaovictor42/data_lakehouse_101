# Laboratório de Data Lakehouse

Ambiente completo e pré-conectado para a aula prática de engenharia de dados.
O aluno não precisa entender Docker — só rodar um comando e abrir o Jupyter.

Só armazenamento e consulta (Postgres, MinIO, Trino, Jupyter, DBeaver-web) — sem orquestrador. O pipeline bronze → silver → gold é construído por um script (`trino/init/construir_pipeline.py`) que roda sozinho, uma vez, assim que o ambiente sobe — no mesmo espírito de `postgres/init/*.sql`, mas para o Trino. Sem DAG nenhum escondendo o que está acontecendo: é um script comum, com o SQL/Python visível, que dá pra abrir e ler como texto, e rodar de novo na mão a qualquer momento (idempotente — cada tabela é sempre `DROP` + `CREATE`). O Jupyter entra depois, só pra explorar o que já foi construído: o notebook `explorando_o_lakehouse.ipynb` consulta e visualiza as camadas via SQL (Trino) e Python.

## Como subir

```bash
docker compose up -d --build
```

Primeira subida demora alguns minutos (baixa as imagens, builda o Jupyter, e roda o pipeline uma vez em background). O comando só devolve o prompt depois que tudo isso termina — inclusive o DBeaver-web (`dbeaver`) só sobe depois que as camadas bronze/silver/gold já existem, de propósito (ver `pipeline-init` no `docker-compose.yml`). Depois disso, tudo fica de pé até você rodar `docker compose down`.

## URLs e credenciais (tudo já vem pronto, ver `.env`)

Nenhum serviço pede credencial do aluno, com **uma única exceção**: o MinIO Console. É uma limitação do próprio MinIO, não deste projeto — o Console web dele sempre exige login, não existe modo anônimo pra essa UI (só dá pra desligar a UI inteira, o que tiraria o efeito visual de ver os arquivos aparecendo em `bronze/`/`silver`/`gold` — ver seção "Arquitetura" abaixo pra essa troca). Todo o resto (Jupyter, Trino UI, as duas conexões do DBeaver-web) abre direto, sem tela de login nenhuma.

| Serviço | URL | Usuário / senha |
|---|---|---|
| Jupyter | http://localhost:8888 | **nenhuma** — abre direto em `/lab` |
| Trino UI | http://localhost:8082 | **nenhuma** |
| DBeaver-web (CloudBeaver) | http://localhost:8978 | **nenhuma** — acesso anônimo, com 2 conexões já prontas: `postgres` (schema `schema`) e `trino` (catálogo `lakehouse`) |
| MinIO Console | http://localhost:9001 | `trilha` / `trilha123` *(única exceção — ver acima)* |
| Postgres | `localhost:5432` | `trilha` / `trilha123`, banco `database`, schema `schema` — só relevante se você conectar de fora com outra ferramenta; o Jupyter e o DBeaver-web já vêm conectados |

O login de administrador do DBeaver-web (`DBEAVER_ADMIN_USER` / `DBEAVER_ADMIN_PASSWORD` no `.env`) só existe para destravar a configuração inicial do CloudBeaver — o aluno nunca precisa dele, só o instrutor, se for mexer em algo em http://localhost:8978/#/admin.

> Como Jupyter e MinIO Console ficam sem exigir (ou quase sem exigir) login, **não exponha as portas deste projeto além da sua própria máquina** (ex: não coloque atrás de um proxy público, não abra as portas no firewall pra internet). Pra uma sala de aula local isso é seguro; pra qualquer coisa acessível de fora, não é.

## Roteiro sugerido para a aula

1. Suba o ambiente antes da aula começar (`docker compose up -d --build`) — assim o tempo de download/build (e a primeira rodada do pipeline) não consome tempo de aula. Quando o comando devolver o prompt, bronze/silver/gold já existem.
2. Mostre o Postgres (`database`, schema `schema`) como o "sistema transacional" de uma lojinha — é a fonte dos dados. Abra o **DBeaver-web** (http://localhost:8978) pra isso, na conexão **"postgres"**: já chega conectado direto no schema `schema`, sem login e sem outros schemas do Postgres poluindo a árvore — o aluno só vê as 4 tabelas que importam.
3. Abra `trino/init/construir_pipeline.py` (no editor de texto que preferir, ou dentro do Jupyter mesmo — o JupyterLab abre `.py` com destaque de sintaxe) e explique cada seção: extrair do Postgres → gravar bronze em Parquet no MinIO → registrar bronze no Trino → construir silver (join) → construir gold (agregados). É o mesmo código que já rodou sozinho quando o ambiente subiu.
4. Pra mostrar rodando *ao vivo* (o "aha" visual): abra o **MinIO Console** (http://localhost:9001) numa aba, e numa célula do Jupyter rode `!python /home/jovyan/trino-init/construir_pipeline.py` — como o script é idempotente (`DROP` + `CREATE` em cada tabela), rodar de novo não tem problema nenhum, e dá pra ver os arquivos reaparecendo em `bronze/`, `silver/`, `gold/` no MinIO Console enquanto o script roda.
5. Abra o notebook `explorando_o_lakehouse.ipynb` (http://localhost:8888) e mostre como o dado é consultado por SQL via Trino, sem os alunos precisarem saber onde/como ele está fisicamente guardado. Dá pra mostrar a mesma coisa no **DBeaver-web**, na conexão **"trino"** — chega direto no catálogo `lakehouse`, então `SELECT * FROM bronze.customers` já funciona sem qualificar nada.
6. Para mostrar o pipeline reagindo a dado novo: insira uma linha em `orders`/`order_items` via `lh.postgres()` (célula do notebook) e rode `!python /home/jovyan/trino-init/construir_pipeline.py` de novo — os alunos veem o `gold.sales_by_day` mudar.

## Arquitetura

```
Postgres (fonte simulada, schema "schema") ──┬───────────────────> DBeaver-web ("postgres")
                                              │
Postgres (metastore) ────────────────────────┼──> Hive Metastore ──┐
                                              │                     │
MinIO (armazenamento S3) ────────────────────┘                     ├─> Trino (SQL) ──> DBeaver-web ("trino")
                                                                     │
                             pipeline-init roda uma vez sozinho:     │
                                   bronze -> silver -> gold ─────────┤
                                                  │                  │
                                                  ▼                  │
                                Jupyter (lakehouse_lab: já conectado, roda de novo ao vivo)
```

- **MinIO**: armazenamento S3-compatível. As camadas bronze/silver/gold são pastas dentro de um único bucket `lakehouse`.
- **Hive Metastore**: registra, para o Trino, quais tabelas existem e onde estão os arquivos no MinIO — é o que transforma "arquivos soltos" em "tabelas consultáveis por SQL". Usa o Postgres como banco de metadados (peça de infraestrutura, não aparece na aula).
- **Trino**: motor de consulta SQL, com um único catálogo: `lakehouse` (as camadas bronze/silver/gold). De propósito sem um catálogo apontando pro Postgres "fonte" — ver "Por que o Trino não enxerga o Postgres" abaixo.
- **pipeline-init**: roda `trino/init/construir_pipeline.py` uma vez, sozinho, assim que Postgres/MinIO/Trino ficam prontos — é o que garante que bronze/silver/gold já existam antes do DBeaver-web ficar acessível. Não aparece na aula (é só infraestrutura); ver "Por que o pipeline roda sozinho" abaixo.
- **DBeaver-web (CloudBeaver)**: cliente SQL web pra inspecionar o Postgres e o Trino sem precisar instalar nada — abre sem login, com duas conexões já prontas: **"postgres"** (direto no schema `schema`) e **"trino"** (direto no catálogo `lakehouse`).
- **Jupyter**: onde a aula explora o que já foi construído. Pacote `lakehouse_lab` pré-instalado (`import lakehouse_lab as lh`) com todas as conexões prontas (Postgres, MinIO, Trino) e variáveis/atalhos para os caminhos das camadas (`lh.bronze_path(...)`, `lh.silver_path(...)`, `lh.gold_path(...)`). Um notebook:
  - `explorando_o_lakehouse.ipynb` — consulta e visualiza o que o pipeline construiu.
  - `trino/init/construir_pipeline.py` também fica acessível de dentro do Jupyter (montado, só leitura, em `/home/jovyan/trino-init/`) — dá pra ler o código-fonte ali, ou rodar de novo com `!python /home/jovyan/trino-init/construir_pipeline.py` numa célula.

### Por que o pipeline virou um script, não mais um notebook

Até uma versão anterior deste projeto, bronze → silver → gold era construído dentro de um notebook (`01_construir_pipeline.ipynb`) que o aluno abria e rodava célula a célula. Isso tinha um problema: **nada rodava até alguém lembrar de fazer isso manualmente** — até lá, o Trino só tinha os schemas de sistema (`default`, `information_schema`), e quem abrisse o DBeaver-web primeiro (um aluno curioso, por exemplo) via um ambiente vazio e confuso.

Agora `trino/init/construir_pipeline.py` é um script comum (mesmo código, sem as células/markdown do notebook), rodado uma vez pelo serviço `pipeline-init` assim que o ambiente sobe — no mesmo espírito de `postgres/init/*.sql` preparando o Postgres, mas para o Trino (que não tem um mecanismo de "rodar isso na primeira subida" embutido como o Postgres tem). Sendo um script, não tem "output de notebook" nenhum pra se preocupar em sujar — só os efeitos reais (arquivos no MinIO, tabelas no Trino/Hive Metastore). O `docker compose up -d --build` só termina depois que os dados já existem (o serviço `dbeaver` depende do `pipeline-init` terminar com sucesso).

Isso não tira a visibilidade do pipeline na aula: o script é idempotente (cada tabela é sempre `DROP` + `CREATE`), continua com o SQL/Python visível pra ler e explicar, e o instrutor roda ele de novo ao vivo — só que agora de dentro de uma célula do Jupyter (`!python /home/jovyan/trino-init/construir_pipeline.py`) ou do terminal do JupyterLab, em vez de célula por célula dentro de um notebook dedicado.

### Por que o explorador de arquivos do Jupyter só mostra o notebook

Duas coisas de propósito, pra reduzir o que o aluno vê sem precisar entender:

- **A pasta `work`** que a imagem base (`jupyter/scipy-notebook`) sempre inclui em `/home/jovyan/work` é removida no `Dockerfile` (`RUN rm -rf /home/jovyan/work`) — este projeto sempre monta `./jupyter/notebooks` ali, então ela nunca é usada; só ficaria vazia, confundindo quem abre o JupyterLab pela primeira vez.
- **A pasta `trino-init`** (onde `trino/init/construir_pipeline.py` fica montado, só leitura) é ocultada do explorador de arquivos e da API de conteúdo do Jupyter via `--ServerApp.root_dir=/home/jovyan/notebooks` no `command:` do serviço `jupyter` — isso restringe a raiz do que o Jupyter enxerga como "sistema de arquivos" a só a pasta `notebooks`, então nem `trino-init` nem nada mais em `/home/jovyan` (arquivos de configuração do Jupyter, etc.) aparece na árvore. Testado: isso é uma restrição só da API/UI do Jupyter, não do sistema operacional — comandos rodados por um kernel (`!python /home/jovyan/trino-init/construir_pipeline.py` numa célula, ou pelo terminal do JupyterLab) continuam acessando esse caminho normalmente, porque isso passa pelo processo do kernel/shell, não pela API de conteúdo restrita pelo `root_dir`.

Se um dia quiser voltar a ver tudo (por exemplo, pra debugar), tire o `--ServerApp.root_dir=...` do `command:` do serviço `jupyter` no `docker-compose.yml` e suba de novo (`docker compose up -d --build jupyter`).

### Por que um schema `schema` em vez do `public` padrão

As 4 tabelas da fonte (`customers`, `products`, `orders`, `order_items`) vivem no schema `schema` (criado em `postgres/init/02_dados_fonte.sql`), não no `public` padrão do Postgres. É só pra reduzir o que o aluno precisa entender: tanto o `lakehouse_lab` (`lh.postgres()`) quanto a conexão "postgres" do DBeaver-web já abrem com esse schema como padrão, então ninguém precisa saber o que é `public` nem navegar pelos schemas de sistema do Postgres (`pg_catalog` etc.) pra achar as 4 tabelas que importam. Se quiser mudar o nome, o valor está em `POSTGRES_SCHEMA` no `.env` — mas como esse arquivo é só documentativo (nem o `postgres/init/02_dados_fonte.sql` nem o `dbeaver/initial-data-sources.conf` leem o `.env`), mudar o nome exige editar os três lugares junto.

### Por que o Trino não enxerga o Postgres

O Trino deste laboratório tem um único catálogo (`lakehouse`), de propósito. Já existiu um segundo catálogo `postgres` (o "sistema fonte", ao vivo) — dava pra fazer `SELECT` federado juntando Postgres e data lake numa única query — mas foi removido pra manter o Trino focado só no papel dele aqui: consultar as camadas bronze/silver/gold. Isso não tira acesso nenhum ao Postgres: ele continua totalmente acessível, só que direto (via `lh.postgres()` no Jupyter, ou a conexão "postgres" do DBeaver-web), sem passar pelo Trino.

Se quiser trazer esse catálogo de volta, é só recriar `trino/etc/catalog/postgres.properties`:

```properties
connector.name=postgresql
connection-url=jdbc:postgresql://postgres:5432/database
connection-user=trilha
connection-password=trilha123
```

(troque `database` por `${POSTGRES_DB}` do `.env` se tiver mudado) e depois `docker compose up -d --build trino`. A conexão "trino" do DBeaver-web voltaria a enxergar `postgres.schema.customers` automaticamente, sem precisar mexer em mais nada.

### As duas conexões do DBeaver-web

O `dbeaver/initial-data-sources.conf` pré-configura duas conexões (ambas visíveis pro aluno sem login, e ele não consegue apagar nem editar nenhuma das duas):

- **"postgres"**: driver Postgres, aponta pro schema `schema` — é a "fonte" da aula. A árvore de navegação dessa conexão é restrita de propósito: abrir "postgres" mostra só `database` → `schema` → as 4 tabelas, direto — sem os schemas de sistema do Postgres (já ficavam ocultos por padrão), sem o schema `public` (vazio, mas que ainda apareceria) e sem as pastas extras que o CloudBeaver mostra por padrão (Roles, Extensions, Event Triggers, Storage, Administer, System Info). Ver os comentários em `dbeaver/initial-data-sources.conf` pra como isso foi feito (chaves `navigator-*` e `filters`) e como desfazer, se um dia quiser ver a árvore completa.
- **"trino"**: driver Trino (`generic:trino_jdbc`, já embutido no CloudBeaver Community, sem precisar baixar driver nenhum), aponta pro catálogo `lakehouse` — é a mesma visão SQL que os notebooks usam (`bronze`, `silver`, `gold`). O Trino deste projeto não tem autenticação configurada (ver `trino/etc/config.properties`), então o `userName` na conexão é só um valor fixo (`student`) sem senha de verdade. A árvore de navegação também é restrita, igual na "postgres": o catálogo interno `system` do Trino (metadados do próprio motor — ver "Por que o Trino não enxerga o Postgres" acima) fica oculto, sobrando só o `lakehouse`; dentro dele só aparecem os schemas `bronze`, `silver` e `gold` (os schemas de sistema do Trino, `default` e `information_schema`, ficam ocultos); e dentro de cada schema só aparecem as tabelas — sem as pastas "Views / Indexes / Procedures / Data Types" que o CloudBeaver mostra por padrão (este projeto nunca cria nada além de tabelas, então elas ficariam sempre vazias). Ver os comentários em `dbeaver/initial-data-sources.conf` pra como isso foi feito.

> Este ambiente usa tabelas Hive/Parquet "puras" (sem Iceberg/Delta Lake), então é um **data lake consultável por SQL**, não um lakehouse com ACID/time-travel completo. Isso foi uma escolha deliberada para manter o primeiro contato simples. Se quiser evoluir para uma "aula 3" sobre lakehouse "de verdade" (schema evolution, time travel), o próximo passo natural é trocar o formato das tabelas para Apache Iceberg — a peça que falta é só essa.

## Resetar o ambiente

```bash
docker compose down -v   # -v também apaga os dados (Postgres, MinIO e o workspace do DBeaver-web)
docker compose up -d --build
```

`-v` também é o jeito de "religar" o `dbeaver/initial-data-sources.conf` se você editar esse arquivo depois da primeira subida — ele só é copiado pro volume `dbeaver-workspace` quando esse volume está vazio (ver comentário no `docker-compose.yml`).

## Status: testado de ponta a ponta

Este ambiente foi validado em 08/2026 com um `docker compose down -v && docker compose up -d --build` do zero, com **todas as imagens fixadas em versões exatas** (nenhuma usa `:latest`): `postgres:16.14`, `minio/minio:RELEASE.2025-09-07T16-13-09Z`, `minio/mc:RELEASE.2025-08-13T08-35-41Z`, `starburstdata/hive:3.1.2-e.18`, `trinodb/trino:483`, `dbeaver/cloudbeaver:26.1.4`, e o Jupyter fixado pelo digest do `jupyter/scipy-notebook` no `Dockerfile`. Os 8 serviços sobem saudáveis, `pipeline-init` termina com exit code 0 e log limpo (`[bronze] ...`, `[silver] ...`, `[gold] ...`, `Pipeline concluído`), `bronze`/`silver`/`gold` já existem em `SHOW SCHEMAS FROM lakehouse` assim que o `docker compose up -d --build` devolve o prompt — sem rodar nada manualmente. `trino/init/construir_pipeline.py` também roda de novo manualmente sem erro (via `docker exec data_lakehouse_101-jupyter python3 ...` e via `!python ...` de dentro do container, simulando uma célula de notebook), confirmando que é idempotente. O notebook `explorando_o_lakehouse.ipynb` roda de ponta a ponta via `jupyter nbconvert --execute` sem erro. Os arquivos aparecem em `bronze/`, `silver/`, `gold/` no MinIO, as tabelas gold batem com os dados inseridos, o DBeaver-web abre já conectado e anônimo com as duas conexões ("postgres" e "trino") funcionando de verdade **desde a primeira consulta, sem precisar rodar nada manualmente antes** — inclusive um `SELECT` real em `gold.sales_by_day` via a conexão Trino, e a árvore de navegação da conexão "postgres" batendo exatamente `database → schema → customers/order_items/orders/products` (sem `public`, sem schemas de sistema) e a da conexão "trino" batendo `lakehouse → bronze/silver/gold → tabelas`, sem o catálogo `system`, sem `default`, sem `information_schema` e sem pastas de Views/Indexes/Procedures. Também confirmado que o Trino só enxerga o catálogo `lakehouse` (`SHOW CATALOGS` não lista mais `postgres`), que `database`/`schema` funcionam sem aspas como identificadores do Postgres, e que o mount `:ro` de `trino/init` realmente bloqueia escrita (testado tentando escrever e recebendo `Read-only file system`) — tudo testado direto pela API do CloudBeaver a partir de uma sessão anônima nova, e o Jupyter abre direto em `/lab` (`curl http://localhost:8888/lab` devolve `200`, sem redirect de login) — sem nenhuma intervenção manual.

Como tudo está pinado, o ambiente não deve mudar de comportamento sozinho entre uma aula e outra — só muda se você editar essas versões de propósito.

## Troubleshooting

### Porta já em uso (`port is already allocated`)

O Trino usa a porta **8082** no host (não 8080) de propósito, para não colidir com outros projetos Docker que você já tenha rodando. Se mesmo assim alguma porta bater com outro container seu, pare o outro projeto (`docker compose down` nele) ou troque o mapeamento de porta no `docker-compose.yml` deste projeto (lado esquerdo do `"host:container"`).

### `import lakehouse_lab` falha no notebook

O pacote fica em `/home/jovyan/lakehouse_lab`, mas o kernel do Jupyter roda com `cwd` em `/home/jovyan/notebooks` (onde ficam os `.ipynb`) — por isso o `Dockerfile` do Jupyter define `ENV PYTHONPATH=/home/jovyan`. Se você mudar a estrutura de pastas do projeto Jupyter, lembre de manter esse `PYTHONPATH` (ou instalar `lakehouse_lab` como pacote de verdade via `pip install`).

### O Jupyter (http://localhost:8888) pede token, ou quero um token de volta

Sem token/senha é o comportamento esperado (`command:` do serviço `jupyter` no `docker-compose.yml`, com `--ServerApp.token='' --ServerApp.password=''`). Se ainda assim pedir um token, o `docker compose up` provavelmente não recriou o container depois dessa mudança — rode `docker compose up -d --build jupyter`. Se preferir voltar a ter um token (por exemplo, se for expor a porta 8888 além da sua própria máquina — o que não é recomendado neste projeto, ver seção de URLs acima), edite o `command:` desse serviço pra `start-notebook.sh --ServerApp.token='SEU_TOKEN_AQUI'`.

### Por que o MinIO está pinado numa versão específica (`RELEASE.2025-09-07T16-13-09Z`) e sem Console de admin

Em 2025 a MinIO removeu as ações administrativas (apagar bucket, gerenciar usuários/políticas etc.) do Console web open-source, empurrando pra versão paga (AIStor). Esta imagem já é de depois dessa mudança, de propósito: o Console em http://localhost:9001 serve só pra *olhar* os arquivos (ótimo pra mostrar bronze/silver/gold enchendo em tempo real na aula), sem botões de administração que não fazem falta aqui — nenhuma célula dos notebooks depende deles, e o único caso de uso administrativo (criar o bucket e as pastas `bronze/silver/gold`) já roda sozinho, via `mc`, no serviço `minio-init`.

Se um dia essa tag específica sumir do Docker Hub — o repositório oficial `minio/minio` foi arquivado, então releases futuras não vêm mais dele — as opções são:

1. Usar essa mesma tag via um fork comunitário que espelha as releases (ex.: `pgsty/minio` no Docker Hub), trocando só o nome da imagem no `docker-compose.yml`.
2. Qualquer tag `RELEASE.*` já é suficiente — a API S3 (o que o projeto realmente usa) nunca muda de comportamento entre essas versões, só a UI do Console.
3. Ações administrativas ocasionais (apagar bucket, etc.) sempre dão pra fazer via `mc`, sem depender de UI nenhuma:
   ```bash
   docker run --rm --network data_lakehouse_101_default --entrypoint sh minio/mc:latest -c "
   mc alias set local http://minio:9000 trilha trilha123 &&
   mc rb --force local/NOME_DO_BUCKET
   "
   ```
   (troque `mc rb --force` por `mc rm --recursive --force` para só esvaziar sem apagar o bucket)
4. Também dá pra listar arquivos sem depender de UI nenhuma: `lh.list_layer("bronze")` no Jupyter.

### `docker compose pull` falha na imagem `starburstdata/hive:3.1.2-e.18`

Veja as tags disponíveis em https://hub.docker.com/r/starburstdata/hive/tags e troque pela mais recente da série `3.1.2-e.*` no `docker-compose.yml`.

### Erros de configuração do Hive Metastore ou do catálogo do Trino após trocar de versão de imagem

Essas duas peças são as mais sensíveis a mudanças de versão:

- O script de entrada do `starburstdata/hive` (`/opt/bin/start-hive-metastore.sh`) valida com `test -v` uma lista grande de variáveis (Azure, Google Cloud, S3) que precisam estar **declaradas mesmo vazias** no `environment:` do serviço `hive-metastore` — todas já estão no `docker-compose.yml`. Se uma versão nova da imagem exigir mais alguma, o log do container (`docker logs data_lakehouse_101-hive-metastore`) mostra exatamente em qual `test -v` ele parou.
- Versões recentes do Trino (a partir de ~430) renomearam as propriedades S3 do conector Hive de `hive.s3.*` para `s3.*` + `fs.native-s3.enabled=true` (já configurado em `trino/etc/catalog/lakehouse.properties`). Se trocar para uma imagem de Trino mais antiga, talvez precise voltar para as chaves `hive.s3.*`.

### Erro de tipo ao criar uma tabela bronze (`Unsupported Trino column type ... for Parquet column ...`)

Sintoma de um schema declarado no `CREATE TABLE` que não bate com o tipo físico que o pandas/pyarrow gravou no Parquet. Os dois casos mais comuns já estão tratados em `trino/init/construir_pipeline.py`:
- `NUMERIC` do Postgres vira `Decimal` no pandas → convertido para `float` antes de gravar (bate com `DOUBLE`).
- `DATE` do Postgres vira `datetime64` no pandas → convertido para `date` puro antes de gravar (bate com `DATE`).

Se adicionar uma coluna nova ao schema do Postgres, o mesmo cuidado se aplica.

### O Trino não encontra as tabelas (`Schema 'bronze' does not exist`)

Não deveria mais acontecer por padrão — o serviço `pipeline-init` já roda `trino/init/construir_pipeline.py` sozinho assim que o ambiente sobe (ver "Por que o pipeline virou um script" acima), então `bronze`/`silver`/`gold` já existem antes mesmo do `docker compose up` terminar. Se mesmo assim aparecer:
- Confira se `pipeline-init` terminou com sucesso: `docker compose ps pipeline-init` (deve mostrar `Exited (0)`) e `docker logs data_lakehouse_101-pipeline-init` pra ver o que rodou.
- Se `pipeline-init` falhou (ex: erro transitório de rede/timing na primeira subida), rode manualmente: `docker exec data_lakehouse_101-jupyter python3 /home/jovyan/trino-init/construir_pipeline.py` — isso constrói tudo do mesmo jeito, só que na mão (sem nenhum arquivo pra sujar, é só um script).
- Se `pipeline-init` está preso em "Created"/nunca inicia, o problema é upstream dele — confira se `trino`, `postgres` e `minio` estão `healthy` (`docker compose ps`).

### Quero recriar só um serviço (ex: depois de editar o Dockerfile do Jupyter)

```bash
docker compose up -d --build jupyter
```

Se a mudança for no `jupyter/Dockerfile` ou no pacote `lakehouse_lab`, rebuilde o `pipeline-init` também (ele usa a mesma imagem, mas é um serviço separado — recriar só o `jupyter` não recria ele):
```bash
docker compose up -d --build jupyter pipeline-init
```

### O DBeaver-web (http://localhost:8978) pede login, ou uma das conexões não aparece

Normal só na primeira vez que o volume `dbeaver-workspace` é criado (leva alguns segundos pra terminar a auto-configuração inicial via `CB_ADMIN_NAME`/`CB_ADMIN_PASSWORD`) — dê um refresh na página depois de uns 10-15s. Se persistir:
- Confira `docker logs data_lakehouse_101-dbeaver` por uma linha `Error loading server auto configuration` — o caso mais comum é `CB_ADMIN_NAME` colidir com um nome de time já reservado pelo CloudBeaver (`admin` ou `user`); troque `DBEAVER_ADMIN_USER` no `.env` para outro nome (ex: `professor`) e suba de novo com `docker compose down -v` (isso reseta o volume `dbeaver-workspace`).
- Se o login aparecer mas as conexões não estiverem visíveis, confirme que `CLOUDBEAVER_APP_GRANT_CONNECTIONS_ACCESS_TO_ANONYMOUS_TEAM=true` está no `docker-compose.yml` — sem isso as conexões existem mas ficam visíveis só pro admin.
- Lembre que `dbeaver/initial-data-sources.conf` só é lido quando o volume `dbeaver-workspace` está vazio — editar esse arquivo (por exemplo, pra adicionar uma terceira conexão) depois da primeira subida não tem efeito até rodar `docker compose down -v` (ou, pra resetar só o DBeaver-web sem apagar os dados do Postgres/MinIO: `docker compose stop dbeaver && docker compose rm -f dbeaver && docker volume rm data_lakehouse_101_dbeaver-workspace && docker compose up -d dbeaver`).
- A conexão "trino" conecta mesmo com o Trino ainda subindo (o CloudBeaver só conecta de verdade quando o aluno clica nela) — se der erro de conexão recusada logo depois de um `docker compose up`, espere o `data_lakehouse_101-trino` ficar `healthy` (`docker compose ps`) e tente de novo.

### A conexão "trino" do DBeaver-web dá `Error connecting to database: TLS/SSL is required for authentication with username and password`

Já corrigido em `dbeaver/initial-data-sources.conf` — a causa era o campo `userPassword` (mesmo vazio, `""`) na conexão "trino": o driver JDBC do Trino recusa autenticar com usuário **e** senha fora de uma conexão HTTPS, então só pode existir uma chave "password" na configuração se ela tiver valor de verdade e a URL for `https://`. A correção foi tirar o campo por completo, deixando só `"userName": "student"` — o Trino deste projeto não valida senha mesmo, então não faz falta. Se você editou esse arquivo manualmente e voltou a ver esse erro, confira se não reintroduziu um `userPassword` (mesmo vazio) na conexão "trino".

### Abrir a conexão "trino" no DBeaver-web pede login, ou dá `SQL Error: Authentication failed: Basic authentication or X-Trino-Original-User or X-Trino-User must be sent`

Já corrigido (`"save-password": true` na conexão "trino" em `dbeaver/initial-data-sources.conf`) — mesmo sem senha real, o CloudBeaver só trata as credenciais como "prontas pra usar" (sem perguntar nada ao aluno) quando `save-password` é `true`. Com `false` (que era o valor anterior, por parecer mais correto já que "não tem senha pra salvar"), o CloudBeaver marca a conexão como precisando de login interativo — e o diálogo de login que aparece não preenche o `userName` sozinho, então uma tentativa de conectar sem digitar nada chega no Trino sem nenhum usuário, daí o erro. Testado ao vivo via API do CloudBeaver: com `save-password: true`, a conexão passa a ter `authNeeded: false` e `credentialsSaved: true` — igual à conexão "postgres" — e conecta direto, sem prompt.

### Editei o filtro de catálogos/schemas da conexão "trino" pela UI do CloudBeaver e ele não faz nada

Um detalhe de pegadinha do driver genérico do Trino: o campo `"type"` desses filtros precisa ser `org.jkiss.dbeaver.ext.generic.model.GenericCatalog` (pro filtro que esconde o catálogo `system`) ou `org.jkiss.dbeaver.ext.generic.model.GenericSchema` (pro filtro que esconde `default`/`information_schema` dentro de `lakehouse`) — mas a própria UI do CloudBeaver, ao criar esses filtros clicando em "Filter" na árvore, grava sozinha `GenericTable` em ambos os casos (testado ao vivo), e o filtro fica salvo sem fazer nada, silenciosamente — sem erro nenhum avisando. Se for mexer nisso pela UI em vez de editar `dbeaver/initial-data-sources.conf` diretamente, confira esse campo depois — ou edite o `data-sources.json` do volume `dbeaver-workspace` na mão.

### Não vejo os filtros da conexão "trino" (ainda aparece `system`, `default`, `information_schema`, ou tabelas do tipo `columns`/`roles`/`schemata`/`table_privileges`/`views` direto na árvore)

Essas últimas são literalmente as tabelas de dentro do schema `information_schema` do Trino (ele sempre tem exatamente essas) — se é isso que você está vendo, quer dizer que `bronze`/`silver`/`gold` não existem (só sobra `information_schema` com conteúdo pra mostrar) **e** o filtro que esconde `information_schema` também não pegou. Dois motivos possíveis, quase sempre os dois juntos:

1. **O volume do DBeaver-web está desatualizado.** Editar `dbeaver/initial-data-sources.conf` não tem efeito nenhum num ambiente que já rodou antes (ver nota no topo desse arquivo e a seção "Resetar o ambiente").
2. **O `pipeline-init` não existia ainda** na versão do `docker-compose.yml` que você tinha, ou falhou — sem ele, nada garante que `bronze`/`silver`/`gold` existam antes de você abrir o DBeaver-web.

Resolve os dois de uma vez:
```bash
docker compose down -v
docker compose up -d --build
```
Esse comando só devolve o prompt depois que `pipeline-init` já terminou de construir as camadas (o serviço `dbeaver` depende disso) — então, se ele voltar sem erro, as camadas já existem e o filtro já está com a config atual. Confira com `docker exec data_lakehouse_101-trino trino --execute "SHOW SCHEMAS FROM lakehouse"` (deve devolver `bronze`, `default`, `gold`, `information_schema`, `silver`) e com `docker compose ps pipeline-init` (deve mostrar `Exited (0)`).
