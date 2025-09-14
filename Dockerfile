FROM ubuntu:22.04 AS builder

ENV PYAPP_DOWNLOAD=https://github.com/ofek/pyapp/releases/latest/download/source.tar.gz
ENV PYTHON_VERSION='3.11'
ENV PYAPP_FULL_ISOLATION=1
ENV PYAPP_SKIP_INSTALL=1
ENV PYAPP_DISTRIBUTION_EMBED=1
ENV PYAPP_PROJECT_NAME=frappe_deployer
ENV PYAPP_EXEC_SPEC=frappe_deployer.main:cli_entrypoint
ENV PYAPP_PIP_EXTRA_ARGS="frappe-manager gitpython typer toml"

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
    jq \
    cargo \
    && rm -rf /var/lib/apt/lists/*

# Install Rust (for cargo build)
RUN curl https://sh.rustup.rs -sSf | bash -s -- -y
ENV PATH="/root/.cargo/bin:/root/.local/bin:${PATH}"

# Install UV and Poetry, and build Python environment
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && uv python install "$PYTHON_VERSION"

# Copy frappe-deployer source
COPY . /frappe-deployer
WORKDIR /frappe-deployer

# Setup PyAPP for building
RUN export UVPYPATH="$(uv python dir)/$(uv python list ${PYTHON_VERSION} --output-format json --only-installed | jq -r '.[0].key')" \
    && export PYAPP_DISTRIBUTION_PYTHON_PATH="bin/python3" \
    && export PYTHON_PATH="$UVPYPATH/${PYAPP_DISTRIBUTION_PYTHON_PATH}" \
    && export PYAPP_PROJECT_VERSION==$(grep -E '^version\s*=' pyproject.toml | head -1 | cut -d '=' -f2 | tr -d ' "' | xargs) \
    && uvx poetry build \
    && uv pip install --python "${PYTHON_PATH}"  dist/*.whl --break-system-packages \
    && export PYAPP_DISTRIBUTION_PATH="$UVPYPATH/../$(basename $UVPYPATH).tar.gz" \
    && tar -czvf $PYAPP_DISTRIBUTION_PATH -C ${UVPYPATH}/ . \
    && curl ${PYAPP_DOWNLOAD} -Lo pyapp-source.tar.gz \
    && tar -xzf pyapp-source.tar.gz \
    && mv pyapp-v* pyapp-latest \
    && cd pyapp-latest \
    && cargo build --release \
    && mv target/release/pyapp /fmd \
    && chmod +x /fmd \
    && cp /frappe-deployer/README.md /README.md

FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    git \
    ssh \
    rsync \
    curl \
    wget \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -s /bin/bash actionuser

# Copy only the built binary, README, LICENSE, and scripts from builder
COPY --from=builder /fmd /fmd
COPY --from=builder /frappe-deployer/LICENSE /LICENSE
COPY --from=builder /README.md /README.md
COPY .github/scripts/entrypoint.sh /entrypoint.sh
COPY .github/scripts/helpers.sh /helpers.sh
RUN chmod +x /entrypoint.sh /helpers.sh

USER actionuser
WORKDIR /github/workspace

ENTRYPOINT ["/entrypoint.sh"]
