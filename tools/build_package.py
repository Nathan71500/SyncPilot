"""Build an unbound source ZIP; never install or replace an existing archive."""
import importlib.util
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("package_check", ROOT / "tests/package_check.py")
checks = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checks)
inventory = checks.check()
target = ROOT / "dist" / ("syncpilot-" + inventory["version"] + "-source.zip")
target.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(target, "x", compression=zipfile.ZIP_DEFLATED) as archive:
    for record in inventory["files"]:
        archive.write(ROOT / "syncpilot" / record["path"], "syncpilot/" + record["path"])
    archive.write(ROOT / "LICENSE", "LICENSE")
print(str(target))
