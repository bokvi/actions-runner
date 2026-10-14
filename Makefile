IMAGE ?= ghcr.io/bokvi/actions-runner
TAG ?= local
PLATFORMS ?= linux/amd64,linux/arm64
DIND_IMAGE ?= $(IMAGE):dind-local

.PHONY: build build-multi push shell test build-dind test-dind

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
## and owned by `runner`, gh and the AWS CLI run (with put-object's conditional-write options),
## and the image still runs as `runner`
test: build
	docker run --rm $(IMAGE):$(TAG) bash -c 'set -e; dpkg -s libatomic1 >/dev/null; test "$$(whoami)" = runner; \
	  gh --version | head -n 1; aws --version; \
	  out=$$(AWS_ACCESS_KEY_ID=x AWS_SECRET_ACCESS_KEY=x AWS_DEFAULT_REGION=auto AWS_MAX_ATTEMPTS=1 \
	    aws s3api put-object --endpoint-url http://127.0.0.1:9 --bucket b --key k \
	      --if-match x --if-none-match "*" 2>&1) && exit 1; \
	  echo "$$out" | grep -q "Could not connect to the endpoint URL" || { echo "$$out" >&2; exit 1; }; \
	  case "$$(uname -m)" in x86_64) arch=x64 ;; aarch64) arch=arm64 ;; *) echo "unsupported arch: $$(uname -m)" >&2; exit 1 ;; esac; \
	  test -d "$$RUNNER_TOOL_CACHE"; not_runner=$$(find "$$RUNNER_TOOL_CACHE" ! -user runner); test -z "$$not_runner"; \
	  for m in "$$RUNNER_TOOL_CACHE"/node/24.*/"$$arch".complete; do test -f "$$m"; \
	    "$${m%.complete}/bin/node" --version | grep "^v24\."; PATH="$${m%.complete}/bin:$$PATH" npm --version; done; \
	  echo OK'

## Build trusted image seeds on the native architecture (requires privileged Docker)
build-dind:
	python3 prewarm/build.py --tag $(DIND_IMAGE)

## Verify real daemons, exact digest hits, isolation, restart and cache misses
test-dind:
	python3 prewarm/test.py --image $(DIND_IMAGE)
