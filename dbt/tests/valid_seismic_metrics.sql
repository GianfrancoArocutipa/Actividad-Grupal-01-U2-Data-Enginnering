-- Verifica rangos físicos válidos de magnitud y profundidad hipocentral
select *
from {{ ref('stg_earthquakes') }}
where magnitude < 4.0
   or magnitude > 10.0
   or depth_km < -10.0
   or depth_km > 800.0
   or latitude < -56.0
   or latitude > 10.0
   or longitude < -90.0
   or longitude > -60.0
