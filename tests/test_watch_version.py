from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]


def test_version_resource_is_generated_from_manifest(tmp_path):
    manifest = tmp_path / "manifest.xml"
    manifest.write_text('<manifest xmlns:iq="http://www.garmin.com/xml/connectiq"><iq:application version="12.34.5"/></manifest>')
    output = tmp_path / "version.xml"
    subprocess.run([sys.executable, str(ROOT / "scripts/generate-watch-version.py"), str(manifest), str(output)], check=True)
    element = ET.parse(output).getroot().find('string[@id="AppVersion"]')
    assert element is not None and element.text == "12.34.5"


def test_committed_version_resource_matches_manifest():
    manifest = ET.parse(ROOT / "watch/manifest.xml").getroot()
    expected = manifest.find('{http://www.garmin.com/xml/connectiq}application').attrib['version']
    actual = ET.parse(ROOT / "watch/resources/strings/version.xml").getroot().find('string[@id="AppVersion"]').text
    assert actual == expected


def test_generator_rejects_missing_manifest_version(tmp_path):
    manifest = tmp_path / "manifest.xml"
    manifest.write_text('<manifest xmlns:iq="http://www.garmin.com/xml/connectiq"><iq:application/></manifest>')
    output = tmp_path / "version.xml"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/generate-watch-version.py"), str(manifest), str(output)], capture_output=True)
    assert result.returncode != 0
    assert not output.exists()
