-- Verifica que existan exactamente 48 registros (4 corredores x 12 meses de 2025)
with summary as (
    select
        count(*) as row_count,
        count(distinct zone) as zone_count,
        count(distinct month) as month_count
    from {{ ref('mart_seismic_monthly') }}
)
select *
from summary
where row_count <> 48
   or zone_count <> 4
   or month_count <> 12
