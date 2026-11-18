-- Verifica que la suma de estratos de profundidad coincida con el total mensual
select *
from {{ ref('mart_seismic_monthly') }}
where (shallow_events + intermediate_events + deep_events) <> total_events
   or strong_events > total_events
   or (total_events > 0 and max_magnitude < avg_magnitude)
