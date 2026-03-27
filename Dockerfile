# Use official Python image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Make sure bgmi is executable
RUN chmod +x bgmi

# Set environment variables
ENV PORT=5000

# Expose the port (this is just documentation, actual port is set by Railway)
EXPOSE $PORT

# Command to run the application
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} app:app"]