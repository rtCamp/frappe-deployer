# python: {{ python_canonical }}
# nodejs: {{ nodejs_canonical }}
FROM {{ base_image_name }} as builder

{% if labels %}
{% for label in labels %}
LABEL {{ label }}
{% endfor %}
{% endif %}

# LABEL org.opencontainers.image.authors="rtCamp <sys@rtcamp.com>"

ARG USER={{ user }}
ARG BENCH={{ bench_name }}
ARG SITENAME={{ site_name }}

RUN groupadd --gid 1000 ${USER} && useradd --uid 1000 --gid 1000 --shell /bin/bash --create-home -d /workspace ${USER} \
&& chown -R ${USER}:${USER} /workspace \
&& mkdir -p /logs && chown ${USER}:${USER} /logs

RUN \
{% if distro == "slim" %}  apt-get update && apt-get install curl gnupg2 xz-utils -yqq && \
{% endif %} \
  rm -rf /var/lib/apt/lists/*
RUN NODE_VERSION="v{{ nodejs.canonical }}" \
  ARCH= && dpkgArch="$(dpkg --print-architecture)" \
  && case "${dpkgArch##*-}" in \
    amd64) ARCH='x64';; \
    arm64) ARCH='arm64';; \
    *) echo "unsupported architecture"; exit 1 ;; \
  esac \
  && for key in $(curl -sL https://raw.githubusercontent.com/nodejs/docker-node/HEAD/keys/node.keys); do \
    gpg --batch --keyserver hkps://keys.openpgp.org --recv-keys "$key" || \
    gpg --batch --keyserver keyserver.ubuntu.com --recv-keys "$key" ; \
  done \
  && curl -fsSLO --compressed "https://nodejs.org/dist/$NODE_VERSION/node-$NODE_VERSION-linux-$ARCH.tar.xz" \
  && curl -fsSLO --compressed "https://nodejs.org/dist/$NODE_VERSION/SHASUMS256.txt.asc" \
  && gpg --batch --decrypt --output SHASUMS256.txt SHASUMS256.txt.asc \
  && grep " node-$NODE_VERSION-linux-$ARCH.tar.xz\$" SHASUMS256.txt | sha256sum -c - \
  && tar -xJf "node-$NODE_VERSION-linux-$ARCH.tar.xz" -C /usr/local --strip-components=1 --no-same-owner \
  && rm "node-$NODE_VERSION-linux-$ARCH.tar.xz" SHASUMS256.txt.asc SHASUMS256.txt \
  && ln -s /usr/local/bin/node /usr/local/bin/nodejs

RUN corepack enable yarn
RUN pip install --no-cache-dir -U pip uv frappe-bench
RUN apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    # Core Utilities
  ca-certificates wget git gettext-base \
  # Database Clients (required for bench commands)
  mariadb-client postgresql-client \
  # PDF runtime dependencies (for wkhtmltopdf)
  libssl3 libpangocairo-1.0-0 xfonts-75dpi xfonts-base fonts-cantarell \
  # Process Management
  jq gosu \
  pkg-config \
  # For pandas
  libbz2-dev \
  # For bench execute
  libsqlite3-dev \
  # For other dependencies
  zlib1g-dev \
  build-essential \

  #  libreadline-dev \
  #  llvm \
  #  libncurses5-dev \
  #  libncursesw5-dev \
  #  xz-utils \
  #  tk-dev \
  #  liblzma-dev \

  # Other
  libffi-dev \
  liblcms2-dev \
  libldap2-dev \
  libmariadb-dev \
  libsasl2-dev \
  libtiff5-dev \
  libwebp-dev \
  redis-tools \
  rlwrap \
  #tk8.6-dev \
  ssh-client \
  # Check if required ?
  && rm -rf /var/lib/apt/lists/*

ENV WKHTMLTOPDF_VERSION=0.12.6.1-3
RUN set -eux; \
    ARCH=$(dpkg --print-architecture); \
    downloaded_file=wkhtmltox_${WKHTMLTOPDF_VERSION}.bookworm_${ARCH}.deb; \
    wget -q https://github.com/wkhtmltopdf/packaging/releases/download/${WKHTMLTOPDF_VERSION}/${downloaded_file}; \
    dpkg -i $downloaded_file || apt-get install -y --no-install-recommends -f; \
    rm $downloaded_file

WORKDIR /workspace

FROM builder as frappe

LABEL author=rtCamp
LABEL org.opencontainers.image.source=https://github.com/rtcamp/frappe-haiku

RUN apt update && apt install --yes file vim
RUN echo "disable-ssl-verify-server-cert" >> /etc/mysql/mariadb.conf.d/50-client.cnf

USER ${USER}

COPY --chown=${USER}:${USER} ./$BENCH/apps /workspace/frappe-bench/apps
COPY --chown=${USER}:${USER} ./$BENCH/sites /workspace/frappe-bench/sites
COPY --chown=${USER}:${USER} ./$BENCH/config /workspace/frappe-bench/config
COPY --chown=${USER}:${USER} ./$BENCH/env /workspace/frappe-bench/env
COPY --chown=${USER}:${USER} ./$BENCH/fmd-config.toml /workspace/frappe-bench/fmd-config.toml
COPY --chown=${USER}:${USER} ./$BENCH/logs /workspace/frappe-bench/logs

RUN mkdir -p /workspace/frappe-bench/sites/$SITENAME/private/files /workspace/frappe-bench/sites/$SITENAME/public/files /workspace/frappe-bench/sites/$SITENAME/logs /workspace/frappe-bench/sites/$SITENAME/locks

RUN /workspace/frappe-bench/env/bin/pip install opentelemetry-distro opentelemetry-exporter-otlp && /workspace/frappe-bench/env/bin/opentelemetry-bootstrap -a install

ENTRYPOINT [ "/usr/bin/env" , "bash" ]
