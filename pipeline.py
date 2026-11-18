import csv
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

import duckdb
import requests

from dashboard import render_dashboard


ROOT = Path(__file__).resolve().parent
YEAR = 2025
START = f"{YEAR}-01-01T00:00:00"
END = f"{YEAR}-12-31T23:59:59"
MIN_MAGNITUDE = 4.0

# Cuatro corredores sísmicos del Cinturón Andino (lat_min, lat_max, lon_min, lon_max)
ZONES = {
    "Andes Norte": (-8.0, 2.0, -83.0, -75.0),
    "Andes Central": (-16.0, -8.0, -80.0, -70.0),
    "Andes Sur": (-26.0, -16.0, -76.0, -66.0),
    "Andes Austral": (-46.0, -26.0, -76.0, -68.0),
}


def extract_zone(zone_name: str, min_lat: float, max_lat: float, min_lon: float, max_lon: float) -> list[tuple]:
    params = {
        "format": "geojson",
        "starttime": START,
        "endtime": END,
        "minlatitude": min_lat,
        "maxlatitude": max_lat,
        "minlongitude": min_lon,
        "maxlongitude": max_lon,
        "minmagnitude": MIN_MAGNITUDE,
        "orderby": "time-asc",
    }
    endpoint = "https://earthquake.usgs.gov/fdsnws/event/1/query"
    print(f"Consultando catálogo sísmico USGS para {zone_name}...", flush=True)
    response = requests.get(endpoint, params=params, timeout=45)
    response.raise_for_status()
    payload = response.json()

    if payload.get("type") != "FeatureCollection" or "features" not in payload:
        raise ValueError(f"{zone_name}: formato GeoJSON inválido en respuesta de USGS")

    rows = []
    for feature in payload["features"]:
        event_id = feature.get("id")
        props = feature.get("properties") or {}
        geom = feature.get("geometry") or {}
        coords = geom.get("coordinates") or []

        if not event_id or len(coords) < 3:
            raise ValueError(f"{zone_name}: evento incompleto sin coordenadas 3D")

        lon, lat, depth_km = float(coords[0]), float(coords[1]), float(coords[2])
        mag = props.get("mag")
        time_ms = props.get("time")
        place = props.get("place") or "Ubicación no especificada"

        if mag is None or time_ms is None:
            raise ValueError(f"{zone_name}: evento {event_id} sin magnitud o marca temporal")

        observed_at = datetime.fromtimestamp(time_ms / 1000.0, tz=timezone.utc).replace(tzinfo=None)
        rows.append((
            str(event_id),
            zone_name,
            observed_at,
            float(mag),
            depth_km,
            lat,
            lon,
            str(place),
        ))

    if not rows:
        raise ValueError(f"{zone_name}: la consulta no devolvió eventos sísmicos")

    return rows


def load_earthquakes(database_path: Path, rows: list[tuple]) -> None:
    with duckdb.connect(str(database_path)) as connection:
        connection.execute("create schema raw")
        connection.execute("""
            create table raw.earthquakes (
                event_id varchar,
                zone varchar,
                observed_at_utc timestamp,
                magnitude double,
                depth_km double,
                latitude double,
                longitude double,
                place varchar
            )
        """)
        connection.executemany(
            "insert into raw.earthquakes values (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )


def transform(database_path: Path, work_dir: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            "from dbt.cli.main import cli; cli()",
            "build",
            "--project-dir",
            str(ROOT / "dbt"),
            "--profiles-dir",
            str(ROOT / "dbt"),
            "--target-path",
            str(work_dir / "target"),
            "--log-path",
            str(work_dir / "logs"),
            "--no-send-anonymous-usage-stats",
            "--no-use-colors",
        ],
        check=True,
        env={**os.environ, "SISMOS_DUCKDB_PATH": str(database_path)},
    )


def export_site(database_path: Path) -> None:
    with duckdb.connect(str(database_path), read_only=True) as connection:
        result = connection.execute("""
            select
                zone,
                month,
                total_events,
                avg_magnitude,
                max_magnitude,
                avg_depth_km,
                shallow_events,
                intermediate_events,
                deep_events,
                strong_events
            from analytics.mart_seismic_monthly
            order by zone, month
        """)
        columns = [column[0] for column in result.description]
        monthly = result.fetchall()

        annual = connection.execute("""
            select
                zone,
                count(*) as total_events,
                round(max(magnitude), 1) as max_magnitude,
                round(avg(depth_km), 1) as avg_depth_km,
                count(*) filter (where magnitude >= 5.0) as strong_events
            from analytics.stg_earthquakes
            group by zone
        """).fetchall()

        top_events = connection.execute("""
            select
                zone,
                strftime(observed_on, '%Y-%m-%d') as date_label,
                magnitude,
                depth_km,
                depth_regime,
                place
            from analytics.stg_earthquakes
            order by magnitude desc, depth_km asc
            limit 8
        """).fetchall()

    expected_rows = len(ZONES) * 12
    if len(monthly) != expected_rows:
        raise ValueError(f"Se esperaban {expected_rows} filas mensuales, se obtuvieron {len(monthly)}")

    site = ROOT / "site"
    site.mkdir(exist_ok=True)
    with (site / "sismos-mensual.csv").open("w", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(columns)
        writer.writerows(monthly)

    html = render_dashboard(YEAR, ZONES, annual, monthly, top_events)
    (site / "index.html").write_text(html, encoding="utf-8")
    (site / "styles.css").write_bytes((ROOT / "dashboard.css").read_bytes())
    print(f"Tablero y CSV generados en {site} ({len(monthly)} filas mensuales)", flush=True)


def main() -> None:
    rows = [
        row
        for zone_name, bbox in ZONES.items()
        for row in extract_zone(zone_name, *bbox)
    ]
    with TemporaryDirectory(prefix="sismos-", dir=ROOT) as temp_dir:
        work_dir = Path(temp_dir)
        database_path = work_dir / "sismos.duckdb"
        load_earthquakes(database_path, rows)
        transform(database_path, work_dir)
        export_site(database_path)


if __name__ == "__main__":
    main()
