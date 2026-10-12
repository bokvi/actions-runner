#!/bin/sh
set -eu

case "${1:-}" in
    dockerd|""|-*) ;;
    *) exec /usr/local/bin/dockerd-entrypoint.sh "$@" ;;
esac

# This image deliberately supports the stock, per-stack data volume only.
for arg in "$@"; do
    case "$arg" in
        --data-root*|--storage-driver*|-s|--feature*|--config-file*)
            echo "prewarm: daemon storage overrides are not supported" >&2
            exit 1
            ;;
    esac
done

root=/var/lib/docker
seed=/opt/docker-seed
mkdir -p "$root" "$seed"
case "$(stat -f -c %T "$root")" in
    overlay*) echo "prewarm: mount a private filesystem-backed volume at $root" >&2; exit 1 ;;
esac

mount -t squashfs -o loop,ro,nodev,nosuid /opt/prewarm/seed.squashfs "$seed"
if [ -e "$root/.prewarm-seed" ]; then
    # Restarting the same stack keeps its private changes, including image removals.
    cmp /opt/prewarm/seed-id "$root/.prewarm-seed" || {
        echo "prewarm: a new seed requires a fresh data volume" >&2
        exit 1
    }
else
    if [ -n "$(ls -A "$root")" ]; then
        echo "prewarm: refusing to initialize an existing Docker data directory" >&2
        exit 1
    fi
    tar -xpf /opt/prewarm/metadata.tar -C "$root"
    cp /opt/prewarm/seed-id "$root/.prewarm-seed"
fi

# overlay2's image layers resolve through private symlinks to the read-only seed.
# New layers, containers, images and all daemon metadata live on the private volume.
# There is no host Docker socket or job-writable shared cache.
exec /usr/local/bin/dockerd-entrypoint.sh "$@" \
    --storage-driver=overlay2 --feature containerd-snapshotter=false
