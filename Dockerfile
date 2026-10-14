# Custom GitHub Actions runner image.
# Adds libatomic1, which Node.js >= 25 needs at runtime, plus a few common build tools,
# the AWS CLI and the GitHub CLI, and Node.js 24 in the runner's tool cache.
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

# AWS CLI v2, taken from the official image (Dependabot bumps it). Ubuntu's awscli package is
# older and lacks conditional writes (s3api put-object --if-match / --if-none-match).
FROM amazon/aws-cli:2.38.0@sha256:ed3233c28ad56d6a66e9e7623a495ab2d7eb08d425f8eea0fdbdfacb12de2ba8 AS aws-cli

FROM ${BASE_IMAGE} AS base

USER root

# gh comes from GitHub's apt repository, signed with the keyring GitHub publishes there. The
# source and keyring are removed afterwards, so a job's `apt-get update` never depends on
# cli.github.com or on that keyring still matching GitHub's signing key.
RUN install -d -m 755 /etc/apt/keyrings \
 && curl -fsSL -o /etc/apt/keyrings/githubcli-archive-keyring.gpg \
      https://cli.github.com/packages/githubcli-archive-keyring.gpg \
 && chmod 644 /etc/apt/keyrings/githubcli-archive-keyring.gpg \
 && echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" \
      > /etc/apt/sources.list.d/github-cli.list \
 && apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      libatomic1 \
      build-essential \
      ca-certificates \
      curl \
      gh \
      git \
      jq \
 && rm -f /etc/apt/sources.list.d/github-cli.list /etc/apt/keyrings/githubcli-archive-keyring.gpg \
 && rm -rf /var/lib/apt/lists/*

# The AWS CLI keeps the official image's layout: the versioned install under /usr/local/aws-cli
# and symlinks in /usr/local/bin. They are recreated rather than copied, because COPY follows
# them and the binary only finds its bundled libraries from its own directory.
COPY --from=aws-cli /usr/local/aws-cli/ /usr/local/aws-cli/
RUN ln -s /usr/local/aws-cli/v2/current/bin/aws /usr/local/aws-cli/v2/current/bin/aws_completer \
      /usr/local/bin/

# Node.js in the tool cache, so actions/setup-node finds it ("Found in cache") instead of
# downloading it in every job.
ENV RUNNER_TOOL_CACHE=/opt/hostedtoolcache
COPY --from=node --chown=runner:runner /toolcache/ ${RUNNER_TOOL_CACHE}/

USER runner

# No ENTRYPOINT/CMD here on purpose: the upstream image's defaults are inherited unchanged.

# Opt-in fleet variant. A project .npmrc or explicit npm configuration can override
# this user-level default; the ordinary runner image remains registry-independent.
FROM base AS ci-bokvi
ARG NPM_REGISTRY=http://172.17.0.1:4873
RUN printf 'registry=%s\n' "$NPM_REGISTRY" > /home/runner/.npmrc

FROM base AS runner
