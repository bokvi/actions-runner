FROM docker:29.8-dind@sha256:1e08cdb63405ca788aea94ef35b792d1e299607c667d33d7bcbcae1fd2611ced AS tools
# Squashfs preserves overlay whiteouts, opaque-directory xattrs and ownership.
# Keeping it compressed avoids copying gigabytes into every new Docker volume.
RUN apk add --no-cache squashfs-tools mount losetup

FROM tools AS runtime
COPY seed.squashfs metadata.tar seed-id /opt/prewarm/
COPY --chmod=0755 entrypoint.sh /usr/local/bin/prewarm-entrypoint.sh
ENTRYPOINT ["prewarm-entrypoint.sh"]
