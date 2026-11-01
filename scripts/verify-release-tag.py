"""Verify a release tag identifies the clean checkout's watch version."""

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def verify(repo: Path, tag: str) -> None:
    if not re.fullmatch(r"v(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)", tag):
        raise ValueError("Release tag must use vMAJOR.MINOR.PATCH")

    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(repo), *args], check=True, text=True,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        ).stdout.strip()

    if git("status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Release checkout must be clean")
    root = ET.parse(repo / "watch/manifest.xml").getroot()
    app = root.find("{http://www.garmin.com/xml/connectiq}application")
    if app is None or tag != "v" + app.get("version", ""):
        raise ValueError("Release tag does not match watch manifest version")
    if git("rev-parse", "--verify", f"refs/tags/{tag}^{{commit}}") != git("rev-parse", "HEAD"):
        raise ValueError("Release tag does not identify HEAD")
    git("merge-base", "--is-ancestor", "HEAD", "refs/remotes/origin/main")


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("Usage: verify-release-tag.py REPOSITORY TAG")
        verify(Path(sys.argv[1]), sys.argv[2])
    except (ValueError, OSError, ET.ParseError, subprocess.CalledProcessError) as exc:
        print(f"Release validation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print(f"Release tag {sys.argv[2]} matches the clean checkout and watch version")
