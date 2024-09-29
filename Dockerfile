FROM python:3.9-alpine

RUN apk add --no-cache postgresql-dev gcc musl-dev postgresql-client libpq curl bash
RUN apk add --no-cache openrc netcat-openbsd

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app

COPY schema.sql /docker-entrypoint-initdb.d/

WORKDIR /app

CMD bash -c "while ! nc -z postgres 5432; do \
              echo 'Waiting for PostgreSQL...'; \
              sleep 3; \
           done; \
           psql -h postgres -U user -d marketplace -f /docker-entrypoint-initdb.d/schema.sql && \
           while ! nc -z elasticsearch 9200; do \
              echo 'Waiting for Elasticsearch...'; \
              sleep 10; \
           done; \
           echo 'Elasticsearch is available. Applying index mapping...'; \
           curl -X PUT 'http://elasticsearch:9200/products/_mapping' \
                -H 'Content-Type: application/json' \
                -d '{ \"properties\": { \"features\": { \"type\": \"object\" } } }' && \
           python main.py"