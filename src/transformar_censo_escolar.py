"""
Camada prata do Censo Escolar 2025 (Tabela_Escola).

    python src/transformar_censo_escolar.py
"""
import logging

import pandas as pd

import config
import limpeza

log = logging.getLogger(__name__)

BRONZE = config.BRONZE_CENSO
PRATA = config.PRATA
PADRAO = config.PADRAO_CENSO

CHAVE = ["CO_ENTIDADE"]

COLUNAS_ID = ["CO_ENTIDADE", "CO_MUNICIPIO", "CO_UF"]
TAMANHO_CO_MUNICIPIO = 7

CODIGO_IN_SEM_RESPOSTA = 9
CODIGO_QT_EXTREMO_INEP = 88888

COLUNAS_EXTREMOS = ["QT_SALAS_UTILIZADAS"]

CATEGORIAS_TP = {
    "TP_DEPENDENCIA": {1: "federal", 2: "estadual", 3: "municipal", 4: "privada"},
    "TP_SITUACAO_FUNCIONAMENTO": {
        1: "em atividade", 2: "paralisada",
        3: "extinta (ano do censo)", 4: "extinta em anos anteriores",
    },
    "TP_LOCALIZACAO": {1: "urbana", 2: "rural"},
}

GRUPOS_INFRA = {
    "infra_basica": [
        "IN_AGUA_POTAVEL", "IN_ENERGIA_REDE_PUBLICA", "IN_ESGOTO_REDE_PUBLICA",
        "IN_BANHEIRO", "IN_COZINHA", "IN_REFEITORIO",
    ],
    "infra_espacos_ensino": [
        "IN_BIBLIOTECA_SALA_LEITURA", "IN_LABORATORIO_CIENCIAS",
        "IN_LABORATORIO_INFORMATICA", "IN_QUADRA_ESPORTES", "IN_PARQUE_INFANTIL",
        "IN_SALA_ATENDIMENTO_ESPECIAL", "IN_SALA_PROFESSOR",
    ],
    "infra_acessibilidade": [
        "IN_ACESSIBILIDADE_RAMPAS", "IN_BANHEIRO_PNE", "IN_ACESSIBILIDADE_CORRIMAO",
        "IN_ACESSIBILIDADE_VAO_LIVRE", "IN_ACESSIBILIDADE_PISOS_TATEIS",
    ],
    "infra_tecnologia": [
        "IN_INTERNET_ALUNOS", "IN_BANDA_LARGA", "IN_DESKTOP_ALUNO",
        "IN_COMP_PORTATIL_ALUNO", "IN_TABLET_ALUNO", "IN_EQUIP_MULTIMIDIA",
        "IN_EQUIP_LOUSA_DIGITAL",
    ],
}


def carregar():
    """Acha Tabela_Escola_2025_V2*.csv na extracao mais recente da bronze e o le."""
    pasta = limpeza.mais_recente(BRONZE)
    encontrados = sorted(pasta.rglob(PADRAO))
    if not encontrados:
        raise FileNotFoundError(f"nenhum '{PADRAO}' em {pasta}")
    caminho = encontrados[0]
    df = pd.read_csv(
        caminho, sep=";", encoding="latin-1", low_memory=False,
        dtype={c: str for c in COLUNAS_ID},
    )
    log.info("lido: %s %s", caminho.name, df.shape)
    log.info("colunas IN_*: %d", sum(c.startswith("IN_") for c in df.columns))
    return df, caminho


def padronizar_codigo_municipio(df):
    """Garante que CO_MUNICIPIO tenha 7 digitos, igual ao id_municipio do IDEB."""
    df["CO_MUNICIPIO"] = df["CO_MUNICIPIO"].str.zfill(TAMANHO_CO_MUNICIPIO)
    fora = int((df["CO_MUNICIPIO"].str.len() != TAMANHO_CO_MUNICIPIO).sum())
    nivel = log.warning if fora else log.info
    nivel("CO_MUNICIPIO com tamanho diferente de %d: %d", TAMANHO_CO_MUNICIPIO, fora)
    return df


def tipar_indicadores(df):
    """Converte as colunas IN_* (0 = nao, 1 = sim) para Int8, tratando o
    codigo 9 e qualquer valor inesperado como ausente."""
    colunas = [c for c in df.columns if c.startswith("IN_")]
    n_nove = 0
    n_outros = 0
    for coluna in colunas:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
        nove = df[coluna] == CODIGO_IN_SEM_RESPOSTA
        n_nove += int(nove.sum())
        df[coluna] = df[coluna].mask(nove)
        outros = df[coluna].notna() & ~df[coluna].isin([0, 1])
        n_outros += int(outros.sum())
        df[coluna] = df[coluna].mask(outros).astype("Int8")
    log.info("%d colunas IN_* convertidas; codigo 9 -> ausente: %d; "
             "outros fora de 0/1 -> ausente: %d", len(colunas), n_nove, n_outros)
    return df, len(colunas), n_nove, n_outros


def tratar_sentinela_qt(df):
    """Nas colunas QT_*, converte o 88888 em ausente e marca em qt_extremo_inep
    as escolas que tinham esse codigo."""
    colunas = [c for c in df.columns if c.startswith("QT_")]
    marcada = pd.Series(False, index=df.index)
    afetadas, total = 0, 0
    for coluna in colunas:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
        alvo = df[coluna] == CODIGO_QT_EXTREMO_INEP
        if n := int(alvo.sum()):
            df[coluna] = df[coluna].mask(alvo)
            marcada |= alvo
            afetadas += 1
            total += n
    df["qt_extremo_inep"] = marcada
    log.info("QT_*: %d valores %d -> ausente em %d de %d colunas; "
             "%d escolas marcadas em qt_extremo_inep",
             total, CODIGO_QT_EXTREMO_INEP, afetadas, len(colunas), int(marcada.sum()))
    return df, afetadas, total, int(marcada.sum())


