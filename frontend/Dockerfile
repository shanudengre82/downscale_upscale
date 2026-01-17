FROM python:3.12-slim AS builder
RUN pip install poetry==1.8.2
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
# Install main + frontend group
RUN poetry config virtualenvs.in-project true && \
    poetry install --only main,frontend --no-root

FROM python:3.12-slim
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
# Copy frontend folder content
COPY frontend/ .
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]