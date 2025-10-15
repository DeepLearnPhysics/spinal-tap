#!/bin/bash
# Quick build and test script for Spinal Tap Docker container

set -e

IMAGE_NAME="spinal-tap"
IMAGE_TAG="local"
PORT=8888

echo "🔨 Building Docker image..."
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

echo "✅ Build complete!"
echo ""
echo "🚀 Starting container..."
echo "📍 Access Spinal Tap at: http://localhost:${PORT}"
echo "🛑 Press Ctrl+C to stop"
echo ""

docker run --rm -it \
  -p ${PORT}:${PORT} \
  --name spinal-tap-dev \
  ${IMAGE_NAME}:${IMAGE_TAG}
