# Custom GitHub Actions runner image.
# Adds libatomic1, which Node.js >= 25 needs at runtime, plus a few common build tools.
ARG BASE_IMAGE=ghcr.io/actions/actions-runner:latest
FROM ${BASE_IMAGE}

USER root

RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libatomic1 \
      build-essential \
      ca-certificates \
      curl \
      git \
      jq \
 && rm -rf /var/lib/apt/lists/*

USER runner

# No ENTRYPOINT/CMD here on purpose: the upstream image's defaults are inherited unchanged.
