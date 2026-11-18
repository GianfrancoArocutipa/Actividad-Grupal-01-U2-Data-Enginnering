from datetime import date, datetime
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

import duckdb
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dashboard import render_dashboard
from pipeline import ZONES, export_site, load_earthquakes, transform


def make_synthetic_rows() -> list[tuple]:
    rows = []
    idx = 1
    for zone in ZONES:
        for month in range(1, 13):
            rows.append((
                f"us2025_{idx:04d}",
                zone,
                datetime(2025, month, 15, 12, 30, 0),
                4.5 if month % 2 == 0 else 5.4,
                45.0 if month % 3 == 0 else 120.0,
                -15.5,
                -72.4,
                f"25 km SO de Corredor {zone}",
            ))
            idx += 1
    return rows


def test_elt_pipeline_and_dbt_build():
    rows = make_synthetic_rows()
    with TemporaryDirectory(prefix="test-sismos-") as temp_dir:
        work_dir = Path(temp_dir)
        db_path = work_dir / "test.duckdb"
        load_earthquakes(db_path, rows)
        transform(db_path, work_dir)

        with duckdb.connect(str(db_path), read_only=True) as conn:
            stg_count = conn.execute("select count(*) from analytics.stg_earthquakes").fetchone()[0]
            mart_count = conn.execute("select count(*) from analytics.mart_seismic_monthly").fetchone()[0]
            assert stg_count == 48
            assert mart_count == 48


def test_render_dashboard_contains_zones_and_metrics():
    annual = [
        (zone, 12, 5.4, 95.0, 6)
        for zone in ZONES
    ]
    monthly = [
        (zone, date(2025, m, 1), 1, 4.8, 5.4, 95.0, 1, 0, 0, 1)
        for zone in ZONES
        for m in range(1, 13)
    ]
    top_events = [
        ("Andes Sur", "2025-06-15", 6.2, 38.5, "Superficial (<70 km)", "40 km O de Tacna, Perú")
    ]
    html = render_dashboard(2025, ZONES, annual, monthly, top_events)
    assert "Sismos Andes" in html
    assert "Andes Sur" in html
    assert "sismos-mensual.csv" in html
