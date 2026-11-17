"""Downloader contracts are tested offline; no Kaggle credentials or traffic."""

import io
import json
import stat
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from knowledge_catalog import datasets


def archive_bytes(entries):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, value in entries:
            archive.writestr(name, value)
    return output.getvalue()


def metadata(**updates):
    result = {
        "ref": "publisher/synthetic-retail",
        "title": "Synthetic retail",
        "description": "These records are synthetically generated for testing.",
        "currentVersionNumber": 1,
        "licenseName": "Apache 2.0",
    }
    result.update(updates)
    return json.dumps(result).encode()


def responses(raw=None, payload=None):
    return [
        (raw if raw is not None else metadata(), {}),
        (
            payload if payload is not None else archive_bytes([("retail.csv", "id,price\n1,2.5\n")]),
            {"host": "storage.googleapis.com"},
        ),
    ]


def test_download_preserves_raw_metadata_and_file_provenance(tmp_path):
    raw = metadata()
    with patch.object(datasets, "_fetch", side_effect=responses(raw)) as fetch:
        result = datasets.download_kaggle("publisher/synthetic-retail", tmp_path)
    assert "datasetVersionNumber=1" in fetch.call_args_list[1].args[0]
    root = Path(result["local_directory"])
    assert (root / "metadata.raw.json").read_bytes() == raw
    assert result["metadata_sha256"] == datasets._sha256(raw)
    assert (root / "archive.zip").exists()
    assert result["synthetic"]["publisher_claim"] is True
    assert result["synthetic"]["independently_verified"] is False
    assert result["license"]["spdx_id"] == "Apache-2.0"
    assert result["files"][0]["license_spdx_id"] == "Apache-2.0"
    assert result["files"][0]["sha256"] == datasets._sha256(Path(result["local_files"][0]).read_bytes())
    assert json.loads((root / "provenance.json").read_text(encoding="utf-8")) == result


@pytest.mark.parametrize(
    "handle", ["https://evil.test/data.zip", "../data", "a/b/../c", "a/b?x=1", "a/b%2f..", "C:/file", "a/."]
)
def test_rejects_urls_and_invalid_handles_before_network(handle, tmp_path):
    with patch.object(datasets, "_fetch") as fetch, pytest.raises(datasets.DatasetDownloadError):
        datasets.download_kaggle(handle, tmp_path)
    fetch.assert_not_called()


@pytest.mark.parametrize(
    "name",
    [
        "../escape.csv",
        "/absolute.csv",
        "a/../escape.csv",
        "a\\escape.csv",
        "C:escape.csv",
        "a/./b.csv",
        "a//b.csv",
        "CON.csv",
        "a/file. ",
    ],
)
def test_rejects_archive_paths_unsafe_on_windows(name, tmp_path):
    payload = archive_bytes([(name, "x")])
    if "\\" in name:
        # ZipInfo writing normalizes native separators on Windows. Simulate a
        # hostile ZIP created on another platform by modifying both name fields.
        payload = payload.replace(name.replace("\\", "/").encode(), name.encode())
    with (
        patch.object(datasets, "_fetch", side_effect=responses(payload=payload)),
        pytest.raises(datasets.DatasetDownloadError, match="path"),
    ):
        datasets.download_kaggle("publisher/synthetic-retail", tmp_path)
    assert not list(tmp_path.rglob("*.csv"))


def test_rejects_archive_symlinks(tmp_path):
    link = zipfile.ZipInfo("link.csv")
    link.create_system = 3
    link.external_attr = (stat.S_IFLNK | 0o777) << 16
    with (
        patch.object(
            datasets, "_fetch", side_effect=responses(payload=archive_bytes([(link, "../../target")]))
        ),
        pytest.raises(datasets.DatasetDownloadError, match="symlink"),
    ):
        datasets.download_kaggle("publisher/synthetic-retail", tmp_path)


@pytest.mark.parametrize(
    "kwargs,entries,message",
    [
        ({"max_uncompressed_bytes": 2}, [("data.csv", "too large")], "uncompressed"),
        ({"max_files": 1}, [("a.csv", "a"), ("b.csv", "b")], "too many"),
        ({}, [("a.csv", "a"), ("A.csv", "b")], "duplicate"),
    ],
)
def test_rejects_zip_bombs_excess_files_and_case_collisions(tmp_path, kwargs, entries, message):
    with (
        patch.object(datasets, "_fetch", side_effect=responses(payload=archive_bytes(entries))),
        pytest.raises(datasets.DatasetDownloadError, match=message),
    ):
        datasets.download_kaggle("publisher/synthetic-retail", tmp_path, **kwargs)


