-- Singular dbt test: role-playing date sanity.
--
-- ship_date_key >= order_date_key for > 99% of fact rows. A small fraction of
-- negative deltas is legitimate (post-hoc corrections in the source system),
-- which is why the threshold is 99% and not 100%.
--
-- Returns: a single row if the violation rate exceeds 1%.

with deltas as (
    select
        case
            when ship_date_key < order_date_key then 1
            else 0
        end as is_negative
    from {{ ref('fct_order_lines') }}
),
agg as (
    select
        sum(is_negative)::numeric as bad,
        count(*)::numeric as total
    from deltas
)
select
    bad,
    total,
    bad / nullif(total, 0) as violation_rate
from agg
where total > 0 and (bad / total) > 0.01
