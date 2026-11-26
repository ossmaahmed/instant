FROM python:3.12-alpine
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN apk upgrade --no-cache \
    && apk add --no-cache tzdata \
    && adduser -D -u 1000 app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY --chown=app:app . .
RUN chmod +x entrypoint.sh
USER app
EXPOSE 8002
ENTRYPOINT ["/app/entrypoint.sh"]
