# Pinada pelo digest (não por tag): essa imagem não publica uma tag de
# versão legível, então o digest é a única forma confiável de garantir
# que o build de hoje não muda sozinho no futuro.
FROM jupyter/scipy-notebook@sha256:fca4bcc9cbd49d9a15e0e4df6c666adf17776c950da9fa94a4f0a045d5c4ad33

USER root
RUN pip install --no-cache-dir \
    trino==0.328.0 \
    boto3==1.34.131 \
    sqlalchemy==2.0.30 \
    psycopg2-binary==2.9.9 \
    s3fs==2024.6.1 \
    pyarrow==16.1.0

# lakehouse_kit (o pacote com as conexões pré-configuradas) NÃO é
# copiado pra imagem aqui — de propósito, pro aluno poder editá-lo. Ele
# mora em jupyter/notebooks/lakehouse_kit no repo e chega no container
# só via bind mount (ver docker-compose.yml):
#   - no serviço `jupyter`, junto do resto de ./jupyter/notebooks — o
#     kernel roda com cwd em /home/jovyan/notebooks, que já contém
#     lakehouse_kit/, então `import lakehouse_kit` funciona sem precisar
#     de PYTHONPATH nenhum (Python inclui o cwd do processo interativo
#     no sys.path automaticamente).
#   - no serviço `pipeline-init`, montado à parte (ele não monta
#     ./jupyter/notebooks inteiro) com PYTHONPATH apontando pra lá —
#     necessário porque `python3 /caminho/script.py` usa a pasta do
#     script, não o cwd, pra resolver imports.

# A imagem base (jupyter/scipy-notebook) já vem com uma pasta "work"
# em /home/jovyan, pensada pra quem não monta um volume próprio. Este
# projeto sempre monta ./jupyter/notebooks ali, então "work" nunca é
# usada — só aparece vazia no explorador de arquivos, confundindo o
# aluno. Removida de propósito para não existir quando o ambiente sobe.
RUN rm -rf /home/jovyan/work

USER jovyan
