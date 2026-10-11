# Custom GitHub Actions runner image.
# Adds libatomic1, which Node.js >= 25 needs at runtime, plus a few common build tools,
# and Node.js 24 in the runner's tool cache.
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

# Node.js in the tool cache, so actions/setup-node finds it ("Found in cache") instead of
# downloading it in every job. setup-node's tool-cache lookup needs
# <cache>/node/<version>/<arch>/ and an empty <arch>.complete marker next to it.
# To bump: set NODE_VERSION to the latest 24.x from https://nodejs.org/dist/index.json.
ARG NODE_VERSION=24.21.0
ARG TARGETARCH
ENV RUNNER_TOOL_CACHE=/opt/hostedtoolcache
RUN case "${TARGETARCH}" in \
      amd64) arch=x64 ;; \
      arm64) arch=arm64 ;; \
      *) echo "unsupported TARGETARCH: ${TARGETARCH}" >&2; exit 1 ;; \
    esac \
 && tarball="node-v${NODE_VERSION}-linux-${arch}.tar.gz" \
 && dir="${RUNNER_TOOL_CACHE}/node/${NODE_VERSION}" \
 && cd /tmp \
 && curl -fsSLO "https://nodejs.org/dist/v${NODE_VERSION}/${tarball}" \
 && curl -fsSL "https://nodejs.org/dist/v${NODE_VERSION}/SHASUMS256.txt" \
      | grep " ${tarball}\$" | sha256sum -c - \
 && mkdir -p "${dir}/${arch}" \
 && tar -xzf "${tarball}" -C "${dir}/${arch}" --strip-components=1 --no-same-owner \
 && rm "${tarball}" \
 && touch "${dir}/${arch}.complete" \
 && chown -R runner:runner "${RUNNER_TOOL_CACHE}" \
 && "${dir}/${arch}/bin/node" --version

USER runner

# No ENTRYPOINT/CMD here on purpose: the upstream image's defaults are inherited unchanged.
