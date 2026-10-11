# Custom GitHub Actions runner image.
# Adds libatomic1, which Node.js >= 25 needs at runtime, plus a few common build tools,
# and Node.js 24 in the runner's tool cache.
ARG BASE_IMAGE=ghcr.io/actions/actions-runner:latest

# Node.js for the tool cache, taken from the official image (Dependabot bumps it within 24.x).
# Lay it out as actions/setup-node's tool-cache lookup expects: <cache>/node/<version>/<arch>/
# and an empty <arch>.complete marker next to it, where <arch> is Node's own (x64, arm64).
FROM node:24.21.0-bookworm-slim@sha256:d6aa754f16b3197301076f047b5def2f02ea1dbbc2ca920407d46d7ec7f87b20 AS node
RUN dir="/toolcache/node/$(node -p process.versions.node)" \
 && arch="$(node -p process.arch)" \
 && mkdir -p "${dir}/${arch}" \
 && cp -a /usr/local/LICENSE /usr/local/bin /usr/local/include /usr/local/lib /usr/local/share "${dir}/${arch}/" \
 && rm -f "${dir}/${arch}/bin/docker-entrypoint.sh" "${dir}/${arch}/bin/nodejs" \
      "${dir}/${arch}/bin/yarn" "${dir}/${arch}/bin/yarnpkg" \
 && touch "${dir}/${arch}.complete"

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

# Node.js in the tool cache, so actions/setup-node finds it ("Found in cache") instead of
# downloading it in every job.
ENV RUNNER_TOOL_CACHE=/opt/hostedtoolcache
COPY --from=node --chown=runner:runner /toolcache/ ${RUNNER_TOOL_CACHE}/

USER runner

# No ENTRYPOINT/CMD here on purpose: the upstream image's defaults are inherited unchanged.
