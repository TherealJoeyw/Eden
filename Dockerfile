FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates postgresql-client \
    && rm -rf /var/lib/apt/lists/*

ENV REPO_URL=https://github.com/TherealJoeyw/Eden.git
ENV BRANCH=main

CMD ["sh", "-c", "rm -rf /app && git clone --branch \"$BRANCH\" --single-branch \"$REPO_URL\" /app && cd /app && pip install --no-cache-dir -r requirements.txt && exec python bot/main.py"]
