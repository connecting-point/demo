# Use Python 3.11 slim as base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# ✅ Set timezone to Asia/Kolkata
ENV TZ=Asia/Kolkata
RUN ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone

# Copy requirements.txt first for Docker caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install --no-cache-dir xlsxwriter

# Create session directory
RUN mkdir -p /tmp/flask_session

# Copy application files
COPY . .

# Expose Flask app port
EXPOSE 5050

# Start the Flask app
CMD ["python3", "app.py"]

