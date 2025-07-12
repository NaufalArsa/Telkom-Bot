# Use official Python image
FROM python:3.11-slim

# Install Node.js (for expand.js)
RUN apt-get update && \
    apt-get install -y curl gnupg && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the code
COPY . .

# Expose no ports (Telegram bot is a worker)
# EXPOSE 8080

# Set environment variables (optional, for Railway these are set in the dashboard)
# ENV PYTHONUNBUFFERED=1

# Start the bot
CMD ["python", "bot.py"]