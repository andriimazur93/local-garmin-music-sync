import os
from pathlib import Path
import shutil
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def repository(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    for name in ("scripts", "watch"):
        shutil.copytree(ROOT / name, repo / name)
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "add", "scripts", "watch"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-qm", "fixture"], check=True)
    sdk = tmp_path / "sdk" / "bin"
    sdk.mkdir(parents=True)
    compiler = sdk / "monkeyc"
    compiler.write_text('#!/bin/bash\nwhile [[ $# -gt 0 ]]; do if [[ "$1" == "-o" ]]; then printf package > "$2"; exit 0; fi; shift; done\nexit 1\n')
    compiler.chmod(0o755)
    key = tmp_path / "key.der"
    key.write_bytes(b"test key")
    env = os.environ | {"CIQ_SDK_HOME": str(sdk.parent), "GARMIN_SIGNING_KEY": str(key)}
    return repo, env


def test_release_build_produces_both_packages_and_checksums(tmp_path):
    repo, env = repository(tmp_path)
    result = subprocess.run(["bash", "scripts/build-release.sh"], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    output = repo / "dist" / "watch-release"
    assert {p.name for p in output.iterdir()} == {"garmin-sync-fr955.prg", "garmin-sync-fr955.iq", "garmin-sync-fr955.prg.sha256", "garmin-sync-fr955.iq.sha256", "build-info.txt"}
    assert subprocess.run(["sha256sum", "--check", "garmin-sync-fr955.prg.sha256", "garmin-sync-fr955.iq.sha256"], cwd=output).returncode == 0
    assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip() in (output / "build-info.txt").read_text()


def test_release_rejects_modified_source(tmp_path):
    repo, env = repository(tmp_path)
    (repo / "watch" / "manifest.xml").write_text("modified")
    result = subprocess.run(["bash", "scripts/build-release.sh"], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not (repo / "dist" / "watch-release").exists()


def test_compiler_failure_does_not_publish_partial_release(tmp_path):
    repo, env = repository(tmp_path)
    compiler = Path(env["CIQ_SDK_HOME"]) / "bin" / "monkeyc"
    compiler.write_text('#!/bin/bash\n[[ "$1" == "-e" ]] && exit 1\nwhile [[ $# -gt 0 ]]; do if [[ "$1" == "-o" ]]; then printf package > "$2"; exit 0; fi; shift; done\nexit 1\n')
    result = subprocess.run(["bash", "scripts/build-release.sh"], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert not (repo / "dist" / "watch-release").exists()


def test_runner_keeps_registration_when_github_cannot_be_reached(tmp_path):
    repo, env = repository(tmp_path)
    runner = repo / ".local" / "actions-runner"
    runner.mkdir(parents=True)
    (runner / "release.env").write_text("")
    (runner / ".runner").write_text('{"agentId": 42}', encoding="utf-8-sig")
    config = runner / "config.sh"
    config.write_text("#!/bin/sh\nexit 0\n")
    config.chmod(0o755)
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    gh = bin_dir / "gh"
    gh.write_text('#!/bin/sh\nif [ "$1" = repo ]; then echo owner/repo; exit 0; fi\necho network-failure >&2\nexit 1\n')
    gh.chmod(0o755)
    env["PATH"] = str(bin_dir) + os.pathsep + env["PATH"]
    result = subprocess.run(["bash", "scripts/start-release-runner.sh"], cwd=repo, env=env, capture_output=True, text=True)
    assert result.returncode != 0
    assert "Could not check runner registration" in result.stderr
    assert (runner / ".runner").exists()
