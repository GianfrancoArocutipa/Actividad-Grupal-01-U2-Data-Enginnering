# Sismos Andes · Pipeline ELT con Python, DuckDB y dbt Core

Observatorio público de actividad sísmica en el Cinturón Andino durante **2025**, construido mediante un pipeline batch 100% libre de AWS (**Python + DuckDB + dbt Core + GitHub Actions + GitHub Pages**).

- **Tablero desplegado (GitHub Pages):** `https://gianfrancoarocutipa.github.io/Actividad-Grupal-01-U2-Data-Enginnering/`
- **Fuente de datos pública:** [USGS Earthquake Catalog API (FDSNWS)](https://earthquake.usgs.gov/fdsnws/event/1/)

---

## Arquitectura del Pipeline (Sin AWS)

```text
API USGS GeoJSON (4 corredores andinos, M ≥ 4.0)
        │
        ▼
  Python (pipeline.py) ──► Validación de esquema y coordenadas 3D
        │
        ▼
  DuckDB (raw.earthquakes)
        │
        ▼
  dbt Core (`dbt build`)
   ├── stg_earthquakes (deduplicación + clasificación de profundidad y magnitud)
   ├── mart_seismic_monthly (grilla completa de 48 corredor-meses)
   └── 13 data tests (integridad, rangos físicos, consistencia por estrato)
        │
        ▼
  Artefacto estático (`site/index.html`, `site/styles.css`, `site/sismos-mensual.csv`)
        │
        ▼
  GitHub Actions ──► Publicación automática en GitHub Pages
```

## Corredores Analizados (2025)

| Corredor | Rango Latitudinal | Sismos (≥ 4,0 Mw) | Mag. Máxima | Sismos ≥ 5,0 Mw |
| :--- | :--- | :---: | :---: | :---: |
| **Andes Norte** | 8°S a 2°N (Ecuador – Norte de Perú) | 88 | 6,3 Mw | 15 |
| **Andes Central** | 16°S a 8°S (Perú Central) | 127 | 6,2 Mw | 19 |
| **Andes Sur** | 26°S a 16°S (Sur de Perú – Norte de Chile) | 558 | 6,1 Mw | 24 |
| **Andes Austral** | 46°S a 26°S (Chile Centro-Sur) | 270 | 6,4 Mw | 16 |

## Ejecución Local

### En Windows (PowerShell)

```powershell
git clone https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering.git
cd Actividad-Grupal-01-U2-Data-Enginnering
py -3.11 -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\pytest -q
.\.venv\Scripts\python pipeline.py
.\.venv\Scripts\python -m http.server 8000 --directory site
```

### En Linux / macOS

```bash
git clone https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering.git
cd Actividad-Grupal-01-U2-Data-Enginnering
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/python pipeline.py
.venv/bin/python -m http.server 8000 --directory site
```

Abre `http://localhost:8000` en el navegador para explorar el tablero y descargar `sismos-mensual.csv`.
