---
title: "From the USGS Seismic API to a Public Andean Observatory with dbt, DuckDB, and GitHub Actions"
published: true
description: "Building a zero-AWS ELT batch pipeline to analyze 1,043 Andean earthquakes in 2025 with Python, DuckDB, and dbt Core, automatically deployed to GitHub Pages."
tags: dataengineering, dbt, duckdb, githubactions
---

How do earthquake frequency and hypocentral depth vary along the South American subduction zone? While some tectonic segments release energy near the surface, others concentrate seismic activity more than 100 kilometers underground. To explore this question with reproducible data, we built **Sismos Andes**, a zero-AWS data engineering batch pipeline that queries the United States Geological Survey (**USGS**) catalog, transforms and validates records with **DuckDB** and **dbt Core**, and automatically publishes a static web observatory along with its monthly CSV dataset.

[Live Observatory (GitHub Pages)](https://gianfrancoarocutipa.github.io/Actividad-Grupal-01-U2-Data-Enginnering/) · [Public GitHub Repository](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering) · [CI/CD Deployment Workflow](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering/actions/workflows/pages.yml)

---

## 1. From the USGS FDSNWS API to Analytical Storage in DuckDB

In [`pipeline.py`](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering/blob/main/pipeline.py), we divide the South American convergent margin into four latitudinal corridors spanning from 46°S to 2°N:

- **Andes Norte** (`8°S to 2°N`): Ecuadorian and Northern Peru subduction zone.
- **Andes Central** (`16°S to 8°S`): Central Peruvian margin and Nazca Ridge interface.
- **Andes Sur** (`26°S to 16°S`): Arica Bend, Altiplano, and Peru–Chile Trench.
- **Andes Austral** (`46°S to 26°S`): Central–Southern Chile segment.

For each corridor, Python queries the public USGS FDSNWS endpoint (`https://earthquake.usgs.gov/fdsnws/event/1/query`), filtering all 2025 seismic events with a minimum magnitude of `4.0 Mw` in GeoJSON format.

Before loading a single row into the database, our ingestion layer validates that the payload is a well-formed GeoJSON `FeatureCollection` and that every event contains a unique identifier (`id`), a valid UTC epoch timestamp, a magnitude reading, and a 3D coordinate vector `[longitude, latitude, depth_km]`. If any record is malformed, the ingestion fails fast.

All **1,043 seismic events** extracted across the four corridors are loaded into `raw.earthquakes` inside an ephemeral **DuckDB** instance. Re-creating the embedded analytical database on every execution guarantees idempotency without relying on AWS S3 or Redshift.

---

## 2. Normalization and Geophysical Classification in `stg_earthquakes`

Our first dbt model ([`dbt/models/stg_earthquakes.sql`](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering/blob/main/dbt/models/stg_earthquakes.sql)) cleans the raw layer, deduplicates boundary events using `row_number() over (partition by event_id ...)`, and classifies each earthquake by its hypocentral depth regime and magnitude tier:

```sql
case
    when depth_km < 70.0 then 'Superficial (<70 km)'
    when depth_km < 300.0 then 'Intermedio (70-300 km)'
    else 'Profundo (>=300 km)'
end as depth_regime,
case
    when magnitude >= 6.0 then 'Fuerte (>=6.0)'
    when magnitude >= 5.0 then 'Moderado (5.0-5.9)'
    else 'Ligero (4.0-4.9)'
end as magnitude_tier
```

This geophysical distinction is essential in Andean seismology: shallow earthquakes (`< 70 km`) occur near the interplate contact or upper crustal faults, whereas intermediate-depth events (`70–300 km`) reflect internal slab deformation within the subducting Nazca plate.

---

## 3. Monthly Aggregation in `mart_seismic_monthly`

In [`dbt/models/mart_seismic_monthly.sql`](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering/blob/main/dbt/models/mart_seismic_monthly.sql), we reference `{{ ref('stg_earthquakes') }}` and cross-join the distinct corridors with a complete 12-month calendar series (`generate_series`). This guarantees that our analytical mart always outputs an exact grid of **48 rows** (4 corridors × 12 months):

```sql
select
    zone,
    month,
    count(*) as total_events,
    round(avg(magnitude), 2) as avg_magnitude,
    round(max(magnitude), 2) as max_magnitude,
    round(avg(depth_km), 1) as avg_depth_km,
    count(*) filter (where depth_km < 70.0) as shallow_events,
    count(*) filter (where depth_km >= 70.0 and depth_km < 300.0) as intermediate_events,
    count(*) filter (where depth_km >= 300.0) as deep_events,
    count(*) filter (where magnitude >= 5.0) as strong_events
from {{ ref('stg_earthquakes') }}
group by zone, month
```

The 2025 metrics reveal a sharp structural contrast across the Andean margin:
- **Andes Sur** accounted for more than half of all seismic activity (**558 earthquakes**, including 24 events `≥ 5.0 Mw`), overwhelmingly dominated by intermediate-depth seismicity (**492 intermediate** vs. 66 shallow events) beneath the Altiplano and Northern Chile trench.
- **Andes Austral** recorded **270 earthquakes** and the strongest event of the year (**6.4 Mw**), driven primarily by shallow interplate activity (**183 shallow events**).
- **Andes Central** accumulated **127 earthquakes** (including the only **3 deep-focus earthquakes** `≥ 300 km` in the catalog), while **Andes Norte** registered **88 earthquakes** with a peak magnitude of **6.3 Mw**.

---

## 4. Data Quality Gates that Block Broken Deployments

Running `dbt build` compiles our SQL models and executes **13 automated data tests** defined in [`dbt/models/schema.yml`](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering/blob/main/dbt/models/schema.yml) and `dbt/tests/`. Beyond enforcing `not_null` and `unique` constraints on `event_id` and `zone_month`, we wrote singular SQL tests to enforce physical and accounting invariants:

```sql
-- dbt/tests/consistent_depth_breakdown.sql
select *
from {{ ref('mart_seismic_monthly') }}
where (shallow_events + intermediate_events + deep_events) <> total_events
   or strong_events > total_events
   or (total_events > 0 and max_magnitude < avg_magnitude)
```

In addition, [`valid_seismic_metrics.sql`](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering/blob/main/dbt/tests/valid_seismic_metrics.sql) asserts that magnitudes, depths, and bounding-box coordinates stay within valid geophysical ranges, and [`complete_zones_months.sql`](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering/blob/main/dbt/tests/complete_zones_months.sql) verifies the exact 48-row monthly grid. If any of the 13 tests returns a single failing row, `dbt build` exits with a non-zero code and halts the site generation before deployment.

---

## 5. Automated CI/CD with GitHub Actions and GitHub Pages (Zero AWS)

Our workflow ([`.github/workflows/pages.yml`](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering/blob/main/.github/workflows/pages.yml)) automates the entire delivery lifecycle without custom servers or AWS dependencies:

1. **Continuous Integration (`build` job)**: On every push, pull request, or scheduled weekly cron run, GitHub Actions installs pinned dependencies, runs unit tests with `pytest`, and executes `python pipeline.py` (which queries USGS, runs `dbt build` on DuckDB, and outputs the static `site/` artifact).
2. **Continuous Deployment (`deploy` job)**: On the `main` branch, a second job (`needs: build`) publishes the verified `index.html`, `styles.css`, and `sismos-mensual.csv` artifact directly to **GitHub Pages** via `actions/deploy-pages@v4`.

---

## 6. Reproduce the Pipeline Locally

Clone the repository and run both the test suite and the end-to-end ELT pipeline in under a minute using Python 3.11+:

```bash
git clone https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering.git
cd Actividad-Grupal-01-U2-Data-Enginnering
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/python pipeline.py
.venv/bin/python -m http.server 8000 --directory site
```

Open `http://localhost:8000` in your browser to explore the interactive seismic dashboard, compare monthly frequency bars and depth breakdowns across the four Andean corridors, inspect the top 8 earthquakes of 2025, and download `sismos-mensual.csv`.
