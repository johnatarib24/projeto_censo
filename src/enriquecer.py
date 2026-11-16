"""
Enriquecimento (camada prata): IDEB (escola) + Censo Escolar (escola).

Roda a partir da raiz do projeto:
    python src/enriquecer.py

Saida: dados/prata/ideb_censo_enriquecido.parquet
Grao do resultado: uma linha por escola do IDEB (anos iniciais, 2025).
"""
from pathlib import Path

import pandas as pd

import limpeza

PRATA = Path("dados/prata")

# Reduzir antes de juntar: so o que o Censo acrescenta ao IDEB.
COLUNAS_CENSO = [
    "CO_ENTIDADE", "CO_MUNICIPIO", "SG_UF",
    "TP_DEPENDENCIA", "TP_SITUACAO_FUNCIONAMENTO", "TP_LOCALIZACAO",
    "indice_infraestrutura",
    "infra_basica", "infra_espacos_ensino", "infra_acessibilidade", "infra_tecnologia",
    "qt_extremo_inep",
    "QT_MAT_FUND_AI",  # matriculas dos anos iniciais (peso da media ponderada); confira o nome
]


# ------------------------------------------------------------ passo 1
def conferir_chaves(esq, dir_, rotulo):
    """Previsao do que a juncao vai fazer. Anote antes de juntar."""
    esq, dir_ = set(esq.dropna()), set(dir_.dropna())
    print(f"[{rotulo}] so na esquerda: {len(esq - dir_)} | "
          f"so na direita: {len(dir_ - esq)} | nos dois: {len(esq & dir_)}")


# ------------------------------------------------------------ passo 2
def juntar_censo(ideb, censo):
    return ideb.merge(
        censo,
        left_on="id_escola",
        right_on="CO_ENTIDADE",
        how="left",
        validate="one_to_one",
    )


# ------------------------------------------------------------ passo 3
def validar(esquerda, resultado, coluna_marcadora, rotulo):
    """Conta antes/depois e devolve as linhas que nao casaram."""
    sem_par = resultado[coluna_marcadora].isna()
    print(f"[{rotulo}] esquerda: {len(esquerda)} | resultado: {len(resultado)} "
          f"| sem par: {int(sem_par.sum())}")
    if len(resultado) != len(esquerda):
        raise ValueError(f"{rotulo}: o numero de linhas mudou (o grao foi alterado)")
    return resultado[sem_par]


# ------------------------------------------------------------ passo 4
def descrever_nao_casadas(sem_censo):
    """Os grupos de quem nao casou: sao o achado, nao o resto."""
    print("\n-- IDEB sem par no Censo --")
    print("por rede:\n", sem_censo["rede"].value_counts(dropna=False).to_string())
    print("com IDEB calculado:", int(sem_censo["ideb_disponivel"].sum()),
          "| sem IDEB:", int((~sem_censo["ideb_disponivel"]).sum()))
    print("por UF (top 5):\n",
          sem_censo["sigla_uf"].value_counts().head(5).to_string())


def conferir_consistencia(df):
    """Casos em que as fontes casaram pela escola mas discordam em outro campo."""
    casou = df["CO_ENTIDADE"].notna()
    uf_dif = casou & (df["sigla_uf"] != df["SG_UF"])
    mun_dif = casou & (df["id_municipio"] != df["CO_MUNICIPIO"])
    rede_dif = casou & (df["rede"].astype("string") != df["TP_DEPENDENCIA"].astype("string"))
    print("\n-- discordancias entre fontes --")
    print("UF (IDEB x Censo):", int(uf_dif.sum()))
    print("municipio (IDEB x Censo):", int(mun_dif.sum()))
    print("rede (IDEB x Censo):", int(rede_dif.sum()))
    return int(uf_dif.sum()), int(mun_dif.sum()), int(rede_dif.sum())


# ------------------------------------------------------------ passo 5
def derivar_pos_juncao(df):
    """Atributos que so existem depois da juncao."""
    # 1) filtro de analise: as mesmas escolas nos dois lados (decisao do README)
    df["na_analise"] = (
        (df["rede"] == "municipal")
        & (df["TP_DEPENDENCIA"] == "municipal")
        & (df["TP_SITUACAO_FUNCIONAMENTO"] == "em atividade")
        & df["ideb_disponivel"]
        & df["indice_infraestrutura"].notna()
    )
    print("\nescolas em na_analise:", int(df["na_analise"].sum()))

    # 2) posicao da escola dentro da sua UF, so entre as escolas da analise
    base = df[df["na_analise"]]
    med_ideb = base.groupby("sigla_uf")["ideb"].median()
    med_infra = base.groupby("sigla_uf")["indice_infraestrutura"].median()
    df["ideb_dif_mediana_uf"] = df["ideb"] - df["sigla_uf"].map(med_ideb)
    # so existe depois da juncao: o indice vem do Censo
    df["infra_dif_mediana_uf"] = df["indice_infraestrutura"] - df["sigla_uf"].map(med_infra)
    return df


def main():
    ideb = pd.read_parquet(PRATA / "ideb_escolas.parquet")
    censo = pd.read_parquet(PRATA / "censo_escolas.parquet")

    faltando = [c for c in COLUNAS_CENSO if c not in censo.columns]
    if faltando:
        print("aviso: colunas do Censo nao encontradas, ignoradas:", faltando)
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
    print("salvo em:", destino, df.shape)

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
    main()