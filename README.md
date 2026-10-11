# actions-runner

[![Build and publish](https://github.com/bokvi/actions-runner/actions/workflows/publish.yml/badge.svg)](https://github.com/bokvi/actions-runner/actions/workflows/publish.yml)

A drop-in replacement for the official [`ghcr.io/actions/actions-runner`](https://github.com/actions/runner/pkgs/container/actions-runner) image with **`libatomic1`** pre-installed.

## Why

Node.js 25+ links against `libatomic.so.1`, which the official runner image doesn't ship. Any job that uses Node 25 (for example via `actions/setup-node`) fails with:

```
node: error while loading shared libraries: libatomic.so.1: cannot open shared object file: No such file or directory
```

This image is the official runner image plus:

| Package | Why |
| --- | --- |
| `libatomic1` | Required by Node.js ≥ 25 |
| `build-essential` | gcc/g++/make for native modules (`node-gyp`, etc.) |
| `git`, `curl`, `jq`, `ca-certificates` | Common tooling (already in the base image today; listed so they stay there) |

Everything else is unchanged. The image runs as the `runner` user, and its entrypoint, `CMD` and working directory (`/home/runner`) are inherited from upstream, so it works anywhere the official image does.

## Usage

```sh
docker pull ghcr.io/bokvi/actions-runner:latest
```

Available tags:

| Tag | Published when |
| --- | --- |
| `latest` | Every push to `main` |
| `1.2.3` | A `v1.2.3` git tag is pushed |
| `sha-<short-sha>` | A `v*` git tag is pushed (the commit the tag points to) |

Platforms: `linux/amd64`, `linux/arm64`.

### Coolify

In your GitHub Actions runner resource, set the **Runner image** field to:

```
ghcr.io/bokvi/actions-runner:latest
```

Redeploy the runner. To pin a version, use a release tag (for example `ghcr.io/bokvi/actions-runner:1.0.0`) instead of `latest`.

### Actions Runner Controller (ARC)

Set the runner container image in your scale set values:

```yaml
template:
  spec:
    containers:
      - name: runner
        image: ghcr.io/bokvi/actions-runner:latest
        command: ["/home/runner/run.sh"]
```

### Other setups

Anywhere you would use `ghcr.io/actions/actions-runner`, swap in `ghcr.io/bokvi/actions-runner`.

## Building locally

```sh
make build        # build for the host architecture
make test         # build, then check libatomic1 is installed and the user is `runner`
make shell        # build, then open a shell in the image
make build-multi  # build linux/amd64 + linux/arm64 with buildx
make push         # build both platforms and push (needs `docker login ghcr.io`)
```

Override `IMAGE`, `TAG` or `PLATFORMS` as needed, for example `make build TAG=dev`.

## Publishing

[`.github/workflows/publish.yml`](.github/workflows/publish.yml) builds the multi-arch image with Docker Buildx and pushes it to GHCR using the built-in `GITHUB_TOKEN`. It runs on:

- push to `main` → `:latest`
- push of a `v*` tag → `:<version>` and `:sha-<short-sha>`
- manual run (`workflow_dispatch`) → on `main`, the same as a push to `main`

To cut a release:

```sh
git tag v1.0.0
git push origin v1.0.0
```

### Package visibility

The workflow labels the image with `org.opencontainers.image.source`, which links the GHCR package to this public repository, so the package is public and can be pulled anonymously.

If you fork this repo and your package ends up **private** (for example because the repo is private, or because of your account or org package settings), make it public by hand once. `GITHUB_TOKEN` can't change package visibility.

1. Open `https://github.com/users/<owner>/packages/container/actions-runner/settings` (for an org, use `https://github.com/orgs/<org>/packages/container/actions-runner/settings`).
2. Under **Danger Zone**, click **Change visibility**, choose **Public**, and confirm.

## License

[MIT](LICENSE)
