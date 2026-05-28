-- Singular dbt test: fact grain on fct_order_lines.
--
-- The declared grain is ONE row per (order_id, line_number). This test fails if
-- ANY (order_id, line_number) pair appears more than once. dbt's convention:
-- this test returns rows that violate the invariant — empty result = pass.
--
-- Why this fires in practice:
--   - The learner joined dim_customer in stg_order_lines without deduplicating
--     dim_customer (e.g. two rows for the same customer_id because they accidentally
--     UNION ALL-ed the sentinel "unknown customer" twice).
--   - The learner used dim_product without uniqueness on product_id, fanning out
--     every line that referenced a product with multiple dim rows.
--   - The learner LEFT JOINed dim_date on order_date and ship_date in the same
--     CTE alias — joining dim_date twice via the same alias creates a cartesian
--     when order_date != ship_date.

select
    order_id,
    line_number,
    count(*) as row_count
from {{ ref('fct_order_lines') }}
group by order_id, line_number
having count(*) > 1
