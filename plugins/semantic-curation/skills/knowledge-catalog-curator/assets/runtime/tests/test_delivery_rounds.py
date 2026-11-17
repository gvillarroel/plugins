"""Focused regressions from additional reviewer rounds R34–R43."""

import io
import json
import zipfile
from unittest.mock import patch

import pytest

from knowledge_catalog import datasets


def kaggle_metadata(**updates):
    value = {
        "ref": "publisher/synthetic-retail",
        "title": "Retail",
        "description": "Fully synthetic retail data.",
        "currentVersionNumber": 1,
        "licenseName": "MIT",
    }
    value.update(updates)
    return json.dumps(value).encode()


def zip_payload(entries=None):
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        for name, body in entries or [("orders.csv", "quantity,price\n1,2\n")]:
            archive.writestr(name, body)
    return payload.getvalue()


@pytest.mark.parametrize(
    "description",
    [
        "These records are not entirely synthetic.",
        "Partially synthetic records from a live business.",
        "A mixture of real and synthetic data.",
        "Synthetic and observed retail records.",
    ],
)
def test_r34_uncertain_synthetic_scope_is_not_affirmed(tmp_path, description):
    responses = [(kaggle_metadata(description=description), {}), (zip_payload(), {})]
    with patch.object(datasets, "_fetch", side_effect=responses):
        provenance = datasets.download_kaggle("publisher/synthetic-retail", tmp_path)
    assert provenance["synthetic"]["publisher_claim"] is False
    assert provenance["synthetic"]["evidence"] == []
    assert provenance["description"] == description


@pytest.mark.parametrize("license_name", [{"name": "MIT"}, ["MIT"]])
def test_r34_malformed_license_is_a_readable_error(tmp_path, license_name):
    with patch.object(
        datasets, "_fetch", side_effect=[(kaggle_metadata(licenseName=license_name), {}), (zip_payload(), {})]
    ):
        with pytest.raises(datasets.DatasetDownloadError, match="licenseName must be text"):
            datasets.download_kaggle("publisher/synthetic-retail", tmp_path)
    assert not list(tmp_path.rglob("provenance.json"))


def test_r34_duplicate_json_cannot_change_license(tmp_path):
    raw = b'{"ref":"publisher/synthetic-retail","currentVersionNumber":1,"licenseName":"Unknown","licenseName":"MIT"}'
    with patch.object(datasets, "_fetch", return_value=(raw, {})) as fetch:
        with pytest.raises(datasets.DatasetDownloadError):
            datasets.download_kaggle("publisher/synthetic-retail", tmp_path)
    assert fetch.call_count == 1


@pytest.mark.parametrize("name", ["COM¹.csv", "lpt².txt", "NUL .csv"])
def test_r35_windows_device_aliases_never_reach_extraction(tmp_path, name):
    with pytest.raises(datasets.DatasetDownloadError, match="unsafe on Windows"):
        datasets._extract(zip_payload([(name, "data")]), tmp_path, max_bytes=100, max_files=5)
    assert not list(tmp_path.iterdir())


def test_r35_malformed_redirect_port_is_rejected():
    assert not datasets._allowed_url("https://www.kaggle.com:not-a-port/file")


class NetworkResponse:
    def __init__(self, payload, length):
        self.stream = io.BytesIO(payload)
        self.headers = {"Content-Length": length}

    def __enter__(self):
        return self

    def __exit__(self, *_):
        pass

    def read(self, count):
        return self.stream.read(count)

    def geturl(self):
        return "https://storage.googleapis.com/archive.zip"


@pytest.mark.parametrize("length,payload", [("-1", b"x"), ("garbage", b"x"), ("6", b"short")])
def test_r35_network_length_is_validated(length, payload):
    response = NetworkResponse(payload, length)
    with patch.object(datasets.request.OpenerDirector, "open", return_value=response):
        with pytest.raises(datasets.DatasetDownloadError, match="Content-Length"):
            datasets._fetch("https://www.kaggle.com/file", limit=100, timeout=10)


@pytest.mark.parametrize(
    "entries",
    [
        [("folder", "x"), ("folder/orders.csv", "data")],
        [("folder/orders.csv", "data"), ("folder", "x")],
    ],
)
def test_r35_zip_file_directory_conflict_is_reported(tmp_path, entries):
    with pytest.raises(datasets.DatasetDownloadError, match="conflicting"):
        datasets._extract(
            zip_payload(entries),
            tmp_path,
            max_bytes=100,
            max_files=5,
        )
    assert not list(tmp_path.iterdir())
