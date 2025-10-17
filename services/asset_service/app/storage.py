import os
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

STORAGE_ROOT = Path(os.getenv("ASSET_STORAGE_PATH", "/var/lib/asset-depot"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def _timestamp_prefix() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")


def save_asset_file(project_id: str, asset_id: str, filename: str, file_obj: BinaryIO) -> str:
    project_dir = STORAGE_ROOT / project_id
    project_dir.mkdir(parents=True, exist_ok=True)

    safe_name = f"{_timestamp_prefix()}_{filename}"
    file_path = project_dir / safe_name

    with open(file_path, "wb") as buffer:
        while True:
            chunk = file_obj.read(1024 * 1024)
            if not chunk:
                break
            buffer.write(chunk)

    relative = str(file_path.relative_to(STORAGE_ROOT))
    return f"depot://{relative}"
