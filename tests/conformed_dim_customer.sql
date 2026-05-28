-- Singular dbt test: conformed-dim invariant on dim_customer.
--
-- Every sk_customer appearing in fct_returns MUST also be resolvable in
-- dim_customer (the SAME dim used by fct_order_lines). If you accidentally
-- built a separate "dim_customer_for_returns" — or filtered dim_customer
-- differently between the two facts — this test catches it.
--
-- Returns: rows from fct_returns whose sk_customer is missing from dim_customer.
-- Empty result = pass.

select
    fr.sk_customer
from {{ ref('fct_returns') }} fr
left join {{ ref('dim_customer') }} dc
    on dc.sk_customer = fr.sk_customer
where dc.sk_customer is null
