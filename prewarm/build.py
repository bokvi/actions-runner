#!/usr/bin/env python3
"""Build a trusted, native-architecture DinD seed. Never accepts job cache state."""
import argparse
import pathlib
import re
import shutil
import subprocess
import tempfile
import time
import uuid

HERE = pathlib.Path(__file__).resolve().parent


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def pins(path):
    values = [s.strip() for s in path.read_text().splitlines()
              if s.strip() and not s.lstrip().startswith("#")]
    if not values or any(not re.fullmatch(r"[a-zA-Z0-9./:_-]+@sha256:[a-f0-9]{64}", s)
                         for s in values):
        raise ValueError("image list must contain full sha256-pinned public references")
    return values


def ready(name, timeout=60):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        result = subprocess.run(["docker", "exec", name, "docker", "info"],
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if result.returncode == 0:
            return time.monotonic() - start
        state = subprocess.run(["docker", "inspect", "--format", "{{.State.Running}}", name],
                               capture_output=True, text=True)
        if state.stdout.strip() != "true":
            break
        time.sleep(0.2)
    subprocess.run(["docker", "logs", "--tail", "30", name])
    raise RuntimeError(f"{name}: daemon did not become ready")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--images", type=pathlib.Path, default=HERE / "images.txt")
    args = parser.parse_args()
    images = pins(args.images)
    name = "runner-seed-" + uuid.uuid4().hex[:12]
    tools = name + ":tools"
    pack = name + "-pack"
    data, output = name + "-data", name + "-output"
    try:
        run("docker", "build", "--target", "tools", "-t", tools, str(HERE))
        run("docker", "volume", "create", data)
        run("docker", "volume", "create", output)
        run("docker", "run", "-d", "--privileged", "--name", name,
            "-v", data + ":/var/lib/docker", "-e", "DOCKER_TLS_CERTDIR=", tools,
            "dockerd", "--host=unix:///var/run/docker.sock",
            "--storage-driver=overlay2", "--feature", "containerd-snapshotter=false")
        ready(name)
        for image in images:
            run("docker", "exec", name, "docker", "pull", image)
        run("docker", "stop", "--timeout", "30", name)
        # The stopped daemon has only pulled trusted images. Preserve its exact
        # digest metadata and filesystem semantics inside an immutable archive.
        # CAP_SYS_ADMIN is needed to read trusted.overlay.* xattrs faithfully.
        run("docker", "create", "--privileged", "--name", pack, "--entrypoint", "sh",
            "-v", data + ":/data:ro", "-v", output + ":/out", tools, "/pack.sh")
        run("docker", "cp", str(HERE / "pack.sh"), pack + ":/pack.sh")
        run("docker", "start", "-a", pack)
        code = run("docker", "inspect", "--format", "{{.State.ExitCode}}", pack,
                   capture_output=True, text=True).stdout.strip()
        if code != "0":
            raise RuntimeError(f"packing seed exited {code}")
        with tempfile.TemporaryDirectory(prefix=name) as tmp:
            context = pathlib.Path(tmp)
            for file in ("seed.squashfs", "metadata.tar", "seed-id"):
                run("docker", "cp", f"{pack}:/out/{file}", str(context / file))
            for file in ("Dockerfile", "entrypoint.sh"):
                shutil.copyfile(HERE / file, context / file)
            run("docker", "build", "--target", "runtime", "-t", args.tag, str(context))
    finally:
        subprocess.run(["docker", "rm", "-f", "-v", name, pack],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["docker", "volume", "rm", data, output],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["docker", "image", "rm", tools],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


if __name__ == "__main__":
    main()
