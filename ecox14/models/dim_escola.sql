-- Dimensao: uma linha por escola do IDEB 2025.
select
    id_escola                                  as escola_id,
    id_municipio                               as municipio_id,
    sigla_uf                                   as uf,
    cast(rede as varchar)                      as rede,
    cast(TP_LOCALIZACAO as varchar)            as localizacao,
    cast(TP_SITUACAO_FUNCIONAMENTO as varchar) as situacao_funcionamento
from {{ source('prata', 'ideb_censo_enriquecido') }}
