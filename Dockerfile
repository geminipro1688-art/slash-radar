# slash-radar 生產映像（零框架，stdlib http.server + requests）
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir requests>=2.28
COPY backend/ ./backend/
COPY frontend/ ./frontend/
RUN mkdir -p data
ENV HOST=0.0.0.0
# Render/Railway 會注入 PORT；本機 docker run -p 8088:8088 預設 8088
EXPOSE 8088
WORKDIR /app/backend
CMD ["python", "serve.py"]
