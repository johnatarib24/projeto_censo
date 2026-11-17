"""
Enriquecimento (camada prata): IDEB (escola) + Censo Escolar (escola).

    python src/enriquecer.py

Saida: dados/prata/ideb_censo_enriquecido.parquet
Grao do resultado: uma linha por escola do IDEB (anos iniciais, 2025).
"""
import logging

import pandas as pd

import config
import limpeza

log = logging.getLogger(__name__)

PRATA = config.PRATA

# Reduzir antes de juntar: so o que o Censo acrescenta ao IDEB.
COLUNAS_CENSO = [
    "CO_ENTIDADE", "CO_MUNICIPIO", "SG_UF",
    "TP_DEPENDENCIA", "TP_SITUACAO_FUNCIONAMENTO", "TP_LOCALIZACAO",
    "indice_infraestrutura",
    "infra_basica", "infra_espacos_ensino", "infra_acessibilidade", "infra_tecnologia",
    "qt_extremo_inep",
]


def conferir_chaves(esq, dir_, rotulo):
    """Previsao do que a juncao vai fazer."""
    esq, dir_ = set(esq.dropna()), set(dir_.dropna())
    log.info("[%s] so na esquerda: %d | so na direita: %d | nos dois: %d",
             rotulo, len(esq - dir_), len(dir_ - esq), len(esq & dir_))


def juntar_censo(ideb, censo):
    df = ideb.merge(
        censo,
        left_on="id_escola",
        right_on="CO_ENTIDADE",
        how="left",
        validate="one_to_one",
    )
    # o left insere ausentes numa coluna booleana e ela vira object
    df["qt_extremo_inep"] = df["qt_extremo_inep"].astype("boolean")
    return df


def validar(esquerda, resultado, coluna_marcadora, rotulo):
    """Conta antes/depois e devolve as linhas que nao casaram."""
    sem_par = resultado[coluna_marcadora].isna()
    log.info("[%s] esquerda: %d | resultado: %d | sem par: %d",
             rotulo, len(esquerda), len(resultado), int(sem_par.sum()))
    if len(resultado) != len(esquerda):
        raise ValueError(f"{rotulo}: o numero de linhas mudou (o grao foi alterado)")
    return resultado[sem_par]


def descrever_nao_casadas(sem_censo):
    """Os grupos de quem nao casou: sao o achado, nao o resto."""
    log.info("IDEB sem par no Censo, por rede:\n%s",
             sem_censo["rede"].value_counts(dropna=False).to_string())
    log.info("IDEB sem par no Censo: com IDEB calculado %d | sem IDEB %d",
             int(sem_censo["ideb_disponivel"].sum()),
             int((~sem_censo["ideb_disponivel"]).sum()))
    log.info("IDEB sem par no Censo, por UF (top 5):\n%s",
             sem_censo["sigla_uf"].value_counts().head(5).to_string())


def conferir_consistencia(df):
    """Casos em que as fontes casaram pela escola mas discordam em outro campo."""
    casou = df["CO_ENTIDADE"].notna()
    uf_dif = int((casou & (df["sigla_uf"] != df["SG_UF"])).sum())
    mun_dif = int((casou & (df["id_municipio"] != df["CO_MUNICIPIO"])).sum())
    rede_dif = int((casou & (df["rede"].astype("string")
                             != df["TP_DEPENDENCIA"].astype("string"))).sum())
    log.info("discordancias entre fontes: UF %d | municipio %d | rede %d",
             uf_dif, mun_dif, rede_dif)
    if uf_dif or mun_dif:
        log.warning("UF ou municipio discordam entre IDEB e Censo")
    return uf_dif, mun_dif, rede_dif


def derivar_pos_juncao(df):
    """Atributos que so existem depois da juncao."""
    df["na_analise"] = (
        (df["rede"] == "municipal")
        & (df["TP_DEPENDENCIA"] == "municipal")
        & (df["TP_SITUACAO_FUNCIONAMENTO"] == "em atividade")
        & df["ideb_disponivel"]
        & df["indice_infraestrutura"].notna()
    )
    log.info("escolas em na_analise: %d", int(df["na_analise"].sum()))

    base = df[df["na_analise"]]
    med_ideb = base.groupby("sigla_uf")["ideb"].median()
    med_infra = base.groupby("sigla_uf")["indice_infraestrutura"].median()
    df["ideb_dif_mediana_uf"] = df["ideb"] - df["sigla_uf"].map(med_ideb)
    df["infra_dif_mediana_uf"] = df["indice_infraestrutura"] - df["sigla_uf"].map(med_infra)

    sem_uf = int((df["ideb"].notna() & df["ideb_dif_mediana_uf"].isna()).sum())
    if sem_uf:
        log.warning("%d escolas com IDEB sem diferenca para a mediana da UF "
                    "(UF sem escola municipal, como o DF)", sem_uf)
    return df


def main():
    ideb = pd.read_parquet(PRATA / "ideb_escolas.parquet")
    censo = pd.read_parquet(PRATA / "censo_escolas.parquet")

    faltando = [c for c in COLUNAS_CENSO if c not in censo.columns]
    if faltando:
        log.warning("colunas do Censo nao encontradas, ignoradas: %s", faltando)
    censo = censo[[c for c in COLUNAS_CENSO if c in censo.columns]]

    n_ideb = len(ideb)

    conferir_chaves(ideb["id_escola"], censo["CO_ENTIDADE"], "escola")
    df = juntar_censo(ideb, censo)
    sem_censo = validar(ideb, df, "CO_ENTIDADE", "ideb+censo")
    descrever_nao_casadas(sem_censo)

    n_uf, n_mun, n_rede = conferir_consistencia(df)

    df = derivar_pos_juncao(df)

    destino = PRATA / "ideb_censo_enriquecido.parquet"
    df.to_parquet(destino, index=False)
    log.info("salvo em: %s %s", destino, df.shape)

    limpeza.registrar(PRATA, {
        "origem": "ideb_escolas.parquet + censo_escolas.parquet",
        "arquivo_prata": destino.name,
        "linhas_antes": n_ideb,
        "linhas_depois": len(df),
        "decisoes": [
            "juncao left a partir do IDEB: id_escola = CO_ENTIDADE, validate=one_to_one",
            f"IDEB sem par no Censo: {len(sem_censo)}; "
            f"destes, sem IDEB calculado: {int((~sem_censo['ideb_disponivel']).sum())}",
            f"discordancias entre fontes: UF {n_uf}, municipio {n_mun}, rede {n_rede}",
            f"coluna na_analise (municipal, em atividade, com IDEB e indice): "
            f"{int(df['na_analise'].sum())} escolas",
            "atributos derivados ideb_dif_mediana_uf e infra_dif_mediana_uf: "
            "diferenca para a mediana da UF entre escolas de na_analise",
        ],
    })


if __name__ == "__main__":
    config.configurar_log()
    main()
