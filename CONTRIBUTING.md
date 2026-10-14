# Contributing

This repository follows the Git conventions in [Dotykacka/docs-git](https://github.com/Dotykacka/docs-git) ([CONTRIBUTING.md](https://github.com/Dotykacka/docs-git/blob/main/CONTRIBUTING.md)). In short:

- **No direct pushes to `main`.** Every change goes through a pull request, which is squash-merged.
- **Branches** are named `<prefix>/<short-description>` in kebab-case, with the prefix `feat/`, `fix/`, `test/`, `chore/`, `docs/` or `ci/`.
- **Commit messages and PR titles** are [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/): `<type>[(scope)][!]: <description>`, imperative mood, lowercase, no trailing period, 72 characters at most. The squash commit uses the PR title.
- **Actions** in workflows are pinned to a full-length commit SHA with the version in a comment. Dependabot keeps the pins up to date.

## Building and testing

Requires Docker with Buildx.

```sh
make test         # build for the host architecture, check libatomic1, gh, the AWS CLI, the cached Node.js and the runner user
make build-multi  # build linux/amd64 and linux/arm64
```

For stack prewarming, also run `make build-dind`, `make test-dind`, and the npm proxy verification
in [prewarm/README.md](prewarm/README.md). The `Prewarm` workflow checks both native architectures
before publishing the DinD seed from `main`.

## Checks

Pull requests must pass the **Lint** workflow, which runs [commitlint](https://commitlint.js.org/) ([`commitlint.config.mjs`](commitlint.config.mjs)) on the PR title and every commit. **Build and publish** runs on `main` and on `v*` tags.

## Scopes

No scopes are defined. Use one only when it makes a change clearer, for example `ci(publish): …`.

## Releases

`main` publishes `ghcr.io/bokvi/actions-runner:latest`. To publish a version, tag the commit on `main` as `v<major>.<minor>.<patch>` and push the tag:

```sh
git tag v1.0.0
git push origin v1.0.0
```

## Credentials

The publish workflow pushes to GHCR with the job's short-lived `GITHUB_TOKEN` (`packages: write`). No long-lived secrets are stored, and OIDC is not needed: GHCR accepts `GITHUB_TOKEN` directly.

## Exceptions

[`.github/repo-config.yml`](.github/repo-config.yml) lists the rules this repository deliberately differs from, and why:

- `repo-name`: this repository is in the bokvi organization, not Dotykacka, so the Dotykacka naming prefixes don't apply. The name mirrors the upstream `actions-runner` image.
- `review-approvals` (`0`): it has a single maintainer. Pull requests are still required but need no approving review.
