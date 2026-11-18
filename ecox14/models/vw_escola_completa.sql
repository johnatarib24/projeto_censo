{{ config(materialized='view') }}
-- Tabela achatada, recriada a partir da estrela.
select
    f.*,
    d.municipio_id,
    d.uf,
    d.rede,
    d.localizacao,
    d.situacao_funcionamento
from {{ ref('fato_escola') }} f
join {{ ref('dim_escola') }} d using (escola_id)
