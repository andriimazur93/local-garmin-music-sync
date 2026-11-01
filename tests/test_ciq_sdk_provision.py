import hashlib
import importlib.util
from pathlib import Path
import zipfile
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/provision-ciq-sdk.py'


def module():
    spec = importlib.util.spec_from_file_location('provision_ciq', SCRIPT)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def make_zip(path, name='bin/monkeyc'):
    with zipfile.ZipFile(path, 'w') as archive:
        info = zipfile.ZipInfo(name)
        info.external_attr = (0o100755 << 16)
        archive.writestr(info, '#!/bin/sh\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_installs_verified_archive_with_executable_compiler(tmp_path):
    archive = tmp_path / 'sdk.zip'
    digest = make_zip(archive)
    dest = tmp_path / 'sdk'
    module().install_archive(archive, dest, digest)
    assert (dest / 'bin/monkeyc').stat().st_mode & 0o111


def test_rejects_wrong_hash_without_installing(tmp_path):
    archive = tmp_path / 'sdk.zip'
    make_zip(archive)
    dest = tmp_path / 'sdk'
    with pytest.raises(ValueError):
        module().install_archive(archive, dest, '0' * 64)
    assert not dest.exists()


def test_rejects_path_escape_without_installing(tmp_path):
    archive = tmp_path / 'sdk.zip'
    digest = make_zip(archive, '../escape')
    dest = tmp_path / 'sdk'
    with pytest.raises(ValueError):
        module().install_archive(archive, dest, digest)
    assert not dest.exists() and not (tmp_path / 'escape').exists()


def test_rejects_symlink_and_existing_destination(tmp_path):
    archive = tmp_path / 'sdk.zip'
    with zipfile.ZipFile(archive, 'w') as zf:
        zf.writestr('bin/monkeyc', 'compiler')
        link = zipfile.ZipInfo('link')
        link.external_attr = 0o120777 << 16
        zf.writestr(link, '/etc/passwd')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    dest = tmp_path / 'sdk'
    with pytest.raises(ValueError):
        module().install_archive(archive, dest, digest)
    dest.mkdir()
    with pytest.raises(ValueError):
        module().install_archive(archive, dest, digest)
