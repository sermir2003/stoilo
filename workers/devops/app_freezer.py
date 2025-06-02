#!/usr/bin/env python3
import argparse
import hashlib
import logging
import os
import re
import subprocess
import sys
import shutil
import venv
from pathlib import Path
import string
import yaml

logger = logging.getLogger(__name__)

def parse_args():
    parser = argparse.ArgumentParser(description='Freezes an executable file from raboshka using PyInstaller')
    parser.add_argument('--app-name', default='raboshka', help='App name')
    parser.add_argument('--version', default='1.0', help='App version for BOINC')
    parser.add_argument('--platform', default='x86_64-pc-linux-gnu', help='BOINC platform identifier')
    parser.add_argument('--pyinstaller-version', default='==6.13.0', help='PyInstaller version in the format (>=/==/<=)a.b.c')
    return parser.parse_args()


def to_base62(num: int) -> str:
    BASE62_ALPHABET = string.digits + string.ascii_uppercase + string.ascii_lowercase
    if num == 0:
        return BASE62_ALPHABET[0]
    chars = []
    base = len(BASE62_ALPHABET)
    while num:
        num, rem = divmod(num, base)
        chars.append(BASE62_ALPHABET[rem])
    chars.reverse()
    return ''.join(chars)


def get_dependencies_hash_base62(dependencies_path):
    with open(dependencies_path, 'rb') as f:
        blob = f.read()
    digest = hashlib.md5(blob).digest()
    num = int.from_bytes(digest, byteorder='big')
    str_code = to_base62(num)
    return str_code


def get_dependencies_hash(dependencies_path):
    with open(dependencies_path, 'rb') as f:
        blob = f.read()
    return  hashlib.md5(blob).hexdigest()

def create_venv(venv_dir):
    logger.info("Creating virtual environment...")
    venv.create(venv_dir, with_pip=True)

    if os.name == 'nt':  # Windows
        python_exe = venv_dir / "Scripts" / "python.exe"
        pip_exe = venv_dir / "Scripts" / "pip.exe"
    else:  # Unix/Linux/Mac
        python_exe = venv_dir / "bin" / "python"
        pip_exe = venv_dir / "bin" / "pip"
    
    logger.info(f"venv created at {venv_dir}\n")
    return python_exe, pip_exe


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    args = parse_args()

    script_dir = Path(__file__).resolve().parent
    apps_dir = script_dir.parent
    building_dir = script_dir / "building"

    if building_dir.exists():
        shutil.rmtree(building_dir)
    
    try:
        python_exe, pip_exe = create_venv(building_dir / "venv")

        shutil.copytree(apps_dir / "src" / args.app_name, building_dir / args.app_name)

        with open("dependencies.yaml", "r") as file:
            data = yaml.safe_load(file)
        requirements = data.get("requirements", [])
        modules = data.get("modules", [])
    
        flavor = get_dependencies_hash("dependencies.yaml")
        binary_name = f"{args.app_name}_{flavor}_{args.version}_{args.platform}"
        output_dir = apps_dir / "apps" / f"{args.app_name}_{flavor}" / args.version / args.platform
        os.makedirs(output_dir, exist_ok=True)
        specifications_dir = apps_dir / "flavor_specs"
        
        try:
            logger.info(f"Installing PyInstaller...")
            subprocess.run([str(pip_exe), "install", f"pyinstaller{args.pyinstaller_version}"], check=True)
            for package in requirements:
                logger.info(f"Installing: {package}...")
                subprocess.run([str(pip_exe), "install", package], check=True)
        except Exception as e:
            logger.error(f"Error installing pip packages: {e}", file=sys.stderr)
            sys.exit(1)
        logger.info("pip packages installed successfully!\n\n")
        
        try:
            hidden_imports = []
            for module in modules:
                hidden_imports.append(f"--hidden-import={module}")
            if "cloudpickle" not in modules:
                hidden_imports.append("--hidden-import=cloudpickle")

            cmd = [
                str(python_exe),
                "-m",
                "PyInstaller",
                "--onefile",
                "--clean",
                "--name", binary_name,
                "--paths", str(building_dir / args.app_name),
                f"--collect-all={args.app_name}",
                "--distpath", str(output_dir),
                "--workpath", str(building_dir / "build"),
                "--specpath", str(building_dir / "spec"),
            ] + hidden_imports + [
                str(building_dir / args.app_name / "__main__.py")
            ]
            
            logger.info(f"Running PyInstaller: {' '.join(cmd)}\n")
            subprocess.run(cmd, check=True)
            shutil.copy("dependencies.yaml", specifications_dir / f"{args.app_name}_{flavor}.yaml")
            
            logger.info(f"Successfully freezed {binary_name}")
            
        except Exception as e:
            logger.error(f"Error building executable: {e}", file=sys.stderr)
            sys.exit(1)
    finally:
        if building_dir.exists():
            shutil.rmtree(building_dir)

if __name__ == "__main__":
    main()
