   select
       sr_number,
       status,
       cast(created_date       as timestamp) as created_at,
       cast(closed_date        as timestamp) as closed_at,
       cast(last_modified_date as timestamp) as last_modified_at,
       cast(community_area     as integer)   as community_area,
       cast(duplicate          as boolean)   as is_duplicate
   from {{ source('raw', 'raw_phb') }}