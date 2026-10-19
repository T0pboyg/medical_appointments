FROM python:3.12-slim

WORKDIR /app

COPY requirements.lock .

RUN pip install --no-cache-dir --require-hashes -r requirements.lock

COPY *.py .
COPY migrations/ ./migrations/
RUN useradd --create-home --uid 10001 appuser

USER appuser

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]