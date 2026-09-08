import pyarrow.parquet as pq
import pytest

from conftest import api_row, snapshot, write_raw
from vsa.load import load, read_snapshots


@pytest.fixture
def raw_dir(tmp_path):
    d = tmp_path / "raw"
    d.mkdir()
    return d


def hour_file(raw_dir):
    return raw_dir / "booksummary_20260907T20.jsonl.gz"


def test_reads_every_member_of_an_appended_file(raw_dir):
    # record.py appends, so each hour file is a multi-member gzip stream.
    # A reader that stops after the first member loses 98% of the data silently.
    write_raw(hour_file(raw_dir), [snapshot(), snapshot(currency="ETH"), snapshot()])
    assert len(list(read_snapshots(hour_file(raw_dir)))) == 3


def test_writes_one_parquet_per_currency_and_hour(raw_dir, tmp_path):
    write_raw(hour_file(raw_dir), [snapshot(), snapshot(currency="ETH")])
    load(raw_dir, tmp_path / "parquet")
    assert (tmp_path / "parquet" / "BTC" / "2026-09-07" / "20.parquet").exists()
    assert (tmp_path / "parquet" / "ETH" / "2026-09-07" / "20.parquet").exists()


def test_reports_the_rows_it_wrote(raw_dir, tmp_path):
    write_raw(hour_file(raw_dir), [snapshot([api_row(), api_row()])])
    report = load(raw_dir, tmp_path / "parquet")
    assert report.rows == 2
    assert report.converted == ["booksummary_20260907T20.jsonl.gz"]


def test_a_second_run_skips_sources_that_have_not_changed(raw_dir, tmp_path):
    write_raw(hour_file(raw_dir), [snapshot()])
    load(raw_dir, tmp_path / "parquet")
    report = load(raw_dir, tmp_path / "parquet")
    assert report.converted == []
    assert report.skipped == ["booksummary_20260907T20.jsonl.gz"]


def test_a_source_file_that_grew_is_reconverted(raw_dir, tmp_path):
    # The current hour is still being appended to while the loader runs.
    write_raw(hour_file(raw_dir), [snapshot()])
    load(raw_dir, tmp_path / "parquet")
    write_raw(hour_file(raw_dir), [snapshot()])
    report = load(raw_dir, tmp_path / "parquet")
    assert report.converted == ["booksummary_20260907T20.jsonl.gz"]
    table = pq.read_table(tmp_path / "parquet" / "BTC" / "2026-09-07" / "20.parquet")
    assert table.num_rows == 2


def test_force_reconverts_everything(raw_dir, tmp_path):
    write_raw(hour_file(raw_dir), [snapshot()])
    load(raw_dir, tmp_path / "parquet")
    report = load(raw_dir, tmp_path / "parquet", force=True)
    assert report.converted == ["booksummary_20260907T20.jsonl.gz"]
