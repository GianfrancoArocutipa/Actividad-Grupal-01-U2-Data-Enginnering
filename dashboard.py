from html import escape


MONTHS = [
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
]

ZONES_DETAIL = {
    "Andes Norte": "Subducción ecuatorial y norte peruano (8°S a 2°N · Ecuador, Piura, Tumbes, Amazonas).",
    "Andes Central": "Margen central peruano y dorsal de Nazca (16°S a 8°S · Lima, Ica, Junín, Ayacucho).",
    "Andes Sur": "Codo de Arica, Altiplano y fosa chileno-peruana (26°S a 16°S · Arequipa, Tacna, Tarapacá, Antofagasta).",
    "Andes Austral": "Segmento centro-sur chileno (46°S a 26°S · Atacama, Valparaíso, Maule, Biobío).",
}


def slugify(name: str) -> str:
    return name.lower().replace(" ", "-")


def number(value: float, decimals: int = 1) -> str:
    return f"{value:.{decimals}f}".replace(".", ",")


def render_top_events(top_events: list[tuple]) -> str:
    items = []
    for zone, date_label, mag, depth_km, regime, place in top_events:
        items.append(
            f"""            <tr>
              <td><span class="badge">{escape(zone)}</span></td>
              <td>{escape(date_label)}</td>
              <td class="num strong-mag">{number(mag, 1)} Mw</td>
              <td class="num">{number(depth_km, 1)} km</td>
              <td>{escape(regime)}</td>
              <td>{escape(place)}</td>
            </tr>"""
        )
    return "\n".join(items)


def render_zone(zone: str, annual: tuple, monthly: list[tuple], max_events: int) -> str:
    total_events, max_mag, avg_depth, strong_events = annual
    slug = slugify(zone)
    rows = []
    for (
        _,
        month,
        events,
        avg_mag,
        m_max_mag,
        m_avg_depth,
        shallow,
        intermediate,
        deep,
        strong,
    ) in monthly:
        width = round((events / max_events) * 100, 1) if max_events else 0
        rows.append(
            f"""            <tr>
              <th scope="row">{MONTHS[month.month - 1]}</th>
              <td class="bar-cell">
                <div class="bar-wrap">
                  <span class="bar" style="width: {width}%"></span>
                  <span class="bar-val">{events}</span>
                </div>
              </td>
              <td class="num">{number(avg_mag, 2)}</td>
              <td class="num">{number(m_max_mag, 1)}</td>
              <td class="num">{number(m_avg_depth, 1)} km</td>
              <td class="num">{shallow} / {intermediate} / {deep}</td>
              <td class="num">{strong}</td>
            </tr>"""
        )

    return f"""    <section id="{slug}" class="zone-card" aria-labelledby="heading-{slug}">
      <header class="zone-heading">
        <div>
          <h2 id="heading-{slug}">{escape(zone)}</h2>
          <p>{escape(ZONES_DETAIL[zone])}</p>
        </div>
      </header>
      <dl class="metrics">
        <div><dt>Sismos registrados (≥ 4,0)</dt><dd>{total_events}</dd></div>
        <div><dt>Magnitud máxima</dt><dd>{number(max_mag, 1)} <span>Mw</span></dd></div>
        <div><dt>Profundidad media</dt><dd>{number(avg_depth, 1)} <span>km</span></dd></div>
        <div><dt>Eventos fuertes (≥ 5,0)</dt><dd>{strong_events}</dd></div>
      </dl>
      <div class="table-scroll" role="region" aria-label="Datos sísmicos mensuales de {escape(zone)}" tabindex="0">
        <table>
          <thead>
            <tr>
              <th scope="col">Mes</th>
              <th scope="col">Frecuencia sísmica</th>
              <th scope="col">Mag. media</th>
              <th scope="col">Mag. máx.</th>
              <th scope="col">Prof. media</th>
              <th scope="col">Sup. / Int. / Prof.</th>
              <th scope="col">Sismos ≥ 5,0</th>
            </tr>
          </thead>
          <tbody>
{chr(10).join(rows)}
          </tbody>
        </table>
      </div>
    </section>"""


