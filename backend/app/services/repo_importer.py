import os
import re
import zipfile
from pathlib import Path

import git

from app.config import settings

# Only accept plain https GitHub URLs. This blocks git's "ext::" / local
# "file://" / bare-path transports, which can otherwise be abused for
# command execution or reading arbitrary local files via a crafted "clone URL".
_GITHUB_URL_RE = re.compile(
    r"^https://(www\.)?github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(\.git)?/?$"
)

_MAX_ZIP_ENTRIES = 20_000
_MAX_ZIP_UNCOMPRESSED_MB = 1024


class ImportError_(Exception):
    """Raised for any user-facing repo import failure (bad url, bad zip, network, etc.)."""


def repo_name_from_github_url(url: str) -> str:
    match = _GITHUB_URL_RE.match(url.strip())
    if not match:
        raise ImportError_(
            "Only https://github.com/<owner>/<repo> URLs are supported in this build."
        )
    return match.group("repo")


def clone_github_repo(url: str, dest_dir: Path) -> None:
    if not _GITHUB_URL_RE.match(url.strip()):
        raise ImportError_(
            "Only https://github.com/<owner>/<repo> URLs are supported in this build."
        )

    dest_dir.mkdir(parents=True, exist_ok=True)
    if any(dest_dir.iterdir()):
        raise ImportError_(f"Destination directory is not empty: {dest_dir}")

    env = dict(os.environ)
    env["GIT_TERMINAL_PROMPT"] = "0"  # never hang prompting for credentials on a private repo

    try:
        git.Repo.clone_from(
            url.strip(),
            dest_dir,
            depth=1,
            single_branch=True,
            env=env,
        )
    except git.GitError as exc:
        raise ImportError_(
            f"Could not clone repository (private, missing, or unreachable): {exc}"
        ) from exc


def extract_zip(zip_bytes: bytes, dest_dir: Path) -> None:
    dest_dir.mkdir(parents=True, exist_ok=True)
    if any(dest_dir.iterdir()):
        raise ImportError_(f"Destination directory is not empty: {dest_dir}")

    import io

    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile as exc:
        raise ImportError_("Uploaded file is not a valid ZIP archive.") from exc

    infos = zf.infolist()
    if len(infos) > _MAX_ZIP_ENTRIES:
        raise ImportError_(f"ZIP has too many entries (> {_MAX_ZIP_ENTRIES}).")

    total_uncompressed = sum(i.file_size for i in infos)
    if total_uncompressed > _MAX_ZIP_UNCOMPRESSED_MB * 1024 * 1024:
        raise ImportError_(
            f"ZIP uncompressed size exceeds {_MAX_ZIP_UNCOMPRESSED_MB}MB limit (possible zip bomb)."
        )

    dest_resolved = dest_dir.resolve()
    for info in infos:
        # Zip-slip protection: reject any entry that would extract outside dest_dir.
        target = (dest_dir / info.filename).resolve()
        if not str(target).startswith(str(dest_resolved) + os.sep) and target != dest_resolved:
            raise ImportError_(f"Unsafe path in ZIP entry: {info.filename}")

    zf.extractall(dest_dir)

    # If the zip has a single top-level folder (typical GitHub "download zip"
    # layout), flatten it so source_dir directly contains the repo contents.
    entries = list(dest_dir.iterdir())
    if len(entries) == 1 and entries[0].is_dir():
        inner = entries[0]
        for child in inner.iterdir():
            child.rename(dest_dir / child.name)
        inner.rmdir()
