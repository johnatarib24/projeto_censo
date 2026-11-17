"""
Carga em banco (DuckDB) e camada Ouro.

    python src/carga.py

Le os Parquet da prata para o esquema `prata` e constroi, em SQL, o esquema
`ouro`: a dimensao, a fato e duas views. O banco inteiro e o arquivo
dados/ouro/projeto.duckdb (apagar o arquivo e uma forma legitima de recomecar).
"""
import logging

import duckdb

import config

log = logging.getLogger(__name__)

TABELAS_PRATA = ["ideb_escolas", "censo_escolas", "ideb_censo_enriquecido"]


def um_valor(con, sql):
    """Le um numero de dentro do Python (con.execute, e nao con.sql)."""
    return con.execute(sql).fetchone()[0]


def conectar():
    config.OURO.mkdir(parents=True, exist_ok=True)
    log.info("abrindo o banco: %s", config.BANCO)
    return duckdb.connect(str(config.BANCO))


def criar_esquemas(con):
    con.execute("CREATE SCHEMA IF NOT EXISTS prata")
    con.execute("CREATE SCHEMA IF NOT EXISTS ouro")


def carregar_prata(con):
    """A prata entra como esta: uma tabela por Parquet, sem importar nada."""
    for nome in TABELAS_PRATA:
        arquivo = config.PRATA / f"{nome}.parquet"
        if not arquivo.exists():
            raise FileNotFoundError(f"{arquivo} nao existe; rode a etapa transformacao/enriquecimento")
        caminho = arquivo.as_posix()
        con.execute(f"""
            CREATE OR REPLACE TABLE prata.{nome} AS
            SELECT * FROM read_parquet('{caminho}')
        """)
        log.info("prata.%s: %d linhas", nome, um_valor(con, f"SELECT COUNT(*) FROM prata.{nome}"))


def construir_ouro(con):
    """A ouro nasce dentro do banco, a partir da prata, e fala a lingua do negocio."""
    # dimensao: uma linha por escola do IDEB 2025
    con.execute("""
        CREATE OR REPLACE TABLE ouro.dim_escola AS
        SELECT
            id_escola                              AS escola_id,
            id_municipio                           AS municipio_id,
            sigla_uf                               AS uf,
            CAST(rede AS VARCHAR)                  AS rede,
            CAST(TP_LOCALIZACAO AS VARCHAR)        AS localizacao,
            CAST(TP_SITUACAO_FUNCIONAMENTO AS VARCHAR) AS situacao_funcionamento
        FROM prata.ideb_censo_enriquecido
    """)

    # fato: uma escola em um ano. O WHERE e o filtro de integridade (chave presente)
    con.execute("""
        CREATE OR REPLACE TABLE ouro.fato_escola AS
        SELECT
            id_escola                    AS escola_id,
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
        FROM prata.ideb_censo_enriquecido
        WHERE id_escola IS NOT NULL
    """)

    # tabela achatada, recriada a partir da estrela como consulta salva
    con.execute("""
        CREATE OR REPLACE VIEW ouro.vw_escola_completa AS
        SELECT f.*, d.municipio_id, d.uf, d.rede, d.localizacao, d.situacao_funcionamento
        FROM ouro.fato_escola f
        JOIN ouro.dim_escola d USING (escola_id)
    """)

    # a resposta da pergunta norteadora: uma linha por UF, so escolas municipais da analise
    con.execute("""
        CREATE OR REPLACE VIEW ouro.vw_uf_municipal AS
        SELECT
            uf,
            COUNT(*)                         AS n_escolas,
            AVG(ideb)                        AS ideb_medio,
            AVG(indice_infraestrutura)       AS infra_media,
            AVG(infra_basica)                AS infra_basica_media,
            AVG(infra_espacos_ensino)        AS infra_espacos_ensino_media,
            AVG(infra_acessibilidade)        AS infra_acessibilidade_media,
            AVG(infra_tecnologia)            AS infra_tecnologia_media
        FROM ouro.vw_escola_completa
        WHERE na_analise
        GROUP BY uf
        ORDER BY uf
    """)
    for tabela in ["dim_escola", "fato_escola", "vw_escola_completa", "vw_uf_municipal"]:
        log.info("ouro.%s: %d linhas", tabela, um_valor(con, f"SELECT COUNT(*) FROM ouro.{tabela}"))


def conferir(con):
    """Cada consulta precisa devolver zero. Se alguma nao devolver, para o pipeline."""
    verificacoes = [
        ("fato: pares (escola, ano) repetidos",
         """SELECT COUNT(*) FROM (
                SELECT escola_id, ano FROM ouro.fato_escola
                GROUP BY escola_id, ano HAVING COUNT(*) > 1)"""),
        ("fato sem dimensao (orfaos)",
         """SELECT COUNT(*) FROM ouro.fato_escola f
            LEFT JOIN ouro.dim_escola d USING (escola_id)
            WHERE d.escola_id IS NULL"""),
        ("dim: escolas repetidas",
         "SELECT COUNT(*) - COUNT(DISTINCT escola_id) FROM ouro.dim_escola"),
        ("fato menos prata (diferenca de linhas)",
         """SELECT (SELECT COUNT(*) FROM ouro.fato_escola)
                  - (SELECT COUNT(*) FROM prata.ideb_censo_enriquecido)"""),
        ("view completa menos fato (diferenca de linhas)",
         """SELECT (SELECT COUNT(*) FROM ouro.vw_escola_completa)
                  - (SELECT COUNT(*) FROM ouro.fato_escola)"""),
        (f"UFs em vw_uf_municipal, diferenca para {config.N_UFS_ANALISE}",
         f"SELECT ABS(COUNT(*) - {config.N_UFS_ANALISE}) FROM ouro.vw_uf_municipal"),
        ("DF em vw_uf_municipal",
         "SELECT COUNT(*) FROM ouro.vw_uf_municipal WHERE uf = 'DF'"),
    ]
    falhas = []
    for descricao, sql in verificacoes:
        valor = um_valor(con, sql)
        if valor == 0:
            log.info("ok: %s = 0", descricao)
        else:
            log.error("FALHOU: %s = %s (esperado 0)", descricao, valor)
            falhas.append(descricao)
    if falhas:
        raise RuntimeError(f"{len(falhas)} conferencia(s) da ouro falharam: {falhas}")


def main():
    con = conectar()
    try:
        criar_esquemas(con)
        carregar_prata(con)
        construir_ouro(con)
        conferir(con)
    finally:
        con.close()


if __name__ == "__main__":
    config.configurar_log()
    main()
