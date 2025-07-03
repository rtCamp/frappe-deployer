FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    ssh \
    rsync \
    curl \
    wget \
    ca-certificates \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash actionuser

# Copy frappe-deployer source
COPY . /frappe-deployer
WORKDIR /frappe-deployer

# Install PyApp and build the binary
RUN pip3 install pyapp
ENV PYAPP_PROJECT_PATH=/frappe-deployer
ENV PYAPP_PROJECT_NAME=frappe-deployer
ENV PYAPP_PROJECT_VERSION=0.8.2
RUN python3 -m pyapp

# Verify binary was created and test it
RUN ls -la /frappe-deployer/dist/ && \
    /frappe-deployer/dist/frappe-deployer --version

# Copy scripts and make executable
COPY .github/scripts/entrypoint.sh /entrypoint.sh
COPY .github/scripts/helpers.sh /helpers.sh
RUN chmod +x /entrypoint.sh /helpers.sh

# Switch to non-root user
USER actionuser
WORKDIR /github/workspace

ENTRYPOINT ["/entrypoint.sh"]
