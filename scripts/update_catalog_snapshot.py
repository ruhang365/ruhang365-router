#!/usr/bin/env python3
"""Replace the bundled snapshot with a validated RHZL public Catalog."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import errno
import gzip
import json
import hashlib
import os
from pathlib import Path
import re
import stat
import sys
import tempfile
import time
import urllib.error
import urllib.request


REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_SCRIPTS = REPO_ROOT / "skills" / "ruhang365-router" / "scripts"
if str(SKILL_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SKILL_SCRIPTS))

from community_catalog import DEFAULT_CATALOG_PATH, FULL_CATALOG_PATH, load_catalog, fetch_catalog  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default="https://rhzl.ruhang365.cn/api/community/catalog",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check", action="store_true", help="Validate the public catalog without writing any files")
    return parser.parse_args()


def file_state(path: Path):
    """Fingerprint content and identity; do not follow output symlinks."""
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise ValueError("output is not a regular file")
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        if (opened.st_dev, opened.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError("output changed while reading")
        digest = hashlib.sha256(stream.read()).digest()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns, digest


def error_category(error: Exception) -> str:
    if isinstance(error, ValueError) and str(error) in {
        'another snapshot updater is writing this output', 'output changed during download',
    }:
        return 'concurrent_update'
    if isinstance(error, urllib.error.HTTPError):
        return f"http_status={error.code}"
    if isinstance(error, TimeoutError) or (isinstance(error, urllib.error.URLError) and isinstance(error.reason, TimeoutError)):
        return "network_timeout"
    if isinstance(error, (urllib.error.URLError, ConnectionError)):
        return "network_error"
    if isinstance(error, ValueError) and str(error) == "Community catalog contentDigest mismatch":
        return "digest_error"
    if isinstance(error, (gzip.BadGzipFile, EOFError)):
        return "protocol_error"
    if isinstance(error, OSError):
        return "filesystem_error"
    return "protocol_error"


@contextmanager
def snapshot_write_lock(output: Path):
    """Stable lock inode shared by cooperating updaters; never unlink it.

    A busy writer fails closed. This is not atomic CAS against arbitrary editors.
    --check and unchanged reads never enter this path or create a lock file.
    """
    lock_path = output.parent / f'.{output.name}.snapshot.lock'
    flags = os.O_RDWR | os.O_CREAT | getattr(os, 'O_NOFOLLOW', 0)
    fd = os.open(lock_path, flags, 0o600)
    locked = False
    try:
        opened, named = os.fstat(fd), lock_path.lstat()
        if not stat.S_ISREG(named.st_mode) or (opened.st_dev, opened.st_ino) != (named.st_dev, named.st_ino):
            raise ValueError('snapshot lock is not a stable regular file')
        try:
            if os.name == 'nt':
                import msvcrt
                if opened.st_size == 0:
                    os.write(fd, b'\0')
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as error:
            if error.errno in (errno.EACCES, errno.EAGAIN):
                raise ValueError('another snapshot updater is writing this output') from error
            raise
        yield
    finally:
        if locked:
            if os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def replace_snapshot(output: Path, catalog: dict, initial_state):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                         prefix=f'.{output.name}.', suffix='.tmp', delete=False) as stream:
            temporary = Path(stream.name)
            json.dump(catalog, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        with snapshot_write_lock(output):
            if file_state(output) != initial_state:
                raise ValueError("output changed during download")
            if initial_state is not None:
                os.chmod(temporary, stat.S_IMODE(output.stat().st_mode))
            os.replace(temporary, output)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    attempts = 0
    try:
        targets = [args.output] if args.output else [FULL_CATALOG_PATH, DEFAULT_CATALOG_PATH]
        states = {path: file_state(path) for path in targets}
        snapshots = {}
        for path in targets:
            if states[path] is not None:
                try:
                    snapshots[path] = load_catalog(path)
                except ValueError:
                    pass  # Invalid local data never supplies an ETag.
        snapshot_path = next(iter(snapshots), None)
        snapshot = snapshots.get(snapshot_path)
        for attempts in range(1, 4):
            try:
                catalog, not_modified = fetch_catalog(args.url, snapshot=snapshot, timeout=20,
                                                   opener=urllib.request.urlopen,
                                                   user_agent="ruhang365-snapshot-bot/0.5")
                break
            except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
                transient = not isinstance(error, urllib.error.HTTPError) or error.code in {502, 503, 504}
                if not transient or attempts == 3:
                    raise
                print(f"snapshot retry: {error_category(error)} attempts={attempts}", file=sys.stderr)
                time.sleep(attempts)
        output = args.output or (FULL_CATALOG_PATH if catalog['schemaVersion'] == '1.1.0' else DEFAULT_CATALOG_PATH)
        unchanged = not_modified or snapshots.get(output) == catalog
        if not args.check and not unchanged:
            replace_snapshot(output, catalog, states[output])
    except Exception as error:
        print(f"snapshot update failed: {error_category(error)} elapsed={time.monotonic() - started:.3f}s attempts={attempts}", file=sys.stderr)
        return 1
    # Do not echo arbitrary remote strings, URL queries, or exception bodies.
    version = catalog['catalogVersion'] if re.fullmatch(r'[A-Za-z0-9_.:+-]{1,128}', catalog['catalogVersion']) else '[redacted]'
    result = 'checked' if args.check else ('unchanged' if unchanged else 'updated')
    print(
        f"snapshot {result}: version={version} digest={catalog['contentDigest']} "
        f"items={len(catalog['items'])} http_status={304 if not_modified else 200} "
        f"elapsed={time.monotonic() - started:.3f}s attempts={attempts}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
