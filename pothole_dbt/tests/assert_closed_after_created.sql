select sr_number, created_at, closed_at
from {{ ref('int_phb') }}
where closed_at < created_at