from pathlib import Path
import importlib.util
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/prepare-watch-release.py"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def make_repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "watch/resources/strings").mkdir(parents=True)
    (tmp_path / "watch/manifest.xml").write_text('<manifest xmlns:iq="http://www.garmin.com/xml/connectiq"><iq:application version="0.1.1"/></manifest>\n')
    (tmp_path / "watch/resources/strings/version.xml").write_text('<strings><string id="AppVersion">0.1.1</string></strings>\n')
    (tmp_path / "CHANGELOG.md").write_text('# Changelog\n\n## [Unreleased]\n\n### Changed\n\n- Existing change.\n')
    git(tmp_path, "add", ".")
    git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture")
    git(tmp_path, "switch", "-qc", "release/0.1.2")
    return tmp_path


def run(repo, version):
    return subprocess.run([sys.executable, str(SCRIPT), str(repo), version], capture_output=True, text=True)


def test_prepares_version_resource_and_unreleased_changelog(tmp_path):
    repo = make_repo(tmp_path)
    result = run(repo, "0.1.2")
    assert result.returncode == 0, result.stderr
    app = ET.parse(repo / "watch/manifest.xml").getroot().find('{http://www.garmin.com/xml/connectiq}application')
    assert app.attrib['version'] == '0.1.2'
    assert ET.parse(repo / "watch/resources/strings/version.xml").getroot().find('string').text == '0.1.2'
    changelog = (repo / 'CHANGELOG.md').read_text()
    assert '## [Unreleased]' in changelog and '0.1.2' in changelog and 'Existing change.' in changelog
    assert '## [0.1.2]' not in changelog


def test_refuses_dirty_tree_wrong_branch_and_nonincreasing_version(tmp_path):
    repo = make_repo(tmp_path)
    assert run(repo, "0.1.1").returncode != 0
    assert run(repo, "0.1.3").returncode != 0
    assert run(repo, "0.1.2-rc1").returncode != 0
    (repo / 'CHANGELOG.md').write_text('unsaved work')
    assert run(repo, "0.1.2").returncode != 0
    assert (repo / 'CHANGELOG.md').read_text() == 'unsaved work'


def test_refuses_existing_version_tag(tmp_path):
    repo = make_repo(tmp_path)
    git(repo, 'tag', 'v0.1.2')
    assert run(repo, '0.1.2').returncode != 0


def test_write_failure_restores_previously_replaced_files(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    original_manifest = (repo / 'watch/manifest.xml').read_bytes()
    original_resource = (repo / 'watch/resources/strings/version.xml').read_bytes()
    original_changelog = (repo / 'CHANGELOG.md').read_bytes()
    spec = importlib.util.spec_from_file_location('prepare_release', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    actual_replace = os.replace
    calls = 0

    def fail_second_replace(src, dst):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError('simulated write failure')
        return actual_replace(src, dst)

    monkeypatch.setattr(module.os, 'replace', fail_second_replace)
    with pytest.raises(OSError):
        module.prepare(repo, '0.1.2')
    assert (repo / 'watch/manifest.xml').read_bytes() == original_manifest
    assert (repo / 'watch/resources/strings/version.xml').read_bytes() == original_resource
    assert (repo / 'CHANGELOG.md').read_bytes() == original_changelog
