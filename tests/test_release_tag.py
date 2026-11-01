from pathlib import Path
import subprocess
import sys


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/verify-release-tag.py"


def git(repo, *args):
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def fixture_repo(tmp_path):
    git(tmp_path, "init", "-q")
    (tmp_path / "watch").mkdir()
    (tmp_path / "watch/manifest.xml").write_text('<manifest xmlns:iq="http://www.garmin.com/xml/connectiq"><iq:application version="0.1.2"/></manifest>')
    git(tmp_path, "add", "watch/manifest.xml")
    git(tmp_path, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "release")
    git(tmp_path, "update-ref", "refs/remotes/origin/main", "HEAD")
    return tmp_path


def verify(repo, tag):
    return subprocess.run([sys.executable, str(SCRIPT), str(repo), tag], capture_output=True, text=True)


def test_matching_tag_at_head_is_accepted(tmp_path):
    repo = fixture_repo(tmp_path)
    git(repo, "tag", "v0.1.2")
    assert verify(repo, "v0.1.2").returncode == 0


def test_missing_or_wrong_version_tag_is_rejected(tmp_path):
    repo = fixture_repo(tmp_path)
    git(repo, "tag", "v0.1.3")
    assert verify(repo, "v0.1.2").returncode != 0
    assert verify(repo, "v0.1.3").returncode != 0
    assert verify(repo, "--help").returncode != 0


def test_tag_must_point_at_head(tmp_path):
    repo = fixture_repo(tmp_path)
    git(repo, "tag", "v0.1.2")
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-qm", "later")
    assert verify(repo, "v0.1.2").returncode != 0


def test_dirty_source_is_rejected(tmp_path):
    repo = fixture_repo(tmp_path)
    git(repo, "tag", "v0.1.2")
    (repo / "watch/manifest.xml").write_text("modified")
    assert verify(repo, "v0.1.2").returncode != 0


def test_release_commit_must_be_reachable_from_origin_main(tmp_path):
    repo = fixture_repo(tmp_path)
    git(repo, "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "--allow-empty", "-qm", "unreviewed")
    git(repo, "tag", "v0.1.2")
    assert verify(repo, "v0.1.2").returncode != 0
