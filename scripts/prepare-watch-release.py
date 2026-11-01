"""Prepare a reviewed release branch without creating a tag or publishing."""

import importlib.util
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


VERSION = re.compile(r"(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)\.(?:0|[1-9][0-9]*)")
APP_TAG = re.compile(r'(<iq:application\b[^>]*?\bversion=")([^"]+)(")', re.DOTALL)


def replace_transactionally(repo: Path, changes: list[tuple[Path, bytes]]) -> None:
    staging = Path(tempfile.mkdtemp(prefix=".release-preparation-", dir=repo))
    replaced = []
    keep_backup = False
    try:
        for index, (target, contents) in enumerate(changes):
            staged = staging / f"{index}.new"
            backup = staging / f"{index}.original"
            shutil.copy2(target, backup)
            staged.write_bytes(contents)
            staged.chmod(target.stat().st_mode)
        try:
            for index, (target, _) in enumerate(changes):
                os.replace(staging / f"{index}.new", target)
                replaced.append((index, target))
        except OSError as failure:
            try:
                for index, target in reversed(replaced):
                    os.replace(staging / f"{index}.original", target)
            except OSError as rollback_failure:
                keep_backup = True
                raise OSError(f"Release preparation failed; backups retained at {staging}: {rollback_failure}") from failure
            raise
    finally:
        if not keep_backup:
            shutil.rmtree(staging)


def prepare(repo: Path, version: str) -> None:
    if not VERSION.fullmatch(version):
        raise ValueError("Version must use MAJOR.MINOR.PATCH")

    def git(*args: str) -> str:
        return subprocess.run(["git", "-C", str(repo), *args], check=True,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()

    if git("status", "--porcelain", "--untracked-files=normal"):
        raise ValueError("Release checkout must be clean")
    if git("branch", "--show-current") != f"release/{version}":
        raise ValueError("Use a release/VERSION branch")
    tag = subprocess.run(["git", "-C", str(repo), "show-ref", "--verify", "--quiet", f"refs/tags/v{version}"])
    if tag.returncode != 1:
        raise ValueError("Release tag already exists or could not be checked")

    manifest = repo / "watch/manifest.xml"
    resource = repo / "watch/resources/strings/version.xml"
    changelog = repo / "CHANGELOG.md"
    text = manifest.read_text(encoding="utf-8")
    matches = list(APP_TAG.finditer(text))
    if len(matches) != 1 or not VERSION.fullmatch(matches[0].group(2)):
        raise ValueError("Manifest must contain one valid application version")
    current = matches[0].group(2)
    if tuple(map(int, version.split("."))) <= tuple(map(int, current.split("."))):
        raise ValueError("New version must be greater than the manifest version")
    node = ET.parse(resource).getroot().find('string[@id="AppVersion"]')
    if node is None or node.text != current:
        raise ValueError("Existing generated resource must match the manifest")
    notes = changelog.read_text(encoding="utf-8")
    unreleased = notes.find("## [Unreleased]")
    changed = notes.find("### Changed\n", unreleased)
    next_section = notes.find("\n## [", unreleased + 1)
    if unreleased < 0 or changed < 0 or (next_section >= 0 and changed > next_section):
        raise ValueError("Changelog needs an Unreleased Changed section")
    insert = changed + len("### Changed\n")
    new_notes = notes[:insert] + f"\n- Prepare watch app version {version} for release.\n" + notes[insert:]
    new_manifest = APP_TAG.sub(lambda m: m.group(1) + version + m.group(3), text, count=1)
    ET.fromstring(new_manifest)

    spec = importlib.util.spec_from_file_location("watch_version", Path(__file__).with_name("generate-watch-version.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory() as tmp:
        temp_manifest = Path(tmp) / "manifest.xml"
        temp_resource = Path(tmp) / "version.xml"
        temp_manifest.write_text(new_manifest, encoding="utf-8")
        module.main(temp_manifest, temp_resource)
        new_resource = temp_resource.read_bytes()
    replace_transactionally(repo, [
        (manifest, new_manifest.encode("utf-8")),
        (resource, new_resource),
        (changelog, new_notes.encode("utf-8")),
    ])


if __name__ == "__main__":
    try:
        if len(sys.argv) != 3:
            raise ValueError("Usage: prepare-watch-release.py REPOSITORY VERSION")
        prepare(Path(sys.argv[1]), sys.argv[2])
    except (ValueError, OSError, ET.ParseError, subprocess.CalledProcessError) as exc:
        print(f"Release preparation failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
    print("Prepared an unreleased candidate; review the changes before committing")
