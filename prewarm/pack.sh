#!/bin/sh
set -eu
mkdir -p /out/metadata/overlay2
cp -a /data/image /out/metadata/
cp -a /data/overlay2/l /out/metadata/overlay2/
for diff in /data/overlay2/*/diff; do
    [ -d "$diff" ] || { echo "no seeded layers" >&2; exit 1; }
    layer=$(basename "$(dirname "$diff")")
    mkdir "/out/metadata/overlay2/$layer"
    for file in link lower committed; do
        if [ -f "/data/overlay2/$layer/$file" ]; then
            cp -p "/data/overlay2/$layer/$file" "/out/metadata/overlay2/$layer/"
        fi
    done
    ln -s "/opt/docker-seed/overlay2/$layer/diff" "/out/metadata/overlay2/$layer/diff"
done
tar -cpf /out/metadata.tar -C /out/metadata .
mksquashfs /data/image /data/overlay2 /out/seed.squashfs \
    -noappend -processors 2 -no-progress
sha256sum /out/seed.squashfs | cut -d ' ' -f 1 > /out/seed-id
