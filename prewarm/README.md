# Ephemeral stack prewarming

This implements the runner-side work in [#4](https://github.com/bokvi/actions-runner/issues/4).
Node 24 is already cached. These opt-in components prepare Docker images and npm downloads
without reusing a job's writable state.

## Components and ownership

| Component | Configuration | Lifetime |
| --- | --- | --- |
| Node tool cache | Root `Dockerfile` | Image content, private container writes |
| Docker seed | `images.txt`, `build.py`, `Dockerfile` | Trusted upstream digests, never job output |
| Docker sidecar | Coolify's `GITHUB_RUNNER_DIND_IMAGE` | One daemon and data volume per stack |
| npm proxy | `npm/compose.yml` on each build host | Public upstream responses, no client publishing |
| npm default | Root Dockerfile's `ci-bokvi` target | User `.npmrc`; npm cache remains private |
| Runner selection | Coolify server's GitHub Runners settings | Applies to new stacks |

Verified against Coolify 4.4.6. Its stack generator is
[`GithubRunnerContainer.php`](https://github.com/coollabsio/coolify/blob/v4.4.6/app/Services/GithubRunner/GithubRunnerContainer.php).
It creates fresh networks and volumes, selects the sidecar through
[`GITHUB_RUNNER_DIND_IMAGE`](https://github.com/coollabsio/coolify/blob/v4.4.6/config/constants.php),
and removes anonymous sidecar volumes with `docker rm -v`. No Coolify source patch is required.
The sidecar setting is global to a Coolify instance: inventory all its pools before changing it.

## Docker seed

Builds run a fresh pinned daemon, pull the exact references in `images.txt`, then stop it.
`pack.sh` captures image/digest metadata and layers. Squashfs preserves Linux ownership,
whiteouts and opaque-directory xattrs; copying layer files through macOS would not.
The seed includes no containers, networks, daemon identity, credentials or job-generated layers.

At startup the sidecar mounts the seed read-only, copies only a small metadata archive to its
private `/var/lib/docker` volume, and uses symlinks to immutable image-layer directories.
New layers and all daemon writes stay on that private filesystem. Image removal/pruning removes
private metadata and symlinks, not the seed. A restart preserves the same stack's changes; a new
stack starts pristine. Different seeds require different empty data volumes.

This uses the **classic `overlay2` image store**, pinned to the Docker version in `Dockerfile`.
The deployed baseline used Docker 29's containerd `overlayfs` store, not a copying `vfs` or
`fuse-overlayfs` driver. This change prepares image layers in advance rather than assuming a
copying driver caused slow creates. Seed layout is Docker-internal: every Docker upgrade must
rebuild and pass real-daemon tests on both architectures before rollout.

Requirements: Linux with Squashfs and loop devices, a real filesystem-backed private data volume,
and Coolify's **Docker (privileged)** mode. Sysbox and No Docker modes are not supported.
Do not switch an isolated pool to privileged mode to use this seed. It does not strengthen the
existing privileged mode's host security boundary.

```sh
make build-dind                  # native architecture; privileged Docker required
make test-dind                   # two stacks, exact pins, restart, isolation and miss
```

The `Prewarm` workflow runs natively on amd64 and arm64. Successful `main` runs publish
`:dind-<full-commit>-amd64`, `:dind-<full-commit>-arm64`, and combined `:dind-<full-commit>` / `:dind`
tags in `ghcr.io/bokvi/actions-runner`. Pin the combined image by digest for deployment.

Keep `images.txt` aligned with the consumer's `config.playwrightImage` and `TEST_IMAGE`.
Remove the Node test image when the consumer stops using it. An unseeded pin still pulls normally.
Never add private images to this public seed. Refresh through reviewed main-branch changes,
never from job-produced state. Dependabot updates the sidecar/proxy bases; consumer image pins
must be updated alongside the consumer's own version decision.

## npm proxy

The proxy forwards only to `https://registry.npmjs.org`, verifies upstream TLS, and strips client
credentials and cookies. GET/HEAD responses are cacheable. Publishing methods are rejected.
Only npm's two audit-query POST endpoints are forwarded uncached, including their content
encoding. npm integrity checks remain enabled. Audit/metadata requests are distinct from tarballs.

Upstream cache directives control freshness. The CDN bot cookie is stripped so it cannot disable
public-response caching. Access logs contain status, `tarball`/`metadata`, and cache outcome,
without dependency names. The proxy is an availability dependency: roll back the runner image
if it is unavailable.

On the build host, verify `docker0` is `172.17.0.1` (or override the compose binding and the runner
target's `NPM_REGISTRY` build argument), then run:

```sh
docker compose -p runner-npm-cache -f prewarm/npm/compose.yml up -d --wait
python3 prewarm/npm/warm.py /private/path/package-lock.json --registry http://172.17.0.1:4873
```

The port binds only to the Docker bridge, not public interfaces. Verify reachability from a fresh
Coolify runner network. The proxy has a 10 GB bounded cache. Warming reads public tarball URLs
from a trusted npm v2/v3 lockfile; other sources are counted and skipped. Keep private lockfiles
outside this public checkout and remove temporary copies. Warm the trusted default-branch
lockfile again when dependencies change.

The `:ci-bokvi` variant sets a user `.npmrc` default, not an overriding environment variable.
Project/scoped registry configuration still wins. Repositories using private npm packages must
configure their authenticated upstream directly in project/scoped registry settings; this proxy
deliberately does not handle credentials.

Local verification:

```sh
NPM_PROXY_BIND=127.0.0.1 NPM_PROXY_PORT=14873 \
  docker compose -p prewarm-test -f prewarm/npm/compose.yml up -d --wait
python3 prewarm/npm/test.py --network prewarm-test_default
docker compose -p prewarm-test -f prewarm/npm/compose.yml down -v
```

## Rollout and rollback

1. Run `make test`, `make build-multi`, `make build-dind`, `make test-dind`, and npm verification.
   Record the image digest and output. Wait for both native `Prewarm` jobs to pass.
2. Deploy and warm the npm proxy on the build host. A fresh npm cache must produce
   `200 tarball HIT` requests; count audit/metadata traffic separately.
3. Pull the pinned seed and runner images onto each build host before selecting them. Coolify
   checks/pulls the runner image on each start; its large layers must already be local.
4. Persist `GITHUB_RUNNER_DIND_IMAGE=ghcr.io/bokvi/actions-runner@sha256:<seed-digest>` in the
   Coolify instance's `/data/coolify/source/.env`. Rebuild its Laravel configuration cache and
   gracefully restart queue workers (`php artisan config:cache`, `php artisan queue:restart`
   inside the Coolify container). Verify `config('constants.github_runner.dind_image')`.
5. In the server's GitHub Runners settings, select the published `ci-bokvi` image by digest.
   Preserve labels, concurrency, limits and Docker mode. Existing jobs finish on their current
   stacks; the settings apply to future stacks.
6. Verify fresh jobs log cached Node, no seeded-image pulls, and warm npm tarballs. Record
   first/second create times, startup latency and concurrent starts against the original setup
   on the same host. Separate preparation gains from unrelated test/queue time.

Rollback: restore the previous runner and sidecar image settings, refresh Coolify's configuration
and workers, and let existing jobs finish. Remove the proxy only after no runner uses it.
Retain old digests until validation completes. Never migrate a live job's Docker root or reuse
a seeded volume with a different daemon image.

Publishing does not prove rollout, CI savings or startup throughput. Record deployment evidence
in the PR/issue and keep #4 and bokvi/id#159 open until their acceptance criteria are checked.
Capacity tuning is bokvi/id#160; stale npm-cache comments in consumer workflows remain a linked
follow-up.
