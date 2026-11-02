"""Streaming, verified-content ZIP snapshots; no automatic restoration."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import BinaryIO
import uuid
import zipfile

from .repository import Repository


def create_backup(repository: Repository, out_dir: str | Path | None = None) -> Path:
    """Archive original bytes while the caller holds the validated data session."""
    directory = Path(out_dir) if out_dir is not None else repository.directory / 'backups'
    directory.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    name = f"backup-{now.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid.uuid4().hex}.zip"
    destination = directory / name

    def write(handle: BinaryIO) -> None:
        files: dict[str, dict[str, int | str]] = {}
        with zipfile.ZipFile(handle, 'w', compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
            for filename in repository.storage_filenames():
                digest = hashlib.sha256()
                size = 0
                with repository.path(filename).open('rb') as source, archive.open(filename, 'w', force_zip64=True) as output:
                    while True:
                        block = source.read(64 * 1024)
                        if not block:
                            break
                        output.write(block)
                        digest.update(block)
                        size += len(block)
                files[filename] = {'size': size, 'sha256': digest.hexdigest()}
            manifest = {'format': 'budget_app_backup', 'version': 1,
                        'created_at': now.isoformat().replace('+00:00', 'Z'), 'files': files}
            archive.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')

    repository.atomic_binary_write(destination, write, overwrite=False)
    return destination
