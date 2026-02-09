FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV HOME=/home/appuser

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends nodejs npm ca-certificates \
    && npm install -g @anthropic-ai/claude-code \
    && useradd --create-home --home-dir /home/appuser --shell /bin/bash appuser \
    && mkdir -p /home/appuser/.claude \
    && printf '{}\n' > /home/appuser/.claude/remote-settings.json \
    && chown -R appuser:appuser /home/appuser /app \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY app /app/app

USER appuser

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
