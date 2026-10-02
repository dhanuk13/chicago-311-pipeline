select
    *,
    date_diff('second', created_at, closed_at) / 86400.0 as response_days
from {{ ref('stg_phb') }}
where not is_duplicate