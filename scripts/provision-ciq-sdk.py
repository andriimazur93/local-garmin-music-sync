"""Install the pinned Garmin Linux SDK from a verified archive."""

import argparse
import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import zipfile


SDK_URL = "https://developer.garmin.com/downloads/connect-iq/sdks/connectiq-sdk-lin-9.3.0-2026-10-20-95888f262.zip"
SDK_SHA256 = "1653cc98edd70029670a3e3fcd4ad6e746974a8b758a7b736a4e11506dfd8bc8"


def install_archive(archive: Path, destination: Path, expected_sha256: str) -> None:
    if destination.exists():
        raise ValueError("SDK destination already exists")
    digest = hashlib.sha256()
    with archive.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    if digest.hexdigest() != expected_sha256:
        raise ValueError("SDK archive checksum does not match")

    with zipfile.ZipFile(archive) as zf:
        for item in zf.infolist():
            path = PurePosixPath(item.filename)
            mode = item.external_attr >> 16
            if (path.is_absolute() or ".." in path.parts or "\\" in item.filename
                    or stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR))):
                raise ValueError("SDK archive contains an unsafe entry")
        if "bin/monkeyc" not in zf.namelist():
            raise ValueError("SDK archive does not contain the compiler")
        staging = Path(tempfile.mkdtemp(prefix=".ciq-sdk-", dir=destination.parent))
        try:
            for item in zf.infolist():
                target = staging.joinpath(*PurePosixPath(item.filename).parts)
                if item.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(item) as source, target.open("wb") as output:
                    shutil.copyfileobj(source, output)
                mode = (item.external_attr >> 16) & 0o777
                if mode:
                    target.chmod(mode)
            if not os.access(staging / "bin/monkeyc", os.X_OK):
                raise ValueError("SDK compiler is not executable")
            if destination.exists():
                raise ValueError("SDK destination already exists")
            staging.rename(destination)
        finally:
            if staging.exists():
                shutil.rmtree(staging)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    install_archive(args.archive, args.destination, SDK_SHA256)
    print("Verified Connect IQ SDK 9.3.0 installed")
