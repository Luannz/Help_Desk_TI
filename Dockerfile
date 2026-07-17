# Usa uma imagem oficial leve do Python
FROM python:3.11-slim

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Evita que o Python grave arquivos .pyc e bufferize o stdout/stderr
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Instala dependências do sistema necessárias para pacotes Python (como psycopg2)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Instala as dependências do projeto
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copia o código do projeto para dentro do container
COPY . /app/

# Expõe a porta que o servidor vai rodar
EXPOSE 8000

# Comando para rodar a aplicação em produção (usando Gunicorn)
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000"]