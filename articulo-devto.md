---
title: "De la API Sísmica del USGS a un Observatorio Público Andino con dbt, DuckDB y GitHub Actions"
published: true
description: "Construimos un pipeline ELT libre de AWS para analizar 1.043 sismos del Cinturón Andino en 2025 con Python, DuckDB y dbt Core, desplegado automáticamente en GitHub Pages."
tags: dataengineering, dbt, duckdb, githubactions
---

¿Cómo varía la frecuencia y la profundidad de los sismos a lo largo de la zona de subducción sudamericana? Mientras que algunos segmentos liberan energía cerca de la superficie, otros concentran su actividad a más de 100 kilómetros de profundidad. Para responder esa pregunta con datos reproducibles construimos **Sismos Andes**, un pipeline batch de ingeniería de datos que consulta el catálogo del Servicio Geológico de los Estados Unidos (**USGS**), transforma y valida los registros con **DuckDB** y **dbt Core**, y publica automáticamente un observatorio web junto con su dataset en CSV.

[Ver el observatorio en vivo](https://gianfrancoarocutipa.github.io/Actividad-Grupal-01-U2-Data-Enginnering/) · [Explorar el repositorio público](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering) · [Ver el workflow de CI/CD](https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering/actions/workflows/pages.yml)

---

## 1. De la API de USGS al almacenamiento analítico en DuckDB

El script `pipeline.py` divide el margen convergente sudamericano en cuatro corredores latitudinales que cubren desde los 46°S hasta los 2°N:

- **Andes Norte** (`8°S a 2°N`): subducción ecuatorial y norte del Perú.
- **Andes Central** (`16°S a 8°S`): margen central peruano y dorsal de Nazca.
- **Andes Sur** (`26°S a 16°S`): codo de Arica, Altiplano y fosa peruano-chilena.
- **Andes Austral** (`46°S a 26°S`): segmento centro-sur de Chile.

Para cada corredor consultamos el endpoint FDSNWS (`https://earthquake.usgs.gov/fdsnws/event/1/query`) filtrando los eventos de 2025 con magnitud mínima de `4.0 Mw` en formato GeoJSON.

Antes de cargar cualquier fila en la base de datos, Python verifica que la respuesta sea una colección GeoJSON válida, que cada evento posea un identificador único (`id`), marca temporal en milisegundos UTC, magnitud y un vector tridimensional de coordenadas `[longitud, latitud, profundidad_km]`. Si un registro viene truncado, el proceso falla inmediatamente.

Los **1.043 eventos sísmicos** extraídos se insertan en la tabla `raw.earthquakes` dentro de una instancia efímera de **DuckDB**. Recrear la base en cada corrida garantiza idempotencia sin depender de servicios de almacenamiento en AWS.

---

## 2. Normalización y clasificación geofísica en `stg_earthquakes`

El primer modelo de dbt (`dbt/models/stg_earthquakes.sql`) limpia la capa cruda, elimina posibles duplicados en bordes geográficos mediante `row_number() over (partition by event_id ...)` y clasifica cada terremoto según su régimen hipocentral y su nivel de magnitud:

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

Esta distinción es clave en sismología andina: los sismos superficiales (`< 70 km`) ocurren cerca del contacto interplaca o en fallas corticales, mientras que los intermedios (`70–300 km`) reflejan la deformación interna de la placa de Nazca al hundirse bajo el continente.

---

## 3. Agregación mensual en `mart_seismic_monthly`

En `dbt/models/mart_seismic_monthly.sql`, usamos `ref('stg_earthquakes')` y cruzamos los corredores con la serie completa de doce meses de 2025 (`generate_series`). De esa forma aseguramos que el modelo final tenga exactamente **48 filas** (4 corredores × 12 meses) incluso si algún corredor tuviera un mes sin eventos:

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

Los resultados de 2025 muestran un contraste notable entre segmentos:
- **Andes Sur** concentró más de la mitad de la actividad (**558 sismos**, con 24 eventos `≥ 5,0 Mw`), dominada abrumadoramente por sismos de profundidad intermedia (**492 intermedios** frente a 66 superficiales) bajo el Altiplano y la fosa norte chilena.
- **Andes Austral** registró **270 sismos** y el evento de mayor magnitud del año (**6,4 Mw**), pero con predominio superficial (**183 superficiales**).
- **Andes Central** acumuló **127 sismos** (incluyendo los únicos **3 sismos profundos** `≥ 300 km` del catálogo) y **Andes Norte** sumó **88 sismos** con un pico de **6,3 Mw**.

---

## 4. Pruebas de calidad de datos que bloquean despliegues defectuosos

Ejecutar `dbt build` compila los modelos y corre **13 pruebas automatizadas** (definidas en `schema.yml` y en `dbt/tests/`). Además de validar unicidad y ausencia de nulos en `event_id` y `zone_month`, escribimos pruebas singulares en SQL para verificar invariantes físicos y contables:

```sql
-- dbt/tests/consistent_depth_breakdown.sql
select *
from {{ ref('mart_seismic_monthly') }}
where (shallow_events + intermediate_events + deep_events) <> total_events
   or strong_events > total_events
   or (total_events > 0 and max_magnitude < avg_magnitude)
```

Otra prueba (`valid_seismic_metrics.sql`) verifica que las magnitudes, profundidades y coordenadas se mantengan dentro de límites geofísicos válidos, y `complete_zones_months.sql` exige los 48 registros exactos. Si cualquiera de las 13 pruebas devuelve una sola fila anómala, `dbt build` termina con código de error y detiene la generación del sitio.

---

## 5. Automatización CI/CD con GitHub Actions y GitHub Pages

El flujo `.github/workflows/pages.yml` automatiza todo el ciclo sin servidores propios ni recursos de AWS:

1. **Integración Continua (`build`)**: En cada push, pull request o ejecución programada (`cron`), instala dependencias, ejecuta las pruebas unitarias con `pytest` y corre `python pipeline.py` (que extrae de USGS, ejecuta `dbt build` sobre DuckDB y genera la carpeta `site/`).
2. **Despliegue Continuo (`deploy`)**: En la rama `main`, el segundo job (`needs: build`) toma el artefacto con `index.html`, `styles.css` y `sismos-mensual.csv` y lo publica en **GitHub Pages** mediante `actions/deploy-pages@v4`.

---

## 6. Reproducir el proyecto localmente

Puedes clonar el repositorio y ejecutar las pruebas y el pipeline completo en menos de un minuto con Python 3.11+:

```bash
git clone https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering.git
cd Actividad-Grupal-01-U2-Data-Enginnering
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/pytest -q
.venv/bin/python pipeline.py
.venv/bin/python -m http.server 8000 --directory site
```

Al abrir `http://localhost:8000` tendrás el observatorio interactivo con las barras comparativas de frecuencia sísmica, el desglose por régimen hipocentral, la tabla de los 8 terremotos más fuertes de 2025 y la descarga directa del archivo `sismos-mensual.csv`.
