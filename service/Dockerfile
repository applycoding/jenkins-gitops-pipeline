FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --gid 65532 app \
    && useradd --uid 65532 --gid 65532 --create-home --shell /usr/sbin/nologin app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY status_api ./status_api

USER 65532

EXPOSE 8000

CMD ["uvicorn", "status_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
