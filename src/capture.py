"""Opt-in, bounded local diagnostic capture. No upload or background work."""

from datetime import datetime, timezone
from pathlib import Path
import struct
import uuid


class PacketCapture:
    def __init__(self, limit: int, directory: Path = Path('logs')) -> None:
        if not 1 <= limit <= 2000:
            raise ValueError('Capture limit must be 1..2000')
        self.limit = limit
        self.count = 0
        self.directory = directory
        self.path: Path | None = None
        self._file = None

    def record(self, data: bytes) -> None:
        if self.count >= self.limit:
            return
        if self._file is None:
            self.directory.mkdir(parents=True, exist_ok=True)
            name = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            self.path = self.directory / f'capture-{name}-{uuid.uuid4().hex[:8]}.bin'
            self._file = self.path.open('xb')
            self._file.write(b'ARECAP01')
        self._file.write(struct.pack('<I', len(data)))
        self._file.write(data)
        self.count += 1
        if self.count == self.limit:
            self.close()

    def close(self) -> None:
        if self._file is not None:
            stream = self._file
            self._file = None
            stream.close()
