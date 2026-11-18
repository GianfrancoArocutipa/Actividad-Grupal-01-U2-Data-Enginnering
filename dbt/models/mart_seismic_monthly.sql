with zones as (
    select distinct zone
    from {{ ref('stg_earthquakes') }}
),

months as (
    select cast(month_start as date) as month
    from generate_series(date '2025-01-01', date '2025-12-01', interval '1 month') as t(month_start)
),

grid as (
    select
        zones.zone,
        months.month
    from zones
    cross join months
),

aggregated as (
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
)

select
    grid.zone || '-' || strftime(grid.month, '%Y-%m') as zone_month,
    grid.zone,
    grid.month,
    coalesce(aggregated.total_events, 0) as total_events,
    coalesce(aggregated.avg_magnitude, 0.0) as avg_magnitude,
    coalesce(aggregated.max_magnitude, 0.0) as max_magnitude,
    coalesce(aggregated.avg_depth_km, 0.0) as avg_depth_km,
    coalesce(aggregated.shallow_events, 0) as shallow_events,
    coalesce(aggregated.intermediate_events, 0) as intermediate_events,
    coalesce(aggregated.deep_events, 0) as deep_events,
    coalesce(aggregated.strong_events, 0) as strong_events
from grid
left join aggregated
    on grid.zone = aggregated.zone
   and grid.month = aggregated.month
order by grid.zone, grid.month