def test_unknown_license_cannot_authorize_publication(tmp_path):
    with patch.object(datasets, "_fetch", side_effect=responses(metadata(licenseName="Unknown"))):
        result = datasets.download_kaggle("publisher/synthetic-retail", tmp_path)
    assert result["publication_allowed"] is False
    assert result["license"]["review_status"] == "unknown"
    assert result["files"][0]["license_spdx_id"] is None


def test_absent_synthetic_evidence_is_not_invented(tmp_path):
    with patch.object(datasets, "_fetch", side_effect=responses(metadata(description="Retail data"))):
        result = datasets.download_kaggle("publisher/synthetic-retail", tmp_path)
    assert result["synthetic"]["publisher_claim"] is False
    assert result["synthetic"]["evidence"] == []


@pytest.mark.parametrize("description", ["This dataset is not synthetic.", "Non-synthetic retail records."])
def test_negated_synthetic_description_does_not_claim_synthetic_data(tmp_path, description):
    with patch.object(datasets, "_fetch", side_effect=responses(metadata(description=description))):
        result = datasets.download_kaggle("publisher/synthetic-retail", tmp_path)
    assert result["synthetic"]["publisher_claim"] is False
    assert result["synthetic"]["evidence"] == []


@pytest.mark.parametrize(
    "raw,version,message",
    [
        (metadata(ref="different/dataset"), None, "does not match"),
        (metadata(currentVersionNumber=None), None, "version"),
        (metadata(), 2, "current version"),
        (b"<html>Login</html>", None, "not JSON"),
    ],
)
def test_metadata_identity_and_version_must_match_archive(tmp_path, raw, version, message):
    with (
        patch.object(datasets, "_fetch", return_value=(raw, {})) as fetch,
        pytest.raises(datasets.DatasetDownloadError, match=message),
    ):
        datasets.download_kaggle("publisher/synthetic-retail", tmp_path, version=version)
    assert fetch.call_count == 1


def test_existing_version_is_never_overwritten(tmp_path):
    with patch.object(datasets, "_fetch", side_effect=responses()):
        result = datasets.download_kaggle("publisher/synthetic-retail", tmp_path)
    original = Path(result["local_files"][0]).read_bytes()
    with (
        patch.object(datasets, "_fetch", return_value=(metadata(), {})),
        pytest.raises(datasets.DatasetDownloadError, match="already exists"),
    ):
        datasets.download_kaggle("publisher/synthetic-retail", tmp_path)
    assert Path(result["local_files"][0]).read_bytes() == original


def test_redirect_hosts_are_allowlisted():
    assert datasets._allowed_url("https://storage.googleapis.com:443/kaggle/archive.zip?signature=secret")
    assert not datasets._allowed_url("https://storage.googleapis.com.evil.test/a")
    assert not datasets._allowed_url("http://www.kaggle.com/a")
    assert not datasets._allowed_url("https://user:password@www.kaggle.com/a")


class Response:
    def __init__(self, payload, headers=None):
        self.payload = io.BytesIO(payload)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, count):
        return self.payload.read(count)

    def geturl(self):
        return "https://storage.googleapis.com/archive.zip?signature=must-not-persist"


@pytest.mark.parametrize(
    "payload,headers,limit,message",
    [
        (b"<html>Login", {"Content-Type": "text/html"}, 100, "HTML"),
        (b" <!DOCTYPE html>", {}, 100, "HTML"),
        (b"12345", {"Content-Length": "5"}, 4, "limit"),
        (b"12345", {}, 4, "limit"),
    ],
)
def test_stream_limits_and_html_error_detection(payload, headers, limit, message):
    with (
        patch.object(datasets.request.OpenerDirector, "open", return_value=Response(payload, headers)),
        pytest.raises(datasets.DatasetDownloadError, match=message),
    ):
        datasets._fetch("https://www.kaggle.com/a", limit=limit, timeout=10)


def test_signed_redirect_query_is_not_saved():
    with patch.object(datasets.request.OpenerDirector, "open", return_value=Response(b"PK123")):
        _, response = datasets._fetch("https://www.kaggle.com/a", limit=20, timeout=10)
    assert "must-not-persist" not in json.dumps(response)


def test_deadline_prevents_slow_streams():
    with (
        patch.object(datasets.request.OpenerDirector, "open", return_value=Response(b"PK123")),
        patch.object(datasets.time, "monotonic", side_effect=[0, 11]),
        pytest.raises(datasets.DatasetDownloadError, match="deadline"),
    ):
        datasets._fetch("https://www.kaggle.com/a", limit=20, timeout=10)
