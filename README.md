# actions-runner

[![Build and publish](https://github.com/bokvi/actions-runner/actions/workflows/publish.yml/badge.svg)](https://github.com/bokvi/actions-runner/actions/workflows/publish.yml)

A drop-in replacement for the official [`ghcr.io/actions/actions-runner`](https://github.com/actions/runner/pkgs/container/actions-runner) image with **`libatomic1`** pre-installed and **Node.js 24** in the tool cache.

## Why

Node.js 25+ links against `libatomic.so.1`, which the official runner image doesn't ship. Any job that uses Node 25 (for example via `actions/setup-node`) fails with:

```
node: error while loading shared libraries: libatomic.so.1: cannot open shared object file: No such file or directory
```

On ephemeral runners every job also starts with an empty tool cache, so `actions/setup-node` downloads Node in each job. This image ships Node.js 24 in the tool cache, so setup-node logs `Found in cache` instead.

This image is the official runner image plus:

| Package | Why |
| --- | --- |
| `libatomic1` | Required by Node.js ≥ 25 |
| `build-essential` | gcc/g++/make for native modules (`node-gyp`, etc.) |
| `git`, `curl`, `jq`, `ca-certificates` | Common tooling (already in the base image today; listed so they stay there) |
| Node.js 24 (the `node` image in the [`Dockerfile`](Dockerfile)) | In the tool cache at `/opt/hostedtoolcache`, where `RUNNER_TOOL_CACHE` points, so `actions/setup-node` with `node-version: 24` doesn't download it. It isn't on `PATH`; jobs still pick their Node with setup-node |

Everything else is unchanged, except where the tool cache lives. Upstream it's `_work/_tool`; here `RUNNER_TOOL_CACHE` moves it to `/opt/hostedtoolcache`. That matters in two cases:

- A volume you mount at `_work/_tool` to keep tools between runs is no longer used. Mount it at `/opt/hostedtoolcache` instead, or set `RUNNER_TOOL_CACHE` back. A volume there hides the cached Node unless it starts out with the image's content.
- In jobs that run in a `container:`, the runner mounts the tool cache into the container as `/__t`. Where the job container doesn't see the runner's filesystem (a separate Docker-in-Docker daemon that shares only `_work` with the runner, or ARC's Kubernetes container mode), `/__t` doesn't have the cached Node. setup-node inside such a container downloads Node instead, and fails if the container's user can't write to `/__t`, which the daemon may create as root.

The image runs as the `runner` user, and its entrypoint, `CMD` and working directory (`/home/runner`) are inherited from upstream, so it works anywhere the official image does.

## Usage

```sh
docker pull ghcr.io/bokvi/actions-runner:latest
```

Available tags:

| Tag | Published when |
| --- | --- |
| `latest` | Every push to `main` |
| `1.2.3` | A push to `main` releases `v1.2.3` (see [Publishing](#publishing)) |
| `sha-<short-sha>` | A push to `main` releases a version (the released commit) |

[Releases](https://github.com/bokvi/actions-runner/releases) list what changed in each version.

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

For the optional seeded Docker sidecar and npm proxy used by ephemeral Coolify stacks, see
[the prewarming runbook](prewarm/README.md). The ordinary `:latest` runner stays independent
of that infrastructure; `:ci-bokvi` and `:dind` are opt-in variants.

```sh
make build        # build for the host architecture
make test         # build, then check libatomic1, the cached Node.js 24 and npm, and the user `runner`
make shell        # build, then open a shell in the image
make build-multi  # build linux/amd64 + linux/arm64 with buildx
make push         # build both platforms and push (needs `docker login ghcr.io`)
```

Override `IMAGE`, `TAG` or `PLATFORMS` as needed, for example `make build TAG=dev`.

The cached Node.js comes from the official `node` image, pinned by tag and digest in the `Dockerfile`. Dependabot proposes new 24.x releases weekly; a move to another major is a manual change, together with the README.

## Publishing

[`.github/workflows/publish.yml`](.github/workflows/publish.yml) builds the multi-arch image with Docker Buildx and pushes it to GHCR using the built-in `GITHUB_TOKEN`. It runs on a push to `main` and on a manual run (`workflow_dispatch`) on `main`, and:

1. pushes the image as `:latest`;
2. runs [semantic-release](https://semantic-release.gitbook.io/) ([`.releaserc.json`](.releaserc.json)), which derives the next version from the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) since the last release and creates the `v<version>` tag and GitHub release;
3. if a version was released, tags the same image as `:<version>` and `:sha-<short-sha>`.

| Commits since the last release | Release |
| --- | --- |
| A breaking change (`feat!:`, `fix!:` or a `BREAKING CHANGE:` footer) | major |
| `feat` | minor |
| `fix`, `perf` | patch |
| Only other types (`ci`, `chore`, `docs`, …) | none, only `:latest` is updated |

Pull requests are squash-merged, so the PR title decides the release. Don't push `v*` tags by hand.

### Package visibility

The workflow labels the image with `org.opencontainers.image.source`, which links the GHCR package to this public repository, so the package is public and can be pulled anonymously.

If you fork this repo and your package ends up **private** (for example because the repo is private, or because of your account or org package settings), make it public by hand once. `GITHUB_TOKEN` can't change package visibility.

1. Open `https://github.com/users/<owner>/packages/container/actions-runner/settings` (for an org, use `https://github.com/orgs/<org>/packages/container/actions-runner/settings`).
2. Under **Danger Zone**, click **Change visibility**, choose **Public**, and confirm.

## License

[MIT](LICENSE)
