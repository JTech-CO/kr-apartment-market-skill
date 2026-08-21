FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Seoul
WORKDIR /app
COPY . /app
RUN python -m pip install --no-cache-dir .
EXPOSE 8765
CMD ["kr-apartment-market", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8765"]
