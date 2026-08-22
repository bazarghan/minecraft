FROM python:3.12.9-slim-bookworm AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY requirements.lock ./
COPY app ./app
RUN pip install --no-cache-dir --prefix=/install --require-hashes -r requirements.lock && \
    pip install --no-cache-dir --prefix=/install --no-deps .

FROM python:3.12.9-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH=/home/manager/.local/bin:$PATH
RUN groupadd --gid 10001 manager && useradd --uid 10001 --gid manager --create-home manager
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --chown=manager:manager app ./app
COPY --chown=manager:manager alembic ./alembic
COPY --chown=manager:manager alembic.ini pyproject.toml ./
USER manager
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
