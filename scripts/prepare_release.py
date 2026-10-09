"""Build a source-only ZIP from git-tracked files. Never includes .env, weights or local data."""

import subprocess
import zipfile
from pathlib import Path


def main():
    files = subprocess.check_output(["git", "ls-files", "-z"]).decode().split("\0")
    files = [Path(file) for file in files if file]
    if not files:
        raise SystemExit("Stage the intended release files with git add first.")
    forbidden = {".env", ".venv", ".cache", "data", "artifacts", ".git"}
    for file in files:
        if any(part in forbidden for part in file.parts):
            raise SystemExit(f"Refusing to package a private or runtime path: {file}")
        if file.stat().st_size > 5_000_000:
            raise SystemExit(f"Review unexpectedly large file before release: {file}")
    output = Path("dist/nocap-source.zip")
    output.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for file in files:
            archive.write(file, "nocap/" + file.as_posix())
    print(f"Built {output}: {len(files)} tracked files, {output.stat().st_size:,} bytes.")


if __name__ == "__main__":
    main()
