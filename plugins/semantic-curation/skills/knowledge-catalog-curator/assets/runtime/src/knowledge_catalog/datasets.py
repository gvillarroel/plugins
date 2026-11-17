"""Bounded, provenance-preserving downloads from public Kaggle datasets.

Dataset descriptions and licenses are publisher assertions. They are evidence for
human review, never proof that synthetic records cannot contain sensitive data.
No third-party packages, credentials, arbitrary download URLs, or Kaggle login
are needed for the public demo datasets.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import tempfile
import time
import zipfile
from datetime import UTC, datetime
from http.client import IncompleteRead
from pathlib import Path, PurePosixPath
from urllib import error, parse, request

DEMO_DATASETS = (
    "noopurbhatt/retail-product-catalog-dataset",
    "kenzabz8/e-commerce-product-sales-dataset-1000-rows",
    "sayalikhot21/synthetic-dataset-for-e-commerce-return-analysis",
)
_HANDLE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}/[A-Za-z0-9][A-Za-z0-9_-]{0,199}\Z")
_LICENSES = {
    "Apache 2.0": "Apache-2.0",
    "MIT": "MIT",
    "CC0: Public Domain": "CC0-1.0",
    "Attribution 4.0 International (CC BY 4.0)": "CC-BY-4.0",
    "CC BY-SA 4.0": "CC-BY-SA-4.0",
}
_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
    *(f"{prefix}{digit}" for prefix in ("com", "lpt") for digit in "¹²³"),
}


class DatasetDownloadError(ValueError):
    """A dataset could not be downloaded or safely validated."""


def _metadata_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise DatasetDownloadError("Kaggle metadata contains duplicate JSON fields")
        result[key] = value
    return result


def _invalid_json_constant(_value):
    raise DatasetDownloadError("Kaggle metadata contains non-finite JSON numbers")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _allowed_url(url: str) -> bool:
    try:
        parsed = parse.urlsplit(url)
        port = parsed.port
    except ValueError:
        return False
    return (
        parsed.scheme == "https"
        and parsed.hostname in {"www.kaggle.com", "kaggle.com", "storage.googleapis.com"}
        and port in {None, 443}
        and not parsed.username
        and not parsed.password
    )


class _KaggleRedirects(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _allowed_url(newurl):
            raise DatasetDownloadError("Kaggle redirected to an unexpected host or protocol")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _fetch(url: str, *, limit: int, timeout: float) -> tuple[bytes, dict]:
    if not _allowed_url(url):
        raise DatasetDownloadError("Only the public Kaggle API and its storage host are allowed")
    started = time.monotonic()
    req = request.Request(
        url,
        headers={"User-Agent": "knowledge-catalog-claude/0.1", "Accept": "application/json, application/zip"},
    )
    opener = request.build_opener(_KaggleRedirects())
    try:
        with opener.open(req, timeout=min(timeout, 30)) as response:
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type:
                raise DatasetDownloadError("Kaggle returned an HTML login or error page")
            declared = response.headers.get("Content-Length")
            if declared is not None:
                if not re.fullmatch(r"[0-9]+", declared.strip()):
                    raise DatasetDownloadError("Kaggle response has an invalid Content-Length")
                declared = int(declared)
                if declared > limit:
                    raise DatasetDownloadError("Kaggle response exceeds the configured download limit")
            chunks = []
            size = 0
            while True:
                # read1 returns after one network read, so a trickling response
                # cannot bypass the overall deadline by filling a large chunk.
                read = getattr(response, "read1", response.read)
                block = read(min(65536, limit - size + 1))
                if time.monotonic() - started > timeout:
                    raise DatasetDownloadError("Kaggle response exceeded the download deadline")
                if not block:
                    break
                size += len(block)
                if size > limit:
                    raise DatasetDownloadError("Kaggle response exceeds the configured download limit")
                chunks.append(block)
            data = b"".join(chunks)
            if declared is not None and size != declared:
                raise DatasetDownloadError("Kaggle response body does not match its Content-Length")
            if data.lstrip()[:20].lower().startswith((b"<!doctype html", b"<html")):
                raise DatasetDownloadError("Kaggle returned an HTML login or error page")
            # Signed storage query parameters are deliberately never persisted.
            final_url = parse.urlsplit(response.geturl())
            return data, {"content_type": content_type, "bytes": size, "host": final_url.hostname}
    except error.HTTPError as exc:
        raise DatasetDownloadError(
            f"Kaggle API returned HTTP {exc.code}; use a public dataset with download access"
        ) from None
    except (error.URLError, TimeoutError, OSError, IncompleteRead) as exc:
        raise DatasetDownloadError(
            f"Kaggle request failed ({type(exc).__name__}); retry with network access"
        ) from None


def _safe_members(archive: zipfile.ZipFile, max_bytes: int, max_files: int) -> list[zipfile.ZipInfo]:
    members = archive.infolist()
    if len(members) > max_files:
        raise DatasetDownloadError("Archive contains too many files")
    total = 0
    seen: dict[str, bool] = {}
    for member in members:
        # ZipInfo normalizes backslashes on Windows and truncates NUL bytes.
        # Inspect the original archive name before that normalization.
        path = PurePosixPath(member.orig_filename)
        parts = member.orig_filename.rstrip("/").split("/")
        if not parts or path.is_absolute() or any(part in {"", ".", ".."} for part in parts):
            raise DatasetDownloadError("Archive contains an unsafe path")
        for part in parts:
            if (
                any(c in part for c in '\\:*?"<>|\x00')
                or any(ord(c) < 32 for c in part)
                or part.endswith((".", " "))
                or part.split(".")[0].rstrip(" ").lower() in _WINDOWS_RESERVED
            ):
                raise DatasetDownloadError("Archive contains a path unsafe on Windows")
        normalized = "/".join(parts).casefold()
        if normalized in seen:
            raise DatasetDownloadError("Archive contains duplicate paths")
        for prefix in PurePosixPath(normalized).parents:
            if str(prefix) in seen and not seen[str(prefix)]:
                raise DatasetDownloadError("Archive contains conflicting file and directory paths")
        if not member.is_dir() and any(name.startswith(normalized + "/") for name in seen):
            raise DatasetDownloadError("Archive contains conflicting file and directory paths")
        seen[normalized] = member.is_dir()
        mode = member.external_attr >> 16
        if stat.S_IFMT(mode) not in {0, stat.S_IFREG, stat.S_IFDIR}:
            raise DatasetDownloadError("Archive contains a symlink or special file")
        if member.flag_bits & 1:
            raise DatasetDownloadError("Encrypted archives are not supported")
        total += member.file_size
        if total > max_bytes:
            raise DatasetDownloadError("Archive exceeds the uncompressed size limit")
    return members


def _extract(archive_bytes: bytes, destination: Path, *, max_bytes: int, max_files: int) -> list[dict]:
    records = []
    try:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
            members = _safe_members(archive, max_bytes, max_files)
            for member in members:
                target = destination.joinpath(*PurePosixPath(member.filename).parts)
                if member.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                digest = hashlib.sha256()
                copied = 0
                with archive.open(member) as source, target.open("xb") as output:
                    while block := source.read(min(65536, member.file_size - copied + 1)):
                        copied += len(block)
                        if copied > member.file_size:
                            raise DatasetDownloadError("Archive member exceeds its declared size")
                        output.write(block)
                        digest.update(block)
                if copied != member.file_size:
                    raise DatasetDownloadError("Archive member has a truncated payload")
                records.append({"path": member.filename, "bytes": copied, "sha256": digest.hexdigest()})
    except (zipfile.BadZipFile, NotImplementedError, RuntimeError, OSError) as exc:
        raise DatasetDownloadError(
            f"Invalid or unsupported Kaggle ZIP archive ({type(exc).__name__})"
        ) from None
    if not records:
        raise DatasetDownloadError("Kaggle archive has no files")
    return records


def download_kaggle(
    handle: str,
    destination: str | Path,
    *,
    version: int | None = None,
    max_download_bytes: int = 25_000_000,
    max_uncompressed_bytes: int = 100_000_000,
    timeout: float = 30,
    max_files: int = 100,
) -> dict:
    """Download a public dataset with a version pin, hashes and review evidence.

    The destination is a local data root. Existing version directories are never
    overwritten. Unknown/unmapped licenses set ``publication_allowed`` to false;
    callers must enforce that gate before sending metadata to a cloud catalog.
    Known licenses still require following the publisher's license conditions.
    """
    if not isinstance(handle, str) or not _HANDLE.fullmatch(handle):
        raise DatasetDownloadError(
            "Dataset handle must be owner/dataset; URLs and path traversal are not accepted"
        )
    if any(
        type(value) is not int or value <= 0
        for value in (max_download_bytes, max_uncompressed_bytes, max_files)
    ):
        raise DatasetDownloadError("Download, extraction and file limits must be positive integers")
    if not isinstance(timeout, (int, float)) or not 0 < timeout <= 300:
        raise DatasetDownloadError("Timeout must be between 0 and 300 seconds")
    if version is not None and (type(version) is not int or version < 1):
        raise DatasetDownloadError("Version must be a positive integer")
    api_url = f"https://www.kaggle.com/api/v1/datasets/view/{handle}"
    raw, _ = _fetch(api_url, limit=2_000_000, timeout=timeout)
    try:
        metadata = json.loads(raw, object_pairs_hook=_metadata_object, parse_constant=_invalid_json_constant)
    except (ValueError, UnicodeDecodeError):
        raise DatasetDownloadError("Kaggle metadata response is not JSON") from None
    if not isinstance(metadata, dict) or metadata.get("ref", "").casefold() != handle.casefold():
        raise DatasetDownloadError("Kaggle metadata does not match the requested dataset")
    current = metadata.get("currentVersionNumber")
    if type(current) is not int or current < 1:
        raise DatasetDownloadError("Kaggle metadata does not identify a dataset version")
    if version is not None and version != current:
        raise DatasetDownloadError(
            "This helper requires the current version so metadata and downloaded content match"
        )
    version = current
    owner, slug = handle.split("/")
    root = Path(destination).expanduser().resolve()
    target = root / owner / slug / f"v{version}"
    if not target.resolve().is_relative_to(root):
        raise DatasetDownloadError("Dataset destination resolves outside the data root")
    if target.exists():
        raise DatasetDownloadError(
            "Dataset version already exists; use its saved provenance or choose a fresh destination"
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    archive_url = f"https://www.kaggle.com/api/v1/datasets/download/{handle}?datasetVersionNumber={version}"
    archive_bytes, response = _fetch(archive_url, limit=max_download_bytes, timeout=timeout)
    if not archive_bytes.startswith(b"PK"):
        raise DatasetDownloadError("Kaggle download is not a ZIP archive")
    description = metadata.get("description", "")
    if not isinstance(description, str):
        raise DatasetDownloadError("Kaggle description is not text")
    # A mixed or negated claim is not evidence that the dataset is synthetic.
    # Preserve the original description for the human to assess uncertainty.
    excluded_claim = re.compile(
        r"\b(?:not(?:\s+\w+){0,3}\s+synthetic|non[-\s]?synthetic|"
        r"(?:partly|partially|semi[-\s]?)\s*synthetic|"
        r"(?:real(?:[-\s]world)?|observed)\s+(?:and|or|&)\s+synthetic|"
        r"synthetic\s+(?:and|or|&)\s+(?:real|observed))\b",
        re.IGNORECASE,
    )
    claims = [
        line.strip()
        for line in description.splitlines()
        if re.search(r"\bsynthetic(?:ally)?\b", line, re.IGNORECASE) and not excluded_claim.search(line)
    ]
    license_name = metadata.get("licenseName") or "Unknown"
    if not isinstance(license_name, str):
        raise DatasetDownloadError("Kaggle licenseName must be text")
    spdx = _LICENSES.get(license_name)
    provenance = {
        "schema_version": 1,
        "source": "kaggle",
        "handle": handle,
        "source_url": f"https://www.kaggle.com/datasets/{handle}",
        "metadata_api_url": api_url,
        "download_api_url": archive_url,
        "title": metadata.get("title", slug),
        "publisher": metadata.get("ownerName") or owner,
        "dataset_version": version,
        "source_last_updated": metadata.get("lastUpdated"),
        "downloaded_at": datetime.now(UTC).isoformat(),
        "license": {
            "name": license_name,
            "spdx_id": spdx,
            "evidence": "Kaggle API licenseName",
            "review_status": "recognized" if spdx else "unknown",
        },
        "publication_allowed": spdx is not None,
        "synthetic": {
            "publisher_claim": bool(claims),
            "independently_verified": False,
            "evidence": claims,
            "evidence_source": "metadata.raw.json description",
        },
        "description": description,
        "metadata_sha256": _sha256(raw),
        "archive": {"bytes": len(archive_bytes), "sha256": _sha256(archive_bytes), "response": response},
        "local_directory": str(target),
    }
    staging = Path(tempfile.mkdtemp(prefix=".kaggle-", dir=target.parent))
    try:
        records = _extract(
            archive_bytes, staging / "files", max_bytes=max_uncompressed_bytes, max_files=max_files
        )
        for record in records:
            record.update(
                {
                    "license": license_name,
                    "license_spdx_id": spdx,
                    "synthetic_publisher_claim": bool(claims),
                    "synthetic_evidence": claims,
                }
            )
        provenance["files"] = records
        provenance["local_files"] = [str(target / "files" / r["path"]) for r in records]
        (staging / "metadata.raw.json").write_bytes(raw)
        (staging / "archive.zip").write_bytes(archive_bytes)
        (staging / "provenance.json").write_text(
            json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        os.replace(staging, target)
    except BaseException:
        shutil.rmtree(staging)
        raise
    return provenance


def main() -> None:
    """Standalone reproducible download command used by the demo."""
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("handle", choices=None, help="Public Kaggle owner/dataset")
    parser.add_argument("--destination", default="data/kaggle")
    parser.add_argument("--version", type=int)
    args = parser.parse_args()
    try:
        result = download_kaggle(args.handle, args.destination, version=args.version)
    except DatasetDownloadError as exc:
        parser.exit(1, f"Download failed: {exc}\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
