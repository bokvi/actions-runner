#!/usr/bin/env python3
"""Exercise exact pins, private state, restarts and cache misses in real DinD."""
import argparse
import concurrent.futures
import io
import json
import pathlib
import subprocess
import tarfile
import time
import uuid

from build import HERE, pins, ready, run

MISS = "alpine:3.24@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True)
    parser.add_argument("--images", type=pathlib.Path, default=HERE / "images.txt")
    args = parser.parse_args()
    images = pins(args.images)
    prefix = "runner-prewarm-test-" + uuid.uuid4().hex[:12]
    names = [prefix + "-a", prefix + "-b"]
    report = {"startup_seconds": {}, "create_seconds": {}}

    def start(name):
        begin = time.monotonic()
        run("docker", "run", "-d", "--privileged", "--name", name,
            "-e", "DOCKER_TLS_CERTDIR=", args.image,
            "dockerd", "--host=unix:///var/run/docker.sock")
        ready(name)
        return time.monotonic() - begin

    def inner(name, *command, **kwargs):
        return run("docker", "exec", name, "docker", *command, **kwargs)

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            for name, duration in zip(names, executor.map(start, names)):
                report["startup_seconds"][name[-1]] = round(duration, 3)
        # Must work before any create marks a pulled top layer committed.
        for image in images:
            inner(names[0], "image", "save", image, stdout=subprocess.DEVNULL)
        report["export_before_create"] = "passed"
        for name in names:
            driver = inner(name, "info", "--format", "{{.Driver}}",
                           capture_output=True, text=True).stdout.strip()
            assert driver == "overlay2", driver
            for image in images:
                timings = []
                for _ in range(2):
                    begin = time.monotonic()
                    container = inner(name, "create", "--pull=never", image, "node", "--version",
                                      capture_output=True, text=True).stdout.strip()
                    timings.append(round(time.monotonic() - begin, 3))
                    inner(name, "start", "-a", container)
                    inner(name, "rm", container)
                report["create_seconds"][name[-1] + ":" + image.split("@", 1)[0]] = timings
                if "mcr.microsoft.com/playwright:" in image:
                    script = """set -eu
browser=$(find /ms-playwright -name chrome -type f | head -n 1)
test -n "$browser"
"$browser" --headless --no-sandbox --disable-gpu --dump-dom 'data:text/html,seed-ok'
"""
                    browser = inner(name, "run", "--rm", "--pull=never", "--init", "--shm-size=1g",
                                    image, "sh", "-c", script, capture_output=True, text=True)
                    assert "seed-ok" in browser.stdout, browser.stderr
                    report["chromium"] = "headless page rendered in both stacks"
        # Consumers also build new layers from seeded images; these writes must
        # stay private and support normal image export.
        dockerfile = ("FROM " + images[-1] + "\nRUN echo build-ok >/seed-build-proof\n").encode()
        context = io.BytesIO()
        with tarfile.open(fileobj=context, mode="w") as archive:
            info = tarfile.TarInfo("Dockerfile")
            info.size = len(dockerfile)
            archive.addfile(info, io.BytesIO(dockerfile))
        run("docker", "exec", "-i", names[0], "docker", "build", "-t", "seed-build-proof", "-",
            input=context.getvalue())
        output = inner(names[0], "run", "--rm", "seed-build-proof", "cat", "/seed-build-proof",
                       capture_output=True, text=True).stdout.strip()
        assert output == "build-ok", output
        inner(names[0], "image", "save", "seed-build-proof", stdout=subprocess.DEVNULL)
        inner(names[0], "image", "rm", "seed-build-proof")
        report["build_and_export"] = "passed"
        # The backing seed is read-only; each daemon still supports normal removal.
        result = subprocess.run(["docker", "exec", names[0], "touch", "/opt/docker-seed/poison"],
                                capture_output=True)
        assert result.returncode != 0, "seed unexpectedly writable"
        inner(names[0], "volume", "create", "job-private-marker")
        inner(names[0], "image", "rm", *images)
        # Restart must not resurrect deleted images or discard private state.
        run("docker", "restart", names[0])
        ready(names[0])
        result = subprocess.run(["docker", "exec", names[0], "docker", "image", "inspect", images[0]],
                                capture_output=True)
        assert result.returncode != 0, "restart resurrected a removed image"
        inner(names[0], "volume", "inspect", "job-private-marker", stdout=subprocess.DEVNULL)
        result = subprocess.run(["docker", "exec", names[1], "docker", "volume", "inspect", "job-private-marker"],
                                capture_output=True)
        assert result.returncode != 0, "a job's volume leaked into another daemon"
        for image in images:
            inner(names[1], "run", "--rm", "--pull=never", image, "node", "--version")
        # A new pin falls back to an ordinary pull into this stack only.
        inner(names[0], "run", "--rm", MISS, "echo", "cache-miss-ok")
        result = subprocess.run(["docker", "exec", names[1], "docker", "image", "inspect", MISS],
                                capture_output=True)
        assert result.returncode != 0, "a job's pulled image leaked into another daemon"
        # A later stack also gets the pristine seed, not the preceding job's state.
        run("docker", "rm", "-f", "-v", names[0])
        start(names[0])
        inner(names[0], "run", "--rm", "--pull=never", images[0], "node", "--version")
        report["isolation_restart_and_miss"] = "passed"
        print(json.dumps(report, indent=2))
    finally:
        subprocess.run(["docker", "rm", "-f", "-v", *names],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
