with deduplicated as (
    select
        event_id,
        zone,
        observed_at_utc,
        cast(date_trunc('day', observed_at_utc) as date) as observed_on,
        cast(date_trunc('month', observed_at_utc) as date) as month,
        round(cast(magnitude as double), 2) as magnitude,
        round(cast(depth_km as double), 2) as depth_km,
        round(cast(latitude as double), 4) as latitude,
        round(cast(longitude as double), 4) as longitude,
        coalesce(place, 'Sin ubicación detallada') as place,
        case
            when depth_km < 70.0 then 'Superficial (<70 km)'
            when depth_km < 300.0 then 'Intermedio (70-300 km)'
            else 'Profundo (>=300 km)'
        end as depth_regime,
        case
            when magnitude >= 6.0 then 'Fuerte (>=6.0)'
            when magnitude >= 5.0 then 'Moderado (5.0-5.9)'
            else 'Ligero (4.0-4.9)'
        end as magnitude_tier,
        row_number() over (partition by event_id order by observed_at_utc desc) as row_num
    from {{ source('raw', 'earthquakes') }}
)

select
    event_id,
    zone,
    observed_at_utc,
    observed_on,
    month,
    magnitude,
    depth_km,
    latitude,
    longitude,
    place,
    depth_regime,
    magnitude_tier
from deduplicated
where row_num = 1
