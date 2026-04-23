FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy your bgmi binary
COPY bgmi .
RUN chmod +x bgmi

# Copy the app
COPY app.py .

# Run the app
CMD
