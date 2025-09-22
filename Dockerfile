# Image Python légère
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# dépendances système pour mysqlclient
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential default-libmysqlclient-dev pkg-config netcat-openbsd \
    && rm -rf /var/lib/apt/lists/*

# user non-root
RUN useradd -m appuser

WORKDIR /app

# dépendances python
COPY requirements.txt /app/
RUN pip install -r requirements.txt

# copie du code
COPY . /app/

RUN chmod +x /app/entrypoint.sh

# droits
RUN chown -R appuser:appuser /app
USER appuser

# port
EXPOSE 8000

# entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]
