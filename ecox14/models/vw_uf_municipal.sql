{{ config(materialized='view') }}
-- Resposta da pergunta norteadora: uma linha por UF, so escolas municipais da analise.
select
    uf,
    count(*)                    as n_escolas,
    avg(ideb)                   as ideb_medio,
    avg(indice_infraestrutura)  as infra_media,
    avg(infra_basica)           as infra_basica_media,
    avg(infra_espacos_ensino)   as infra_espacos_ensino_media,
    avg(infra_acessibilidade)   as infra_acessibilidade_media,
    avg(infra_tecnologia)       as infra_tecnologia_media
from {{ ref('vw_escola_completa') }}
where na_analise
group by uf
order by uf
