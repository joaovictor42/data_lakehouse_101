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

# O kernel roda com cwd em /home/jovyan/notebooks (onde ficam os .ipynb),
# não em /home/jovyan — então o pacote só é importável em qualquer
# notebook se /home/jovyan estiver explicitamente no PYTHONPATH.
COPY lakehouse_lab /home/jovyan/lakehouse_lab
RUN chown -R jovyan:users /home/jovyan/lakehouse_lab
ENV PYTHONPATH=/home/jovyan

USER jovyan
