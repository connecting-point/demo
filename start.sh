#!/bin/bash

echo "🔄 Stopping old container..."
docker compose down

echo "🔧 Building Docker image..."
docker compose build

echo "🚀 Starting container..."
docker compose up -d

echo "✅ App is running at http://localhost:5050"

