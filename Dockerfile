FROM python:3.11-slim

WORKDIR /app

# System deps kept minimal; pypdf/python-docx are pure-python.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# Use a non-root user
RUN useradd -m appuser
USER appuser

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
