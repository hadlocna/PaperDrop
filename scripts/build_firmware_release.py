#!/usr/bin/env python3
import argparse
import hashlib
import json
import tarfile
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def display_path(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except ValueError:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a PaperDrop OTA firmware package.")
    parser.add_argument("version", help="Firmware version to package, for example 1.1.0")
    parser.add_argument(
        "--output-dir",
        default="build/firmware",
        help="Directory to write the tar.gz package and manifest",
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    source_dir = repo_root / "agent" / "src"
    output_dir = repo_root / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    package_path = output_dir / f"paperdrop-agent-{args.version}.tar.gz"
    manifest_path = output_dir / f"paperdrop-agent-{args.version}.json"

    with tarfile.open(package_path, "w:gz") as tar:
        for path in sorted(source_dir.rglob("*")):
            if not path.is_file():
                continue
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            arcname = Path("agent") / "src" / path.relative_to(source_dir)
            tar.add(path, arcname=arcname)

    checksum = sha256_file(package_path)
    manifest = {
        "version": args.version,
        "package": display_path(package_path, repo_root),
        "sha256": checksum,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    print(f"package={package_path}")
    print(f"sha256={checksum}")
    print(f"manifest={manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
