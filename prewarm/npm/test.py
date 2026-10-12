#!/usr/bin/env python3
"""Check the proxy with fresh npm caches and attempted registry writes."""
import argparse
import json
import subprocess
import time
import urllib.error
import urllib.request

NODE = "node:24-bookworm@sha256:64af3819f9275802414d7cdc38c27e9d82bd564dec4d4da87d008255d36c63b4"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", default="http://127.0.0.1:14873")
    parser.add_argument("--network", required=True)
    args = parser.parse_args()
    url = args.registry + "/is-number/-/is-number-7.0.0.tgz"
    with urllib.request.urlopen(url, timeout=60) as response:
        original = response.read()
    # The first response can finish reaching the client just before nginx commits
    # its cache file. Wait only for that bounded write, not a fresh upstream fill.
    for attempt in range(10):
        with urllib.request.urlopen(url, timeout=60) as response:
            assert response.read() == original
            if response.headers["X-Cache-Status"] == "HIT":
                break
        time.sleep(0.1)
    else:
        raise AssertionError("tarball did not become a cache hit")
    for method in ("PUT", "POST", "DELETE", "PATCH"):
        request = urllib.request.Request(url, data=b"poison", method=method)
        try:
            urllib.request.urlopen(request, timeout=30)
            raise AssertionError(f"{method} unexpectedly accepted")
        except urllib.error.HTTPError as error:
            assert error.code == 405, (method, error.code)
    # npm rewrites npmjs.org lockfile URLs for the configured registry. Each
    # container has a new writable local cache; no npm cache volume is shared.
    script = """set -eu
printf 'registry=http://registry:8080\n' > /root/.npmrc
mkdir /work && cd /work
printf '{"dependencies":{"is-number":"7.0.0"}}\n' > package.json
npm install --package-lock-only --ignore-scripts --no-audit --no-fund
npm ci --ignore-scripts --no-fund
npm audit --audit-level=low
test "$(node -p 'require("is-number")(42)')" = true
npm install is-number@6.0.0 --ignore-scripts --no-audit --no-fund
"""
    for _ in range(2):
        subprocess.run(["docker", "run", "--rm", "--network", args.network, NODE,
                        "sh", "-c", script], check=True)
    with urllib.request.urlopen(url, timeout=60) as response:
        assert response.read() == original
        assert response.headers["X-Cache-Status"] == "HIT"
    print(json.dumps({"warm_tarball": "HIT", "write_methods": "rejected",
                      "fresh_npm_caches": 2, "dependency_miss_and_audit": "passed"}))


if __name__ == "__main__":
    main()
