import gzip
import hashlib
import json
import os
import shutil
import tempfile
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

STORAGE_ROOT = Path(os.getenv("ASSET_STORAGE_PATH", "/var/lib/asset-depot"))
STORAGE_ROOT.mkdir(parents=True, exist_ok=True)

OBJECTS_DIR = STORAGE_ROOT / "objects"
REFS_DIR = STORAGE_ROOT / "refs"
OBJECTS_DIR.mkdir(parents=True, exist_ok=True)
REFS_DIR.mkdir(parents=True, exist_ok=True)

REPLICA_ROOT_VALUE = os.getenv("ASSET_STORAGE_REPLICA_PATH")
REPLICA_ROOT = Path(REPLICA_ROOT_VALUE) if REPLICA_ROOT_VALUE else None
if REPLICA_ROOT:
    REPLICA_ROOT.mkdir(parents=True, exist_ok=True)


def _timestamp_prefix() -> str:
    return datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")


def _replicate_object(relative_path: Path, source_path: Path) -> None:
    if not REPLICA_ROOT:
        return
    replica_path = REPLICA_ROOT / relative_path
    replica_path.parent.mkdir(parents=True, exist_ok=True)
    if replica_path.exists():
        return
    shutil.copy2(source_path, replica_path)


def save_asset_file(project_id: str, asset_id: str, filename: str, file_obj: BinaryIO) -> str:
    hasher = hashlib.sha256()
    total_bytes = 0

    with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
        temp_path = Path(tmp_file.name)
        with gzip.GzipFile(fileobj=tmp_file, mode="wb") as gzip_buffer:
            while True:
                chunk = file_obj.read(1024 * 1024)
                if not chunk:
                    break
                hasher.update(chunk)
                gzip_buffer.write(chunk)
                total_bytes += len(chunk)

    digest = hasher.hexdigest()
    object_dir = OBJECTS_DIR / digest[:2] / digest[2:4]
    object_dir.mkdir(parents=True, exist_ok=True)
    object_filename = f"{digest}.bin.gz"
    object_path = object_dir / object_filename

    if object_path.exists():
        temp_path.unlink(missing_ok=True)
    else:
        shutil.move(str(temp_path), str(object_path))

    relative_object = object_path.relative_to(STORAGE_ROOT)
    _replicate_object(relative_object, object_path)

    reference_dir = REFS_DIR / project_id
    reference_dir.mkdir(parents=True, exist_ok=True)
    pointer_name = f"{_timestamp_prefix()}_{asset_id}.json"
    pointer_path = reference_dir / pointer_name

    pointer_payload = {
        "asset_id": asset_id,
        "filename": filename,
        "object_path": str(relative_object),
        "checksum": digest,
        "bytes": total_bytes,
        "compressed_bytes": object_path.stat().st_size,
        "created_at": datetime.utcnow().isoformat() + "Z",
    }
    pointer_path.write_text(json.dumps(pointer_payload, indent=2))

    return f"depot://{pointer_path.relative_to(STORAGE_ROOT)}"
