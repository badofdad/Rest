FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the bgmi binary file
COPY bgmi .

# IMPORTANT: Make the binary executable
RUN chmod +x bgmi

# Copy the Flask app
COPY app.py .

# Expose the port
EXPOSE 5000

# Run the application
CMD ["python", "app.py"]
