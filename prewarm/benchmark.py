#!/usr/bin/env python3
"""Compare stock and seeded sidecars on one host; does not alter the live pool."""
import argparse
import concurrent.futures
import json
import subprocess
import time
import uuid

from build import HERE, pins, ready, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", required=True)
    parser.add_argument("--baseline", default="docker:29.8-dind@sha256:1e08cdb63405ca788aea94ef35b792d1e299607c667d33d7bcbcae1fd2611ced")
    parser.add_argument("--cpus", default="3")
    args = parser.parse_args()
    images = pins(HERE / "images.txt")
    prefix = "runner-benchmark-" + uuid.uuid4().hex[:12]
    names = []
    result = {"cpu_limit": args.cpus, "scope": "sidecar only; excludes Coolify/GitHub registration"}

    def start(name, image):
        begin = time.monotonic()
        run("docker", "run", "-d", "--privileged", "--cpus", args.cpus, "--name", name,
            "-e", "DOCKER_TLS_CERTDIR=", image, "dockerd", "--host=unix:///var/run/docker.sock",
            stdout=subprocess.DEVNULL)
        ready(name)
        return round(time.monotonic() - begin, 3)

    try:
        for kind, image in (("baseline", args.baseline), ("seeded", args.seed)):
            # Host image downloads/unpacking are deliberately outside the timer.
            run("docker", "image", "inspect", image, stdout=subprocess.DEVNULL)
            name = prefix + "-" + kind
            names.append(name)
            record = {"startup_seconds": start(name, image), "images": {}}
            record["driver"] = run("docker", "exec", name, "docker", "info", "--format", "{{.Driver}}",
                                   capture_output=True, text=True).stdout.strip()
            for pin in images:
                stats = {}
                if kind == "baseline":
                    begin = time.monotonic()
                    run("docker", "exec", name, "docker", "pull", pin, stdout=subprocess.DEVNULL)
                    stats["pull_seconds"] = round(time.monotonic() - begin, 3)
                else:
                    stats["pull_seconds"] = 0
                stats["create_seconds"] = []
                for _ in range(2):
                    begin = time.monotonic()
                    container = run("docker", "exec", name, "docker", "create", "--pull=never", pin,
                                    "node", "--version", capture_output=True, text=True).stdout.strip()
                    stats["create_seconds"].append(round(time.monotonic() - begin, 3))
                    run("docker", "exec", name, "docker", "rm", container, stdout=subprocess.DEVNULL)
                record["images"][pin.split("@", 1)[0]] = stats
            run("docker", "rm", "-f", "-v", name, stdout=subprocess.DEVNULL)
            # Repeat concurrent starts with fresh volumes to expose per-stack copy costs.
            pairs = []
            for sample in range(3):
                pair = [f"{name}-{sample}-{index}" for index in range(2)]
                names.extend(pair)
                begin = time.monotonic()
                with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                    durations = list(executor.map(lambda item: start(item, image), pair))
                pairs.append({"ready_seconds": durations, "batch_seconds": round(time.monotonic() - begin, 3)})
                run("docker", "rm", "-f", "-v", *pair, stdout=subprocess.DEVNULL)
            record["concurrent_starts"] = pairs
            result[kind] = record
        print(json.dumps(result, indent=2))
    finally:
        subprocess.run(["docker", "rm", "-f", "-v", *names],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
