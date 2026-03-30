#!/usr/bin/env python3

import argparse
import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path


logger = logging.getLogger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build an rt_<flavor> BOINC worker binary from Python sources using PyInstaller"
    )
    parser.add_argument("-r", "--runtime-spec", required=True, help="Path to runtime spec JSON")
    parser.add_argument("--src", default="../runner", help="Path to application source directory")
    parser.add_argument("--base-python", default="/usr/bin/python3", help="Path to Python interpreter used to create the build venv")
    parser.add_argument("--out-dir", default=".", help="Output directory for the built executable and build metadata JSON")
    parser.add_argument("--build-dir", default="building", help="Temporary build directory")
    parser.add_argument("--keep-build-dir", default=False, action='store_true', help="Do not delete build dir after execution")
    parser.add_argument("-v", "--version", default="1.0", help="BOINC application version, e.g. 1.0")
    parser.add_argument("-p", "--platform", default="x86_64-pc-linux-gnu", help="BOINC platform identifier")
    parser.add_argument("--pyinstaller-version", default="6.13.0", help="PyInstaller version to install into the build venv")
    return parser.parse_args()


def run(cmd):
    logger.info("Running: %s", " ".join(map(str, cmd)))
    subprocess.run(cmd, check=True)


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    args = parse_args()

    runtime_spec_path = Path(args.runtime_spec).expanduser().resolve()
    src_dir = Path(args.src).expanduser().resolve()
    out_dir = Path(args.out_dir).expanduser().resolve()
    build_dir = Path(args.build_dir).expanduser().resolve()
    base_python = Path(args.base_python).expanduser().resolve()

    with open(runtime_spec_path, "r", encoding="utf-8") as f:
        runtime_spec = json.load(f)

    canonical_runtime_spec = json.dumps(runtime_spec, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    runtime_spec_md5 = hashlib.md5(canonical_runtime_spec.encode("utf-8")).hexdigest()
    flavor = runtime_spec_md5[:16]

    expected_python_version = runtime_spec["python_version"]
    actual_python_version = subprocess.check_output(
        [str(base_python), "-c", "import sys; print(sys.version.split()[0])"],
        text=True,
    ).strip()
    if actual_python_version != expected_python_version:
        raise RuntimeError(f"Base python version mismatch: expected {expected_python_version}, got {actual_python_version}")

    cloudpickle_version = runtime_spec["cloudpickle_version"]

    requirements = list(runtime_spec.get("requirements", []))
    if any(req.startswith("cloudpickle") for req in requirements):
        raise RuntimeError("Do not specify cloudpickle in requirements, use cloudpickle_version instead")
    requirements.append(f"cloudpickle=={cloudpickle_version}")

    modules = list(runtime_spec.get("modules", []))
    if "cloudpickle" in modules:
        raise RuntimeError("Do not specify cloudpickle in modules, it is added automatically")
    modules.append("cloudpickle")

    app_name = f"rt_{flavor}"
    artifact_name = f"{app_name}_{args.version}_{args.platform}"

    if build_dir.exists():
        shutil.rmtree(build_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True)

    try:
        venv_dir = build_dir / "venv"
        run([str(base_python), "-m", "venv", str(venv_dir)])

        if os.name == "nt":
            python_exe = venv_dir / "Scripts" / "python.exe"
        else:
            python_exe = venv_dir / "bin" / "python"

        run([str(python_exe), "-m", "pip", "install", f"pyinstaller=={args.pyinstaller_version}"])
        if requirements:
            run([str(python_exe), "-m", "pip", "install"] + requirements)

        dist_dir = build_dir / "dist"
        work_dir = build_dir / "work"
        spec_dir = build_dir / "spec"

        cmd = [
            str(python_exe), "-m", "PyInstaller",
            "--onefile",
            "--clean",
            "--name", artifact_name,
            "--paths", str(src_dir),
            "--distpath", str(dist_dir),
            "--workpath", str(work_dir),
            "--specpath", str(spec_dir),
        ]
        for module in modules:
            for module in modules:
                if module == "torch":
                    cmd.append("--hidden-import=torch")
                else:
                    cmd.append(f"--collect-all={module}")
        cmd.append(str(src_dir / "__main__.py"))

        run(cmd)

        suffix = ".exe" if os.name == "nt" else ""
        built_artifact = dist_dir / f"{artifact_name}{suffix}"
        final_artifact = out_dir / f"{artifact_name}{suffix}"
        shutil.copy2(built_artifact, final_artifact)

        build_metadata = {
            "app_name": app_name,
            "flavor": flavor,
            "version": args.version,
            "platform": args.platform,
            "artifact_name": artifact_name,
            "runtime_spec_md5": runtime_spec_md5,
            "python_version": expected_python_version,
            "cloudpickle_version": cloudpickle_version,
            "pyinstaller_version": args.pyinstaller_version,
            "requirements": requirements,
            "modules": modules,
            "build_time_utc": datetime.now(timezone.utc).isoformat(),
        }

        with open(out_dir / f"{artifact_name}.build.json", "w", encoding="utf-8") as f:
            json.dump(build_metadata, f, ensure_ascii=False, indent=2)
            f.write("\n")

        logger.info("Built artifact: %s", final_artifact)

    finally:
        if not args.keep_build_dir and build_dir.exists():
            shutil.rmtree(build_dir)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        logger.error("Build failed: %s\n%s", e, traceback.format_exc())
        sys.exit(1)
