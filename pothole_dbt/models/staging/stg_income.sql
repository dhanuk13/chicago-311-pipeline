select
    community_area,
    community,
    income,
    hardship
from {{ ref('community_income') }}
where community_area is not null