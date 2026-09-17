FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
RUN useradd --create-home --uid 10001 scalelink
USER scalelink
EXPOSE 8001
CMD ["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8001"]