def remover_coluna_constante(df, coluna="NU_ANO_CENSO", valor=2025):
    """Remove a coluna so depois de confirmar que e constante e igual ao esperado."""
    if coluna not in df.columns:
        return df, False
    unicos = df[coluna].dropna().unique()
    if len(unicos) == 1 and int(unicos[0]) == valor:
        log.info("%s constante (%s): removida", coluna, valor)
        return df.drop(columns=coluna), True
    log.warning("%s nao e constante (%s), mantida", coluna, unicos[:5])
    return df, False


def tipar_categorias(df):
    """TP_DEPENDENCIA, TP_SITUACAO_FUNCIONAMENTO e TP_LOCALIZACAO: de codigos
    numericos para categorias com rotulo legivel."""
    total_fora = 0
    for coluna, mapa in CATEGORIAS_TP.items():
        df, fora = limpeza.tipar_categoria(
            df, coluna, list(mapa.values()), mapa=mapa)
        total_fora += fora
    return df, total_fora


def derivar_infraestrutura(df):
    """4 fracoes por bloco e o indice_infraestrutura geral."""
    todas = [c for cols in GRUPOS_INFRA.values() for c in cols]
    assert len(todas) == len(set(todas)), "item repetido entre blocos"
    for bloco, colunas in GRUPOS_INFRA.items():
        df[bloco] = limpeza.proporcao_presente(df, colunas)
    df["indice_infraestrutura"] = limpeza.proporcao_presente(df, todas)
    ativas = df["TP_SITUACAO_FUNCIONAMENTO"] == "em atividade"
    log.info("indice_infraestrutura: %d itens em %d blocos", len(todas), len(GRUPOS_INFRA))

    sem_indice = int(df.loc[ativas, "indice_infraestrutura"].isna().sum())
    nivel = log.warning if sem_indice else log.info
    nivel("escolas em atividade sem indice (ausente): %d", sem_indice)
    log.info("sem indice fora de atividade: %d de %d",
             int(df.loc[~ativas, "indice_infraestrutura"].isna().sum()),
             int((~ativas).sum()))
    log.info("indice_infraestrutura (em atividade):\n%s",
             df.loc[ativas, "indice_infraestrutura"].describe().round(3).to_string())
    return df, len(todas)


def salvar(df):
    """Parquet preserva Int8, categorias e booleanos."""
    PRATA.mkdir(parents=True, exist_ok=True)
    destino = PRATA / "censo_escolas.parquet"
    df.to_parquet(destino, index=False)
    log.info("salvo em: %s %s", destino, df.shape)
    return destino


def main():
    df, origem = carregar()
    antes = len(df)

    df = limpeza.tirar_espacos(df)
    df = padronizar_codigo_municipio(df)
    df, repetidas = limpeza.conferir_chave(df, CHAVE, mostrar=["NO_ENTIDADE"])
    df, n_indicadores, n_nove, n_outros = tipar_indicadores(df)
    df, qt_afetadas, qt_sentinelas, qt_escolas = tratar_sentinela_qt(df)
    df, removeu_ano = remover_coluna_constante(df)

    decisoes = [
        "espacos removidos de nomes de coluna e de texto",
        "codigos (CO_ENTIDADE, CO_MUNICIPIO, CO_UF) lidos como texto; "
        "CO_MUNICIPIO com 7 digitos",
        f"chave {CHAVE}: {repetidas} repeticoes removidas",
        f"{n_indicadores} colunas IN_* convertidas para Int8; codigo 9 "
        f"(nao informado) virou ausente: {n_nove}; outros fora de 0/1: {n_outros}",
        f"QT_*: codigo {CODIGO_QT_EXTREMO_INEP} (extremo marcado pelo INEP) virou "
        f"ausente: {qt_sentinelas} valores em {qt_afetadas} colunas; "
        f"{qt_escolas} escolas marcadas em qt_extremo_inep",
        "ausentes de colunas condicionais mantidos (nao se aplica, nao e erro)",
    ]
    if removeu_ano:
        decisoes.append("NU_ANO_CENSO removida: constante (2025) em todas as linhas")

    for coluna in COLUNAS_EXTREMOS:
        if coluna not in df.columns:
            log.warning("coluna nao encontrada: %s", coluna)
            continue
        df, n_iqr, _ = limpeza.marcar_extremos(df, coluna)
        if n_iqr is not None:
            decisoes.append(f"{coluna}: {n_iqr} extremos marcados por IQR, mantidos")

    df, fora_tp = tipar_categorias(df)
    decisoes.append(
        f"{list(CATEGORIAS_TP)} tipadas como categoria com rotulos do dicionario "
        f"do INEP ({fora_tp} valores fora do dicionario viraram ausentes)")

    df, n_itens = derivar_infraestrutura(df)
    decisoes.append(
        f"atributo derivado indice_infraestrutura: fracao de {n_itens} itens "
        f"IN_* presentes, em {len(GRUPOS_INFRA)} blocos ({list(GRUPOS_INFRA)})")

    destino = salvar(df)
    limpeza.registrar(PRATA, {
        "origem": origem.name,
        "arquivo_prata": destino.name,
        "linhas_antes": antes,
        "linhas_depois": len(df),
        "decisoes": decisoes,
    })


if __name__ == "__main__":
    config.configurar_log()
    main()
