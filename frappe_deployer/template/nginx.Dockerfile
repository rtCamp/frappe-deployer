FROM {{base_image_name}}

{% if labels %}
{% for label in labels %}
LABEL {{ label }}
{% endfor %}
{% endif %}

ARG SITENAME={{site_name}}
ARG BENCH={{bench_name}}
ARG USER={{user}}

{% if additional_packages %}
# Install additional custom packages
RUN apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
  {% for package in additional_packages %}{{ package }} \
  {% endfor %} && rm -rf /var/lib/apt/lists/*
{% endif %}

#RUN groupadd --gid 1000 $USER && useradd --uid 1000 --gid 1000 -G nginx -G www-data --shell /bin/bash --create-home -d /workspace $USER
RUN usermod -aG www-data nginx
RUN mkdir -p /workspace/frappe-bench/sites/$SITENAME/private/files /workspace/frappe-bench/sites/$SITENAME/public/files /workspace/frappe-bench/sites/$SITENAME/logs /workspace/frappe-bench/sites/$SITENAME/locks
COPY  ./$BENCH/sites/assets /workspace/frappe-bench/sites/assets
