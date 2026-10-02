select count(*) as area_count
from {{ ref('mart_community') }}
having count(*) != 77