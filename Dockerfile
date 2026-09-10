FROM python:3.12-slim AS builder

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN pip install --no-cache-dir uv

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN uv pip install --system --no-cache .

FROM python:3.12-slim

WORKDIR /app

RUN groupadd -r forge && useradd -r -g forge -m forge

COPY --from=builder /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=builder /usr/local/bin/syntheticforge /usr/local/bin/syntheticforge
COPY schemas/ ./schemas/

USER forge

ENTRYPOINT ["syntheticforge"]
CMD ["--help"]
