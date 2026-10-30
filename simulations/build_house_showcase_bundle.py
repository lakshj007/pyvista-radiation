"""Bundle the standalone example and native assets for offline review."""

from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "examples/house_showcase"
OUTPUT = ROOT / "preview/house_showcase.zip"


def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for path in sorted(SOURCE.rglob("*")):
            if path.is_file() and (path.suffix in (".py", ".rst", ".vtm", ".vts", ".vtu", ".vtp", ".json") or path.name == "LICENSE"):
                entry = ZipInfo("house_showcase/" + path.relative_to(SOURCE).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
                entry.compress_type = ZIP_DEFLATED
                entry.external_attr = 0o100644 << 16
                archive.writestr(entry, path.read_bytes())
    print(f"{OUTPUT}: {OUTPUT.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
