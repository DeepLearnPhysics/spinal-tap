#!/bin/bash
# Quick build and test script for Spinal Tap Docker container

set -e

IMAGE_NAME="spinal-tap"
IMAGE_TAG="local"
PORT=8888
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🔨 Building Docker image..."
docker build -f "${REPO_ROOT}/docker/Dockerfile" \
  -t "${IMAGE_NAME}:${IMAGE_TAG}" "${REPO_ROOT}"

echo "✅ Build complete!"
echo ""
echo "🚀 Starting container..."
echo "📍 Access Spinal Tap at: http://localhost:${PORT}"
echo "🛑 Press Ctrl+C to stop"
echo ""

docker run --rm -it \
  -p "${PORT}:${PORT}" \
  --name spinal-tap-dev \
  "${IMAGE_NAME}:${IMAGE_TAG}"
