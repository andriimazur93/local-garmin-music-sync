"""Generate the watch's read-only version resource from its manifest."""

from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def main(manifest: Path, output: Path) -> None:
    application = ET.parse(manifest).getroot().find(
        "{http://www.garmin.com/xml/connectiq}application"
    )
    if application is None or not application.get("version"):
        raise ValueError("Watch manifest has no application version")
    root = ET.Element("strings")
    ET.SubElement(root, "string", id="AppVersion").text = application.attrib["version"]
    ET.indent(root, space="    ")
    output.write_bytes(ET.tostring(root, encoding="utf-8") + b"\n")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
