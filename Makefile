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

## Check that libatomic1 is present and the image still runs as `runner`
test: build
	docker run --rm $(IMAGE):$(TAG) bash -c 'dpkg -s libatomic1 >/dev/null && test "$$(whoami)" = runner && echo OK'
