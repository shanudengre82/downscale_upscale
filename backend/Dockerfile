FROM python:3.12-slim AS builder
RUN pip install poetry==1.8.2
WORKDIR /app
# Copy from root context
COPY pyproject.toml poetry.lock* ./
# Install main + backend group
RUN poetry config virtualenvs.in-project true && \
    poetry install --only main,backend --no-root

FROM python:3.12-slim
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH"
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 wget && rm -rf /var/lib/apt/lists/*
COPY --from=builder /app/.venv /app/.venv
# Copy backend folder content
COPY backend/ .
RUN wget https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]