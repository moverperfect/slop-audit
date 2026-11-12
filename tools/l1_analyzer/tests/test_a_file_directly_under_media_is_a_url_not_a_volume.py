"""`/media/img1.jpg` is a web path, and no machine has a file there.

`/media/` is on the machine-specific list because Linux mounts removable volumes beneath it,
`/media/<user>/<label>` or `/media/<label>`. It is also the most common URL prefix for uploaded
images on the web, and on an Astro site audited on 2026-11-12 the check's one finding was a
mock article's image, `url: '/media/img1.jpg'`.

The two can be told apart for one shape. The filesystem standard has `/media` hold a directory
per mounted volume, so a path that names a FILE directly under `/media` is inside no volume at
all: whatever it is, it is not one machine's mount. Any path with a directory between `/media`
and the file is still flagged, because `/media/usb/report.csv` and `/media/images/hero.jpg` look
the same and only one of them is a URL. `/mnt` gets no such allowance: it is itself a mount
point, so a file directly under it is a file on a mounted disk.
"""

from __future__ import annotations

import pathlib
import tempfile

from l1_analyzer import absolute_paths


def _findings(source: str) -> list[str]:
    with tempfile.TemporaryDirectory() as d:
        root = pathlib.Path(d)
        (root / "a.ts").write_text(source)
        return [f["path"] for f in absolute_paths.scan(root, "typescript")["findings"]]


def test_a_file_named_directly_under_media_is_not_a_machine_path():
    assert _findings("export const image = { url: '/media/img1.jpg' };\n") == []


def test_a_path_through_a_volume_under_media_is_still_flagged():
    assert _findings("const a = '/media/usb/report.csv';\nconst b = '/media/adam/Backup';\n") == [
        "/media/usb/report.csv", "/media/adam/Backup"]


def test_a_bare_volume_under_media_is_still_flagged():
    assert _findings("const mount = '/media/backup';\n") == ["/media/backup"]


def test_a_file_directly_under_mnt_is_still_flagged():
    assert _findings("const dump = '/mnt/backup.tar';\n") == ["/mnt/backup.tar"]
