# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies if needed
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY pyproject.toml MANIFEST.in README.md ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir .

# Expose the default port
EXPOSE 8888

# Set the entrypoint to run spinal-tap
ENTRYPOINT ["spinal-tap"]

# Default arguments (can be overridden)
CMD ["--host", "0.0.0.0", "--port", "8888"]
