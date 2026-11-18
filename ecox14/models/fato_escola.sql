-- Fato: uma escola em um ano. O where e o filtro de integridade (chave presente).
select
    id_escola                    as escola_id,
    ano,
    ideb,
    taxa_aprovacao,
    indicador_rendimento,
    nota_saeb_matematica,
    nota_saeb_lingua_portuguesa,
    nota_saeb_media_padronizada,
    indice_infraestrutura,
    infra_basica,
    infra_espacos_ensino,
    infra_acessibilidade,
    infra_tecnologia,
    ideb_dif_mediana_uf,
    infra_dif_mediana_uf,
    ideb_disponivel,
    na_analise
from {{ source('prata', 'ideb_censo_enriquecido') }}
where id_escola is not null
