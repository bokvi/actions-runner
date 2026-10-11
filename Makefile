IMAGE ?= ghcr.io/bokvi/actions-runner
TAG ?= local
PLATFORMS ?= linux/amd64,linux/arm64

.PHONY: build build-multi push shell test

## Build for the host architecture and load into the local Docker daemon
build:
	docker build -t $(IMAGE):$(TAG) .

## Build for all platforms (result stays in the build cache; use `push` to publish)
build-multi:
	docker buildx build --platform $(PLATFORMS) -t $(IMAGE):$(TAG) .

## Build for all platforms and push (requires `docker login ghcr.io`)
push:
	docker buildx build --platform $(PLATFORMS) -t $(IMAGE):$(TAG) --push .

## Open a shell in the locally built image
shell: build
	docker run --rm -it $(IMAGE):$(TAG) bash

## Check that libatomic1 is present, Node.js 24 is in the tool cache under setup-node's arch name
## and owned by `runner`, and the image still runs as `runner`
test: build
	docker run --rm $(IMAGE):$(TAG) bash -c 'set -e; dpkg -s libatomic1 >/dev/null; test "$$(whoami)" = runner; \
	  case "$$(uname -m)" in x86_64) arch=x64 ;; aarch64) arch=arm64 ;; *) echo "unsupported arch: $$(uname -m)" >&2; exit 1 ;; esac; \
	  test -d "$$RUNNER_TOOL_CACHE"; not_runner=$$(find "$$RUNNER_TOOL_CACHE" ! -user runner); test -z "$$not_runner"; \
	  for m in "$$RUNNER_TOOL_CACHE"/node/24.*/"$$arch".complete; do test -f "$$m"; \
	    "$${m%.complete}/bin/node" --version | grep "^v24\."; PATH="$${m%.complete}/bin:$$PATH" npm --version; done; \
	  echo OK'