def render_dashboard(
    year: int,
    zones: dict,
    annual: list[tuple],
    monthly: list[tuple],
    top_events: list[tuple],
) -> str:
    annual_by_zone = {
        zone: values
        for zone, *values in annual
    }
    for zone in zones:
        annual_by_zone.setdefault(zone, (0, 0.0, 0.0, 0))

    total_year_events = sum(v[0] for v in annual_by_zone.values())
    max_year_mag = max((v[1] for v in annual_by_zone.values()), default=0.0)
    total_strong = sum(v[3] for v in annual_by_zone.values())
    max_monthly_events = max(1, *(row[2] for row in monthly))

    links = "\n".join(
        f'<a href="#{slugify(zone)}">{escape(zone)}</a>'
        for zone in zones
    )
    sections = "\n".join(
        render_zone(
            zone,
            annual_by_zone[zone],
            [row for row in monthly if row[0] == zone],
            max_monthly_events,
        )
        for zone in zones
    )
    top_rows = render_top_events(top_events)

    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="description" content="Observatorio de actividad sísmica en el Cinturón Andino ({year}) procesado con Python, DuckDB y dbt.">
  <title>Sismos Andes · Observatorio Sísmico {year}</title>
  <link rel="stylesheet" href="styles.css">
</head>
<body>
  <header class="hero">
    <div class="container">
      <p class="period">Catálogo Sísmico USGS · Enero–diciembre {year}</p>
      <h1>Sismos Andes</h1>
      <p class="intro">Actividad sísmica, distribución hipocentral y magnitudes (≥ 4,0 Mw) a lo largo de cuatro corredores de subducción del Cinturón Andino.</p>
      <div class="global-summary">
        <div><span>Total anual andino</span><strong>{total_year_events} sismos</strong></div>
        <div><span>Mayor magnitud registrada</span><strong>{number(max_year_mag, 1)} Mw</strong></div>
        <div><span>Eventos moderados/fuertes (≥ 5,0)</span><strong>{total_strong} sismos</strong></div>
      </div>
      <div class="actions">
        <a class="download" href="sismos-mensual.csv" download>Descargar resumen mensual (CSV)</a>
      </div>
    </div>
  </header>
  <main class="container">
    <nav class="zone-nav" aria-label="Corredores sísmicos">
      {links}
      <a href="#eventos-destacados">Mayores eventos</a>
    </nav>
    <p class="reading-note">Las barras de frecuencia mensual comparten la misma escala entre los cuatro corredores. La columna <strong>Sup. / Int. / Prof.</strong> desglosa sismos superficiales (&lt;70 km), intermedios (70–300 km) y profundos (≥300 km).</p>
    {sections}
    <section id="eventos-destacados" class="zone-card" aria-labelledby="heading-destacados">
      <header class="zone-heading">
        <div>
          <h2 id="heading-destacados">Eventos de mayor magnitud en {year}</h2>
          <p>Los 8 sismos de mayor liberación de energía registrados en los cuatro corredores durante el periodo analizado.</p>
        </div>
      </header>
      <div class="table-scroll" role="region" aria-label="Eventos de mayor magnitud" tabindex="0">
        <table>
          <thead>
            <tr>
              <th scope="col">Corredor</th>
              <th scope="col">Fecha (UTC)</th>
              <th scope="col">Magnitud</th>
              <th scope="col">Profundidad</th>
              <th scope="col">Régimen</th>
              <th scope="col">Epicentro referencial</th>
            </tr>
          </thead>
          <tbody>
{top_rows}
          </tbody>
        </table>
      </div>
    </section>
  </main>
  <footer class="container footer">
    <p>Pipeline batch construido con <strong>Python</strong>, <strong>DuckDB</strong> y <strong>dbt Core</strong>. Datos obtenidos de la API pública <a href="https://earthquake.usgs.gov/fdsnws/event/1/">USGS Earthquake Catalog</a>.</p>
    <a href="https://github.com/GianfrancoArocutipa/Actividad-Grupal-01-U2-Data-Enginnering">Explorar código fuente en GitHub</a>
  </footer>
</body>
</html>
"""
