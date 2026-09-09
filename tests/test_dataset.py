from conftest import api_row, snapshot, write_raw
from vsa.dataset import connect
from vsa.load import load


def test_quotes_view_spans_every_loaded_partition(tmp_path):
    raw, out = tmp_path / "raw", tmp_path / "parquet"
    raw.mkdir()
    write_raw(raw / "booksummary_20260907T20.jsonl.gz", [snapshot([api_row(), api_row()])])
    write_raw(raw / "booksummary_20260907T21.jsonl.gz", [snapshot(currency="ETH")])
    load(raw, out)

    with connect(out) as con:
        assert con.sql("SELECT count(*) FROM quotes").fetchone()[0] == 3
        assert con.sql("SELECT count(*) FROM quotes WHERE currency='ETH'").fetchone()[0] == 1


def test_timestamps_render_in_utc_whatever_the_machine_is_set_to(tmp_path):
    # snapshot_ts is stored as an instant; without pinning the session timezone
    # every printed time silently becomes the analyst's local one.
    raw, out = tmp_path / "raw", tmp_path / "parquet"
    raw.mkdir()
    write_raw(raw / "booksummary_20260907T20.jsonl.gz", [snapshot()])
    load(raw, out)

    with connect(out) as con:
        assert con.sql("SELECT strftime(snapshot_ts, '%Y-%m-%d %H:%M') FROM quotes").fetchone()[0] \
            == "2026-09-07 20:00"
