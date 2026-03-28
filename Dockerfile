FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN chmod +x bgmi

ENV PORT=5000

# Add this to ensure logs are captured
ENV PYTHONUNBUFFERED=1

EXPOSE $PORT

CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --access-logfile - --error-logfile - app:app"]