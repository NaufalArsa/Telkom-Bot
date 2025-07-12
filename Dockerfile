# Use official Python image
FROM python:3.11-slim

# Install Node.js and system dependencies for Puppeteer
RUN apt-get update && \
    apt-get install -y curl gnupg wget ca-certificates fonts-liberation libappindicator3-1 libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 libdbus-1-3 libgdk-pixbuf2.0-0 libnspr4 libnss3 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 xdg-utils && \
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - && \
    apt-get install -y nodejs && \
    apt-get clean && rm -rf /var/lib/apt/lists/*

# Set work directory
WORKDIR /app

# Set environment variable to skip Puppeteer's auto Chromium download
ENV PUPPETEER_SKIP_DOWNLOAD=true

# Copy Node dependencies and install
COPY package*.json ./
RUN npm install

# Manually install Chromium after npm install
RUN npx puppeteer browsers install chrome

# Copy Python requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your code
COPY . .

# Start the bot
CMD ["python", "bot.py"]