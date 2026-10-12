#!/usr/bin/env python3
"""Prime public npm tarballs from a trusted lockfile; do not publish the lockfile."""
import argparse
import concurrent.futures
import json
import urllib.parse
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("lockfile")
    parser.add_argument("--registry", required=True)
    args = parser.parse_args()
    registry = urllib.parse.urlsplit(args.registry)
    if registry.scheme not in ("http", "https") or not registry.netloc or registry.query or registry.fragment:
        parser.error("registry must be an http(s) base URL")
    with open(args.lockfile) as file:
        lock = json.load(file)
    if lock.get("lockfileVersion") not in (2, 3) or "packages" not in lock:
        parser.error("expected npm lockfileVersion 2 or 3")
    urls = set()
    skipped = 0
    for package in lock["packages"].values():
        resolved = package.get("resolved", "")
        source = urllib.parse.urlsplit(resolved)
        if source.scheme == "https" and source.netloc == "registry.npmjs.org" and source.path.endswith(".tgz"):
            urls.add(args.registry.rstrip("/") + source.path)
        elif resolved:
            skipped += 1

    def fetch(url):
        with urllib.request.urlopen(url, timeout=120) as response:
            while response.read(1024 * 1024):
                pass

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        list(executor.map(fetch, sorted(urls)))
    print(json.dumps({"public_tarballs_warmed": len(urls), "other_sources_skipped": skipped}))


if __name__ == "__main__":
    main()
