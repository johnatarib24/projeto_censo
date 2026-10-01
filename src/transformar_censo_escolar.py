"""
Camada prata do Censo Escolar 2025 (Tabela_Escola).

    python src/transformar_censo_escolar.py
"""
from pathlib import Path

import pandas as pd

import limpeza

BRONZE = Path("dados/bronze/microdados_censo_escolar")
PRATA = Path("dados/prata")
PADRAO = "Tabela_Escola_2025_V2*.csv"

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


def carregar():                                        #Acha Tabela_Escola_2025_V2*.csv na extração mais recente da Bronze e o lê.
    pasta = limpeza.mais_recente(BRONZE)
    encontrados = sorted(pasta.rglob(PADRAO))
    if not encontrados:
        raise FileNotFoundError(f"nenhum '{PADRAO}' em {pasta}")
    caminho = encontrados[0]
    df = pd.read_csv(
        caminho, sep=";", encoding="latin-1", low_memory=False,
        dtype={c: str for c in COLUNAS_ID},
    )
    print("lido:", caminho.name, df.shape)
    print("colunas IN_*:", sum(c.startswith("IN_") for c in df.columns))
    return df, caminho


def padronizar_codigo_municipio(df):                       #Garante que CO_MUNICIPIO tenha 7 dígitos, igual ao id_municipio do IDEB

    df["CO_MUNICIPIO"] = df["CO_MUNICIPIO"].str.zfill(TAMANHO_CO_MUNICIPIO)
    fora = int((df["CO_MUNICIPIO"].str.len() != TAMANHO_CO_MUNICIPIO).sum())
    print(f"CO_MUNICIPIO com tamanho diferente de {TAMANHO_CO_MUNICIPIO}:", fora)
    return df


def tipar_indicadores(df):                                          #Converte as 213 colunas IN_* (0 = não, 1 = sim) para o tipo 
    colunas = [c for c in df.columns if c.startswith("IN_")]        #Int8, tratando o código 9 e qualquer valor inesperado como 
    n_nove = 0                                                      #ausente.
    n_outros = 0
    for coluna in colunas:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
        nove = df[coluna] == CODIGO_IN_SEM_RESPOSTA
        n_nove += int(nove.sum())
        df[coluna] = df[coluna].mask(nove)
        outros = df[coluna].notna() & ~df[coluna].isin([0, 1])
        n_outros += int(outros.sum())
        df[coluna] = df[coluna].mask(outros).astype("Int8")
    print(f"{len(colunas)} colunas IN_* convertidas; "
          f"codigo 9 -> ausente: {n_nove}; outros fora de 0/1 -> ausente: {n_outros}")
    return df, len(colunas), n_nove, n_outros


def tratar_sentinela_qt(df):                                        #Nas colunas QT_* (contagens), converte o 88888 em ausente e 
    colunas = [c for c in df.columns if c.startswith("QT_")]        #marca em uma coluna única (qt_extremo_inep) quais escolas 
    marcada = pd.Series(False, index=df.index)                      #tinham esse código.
    afetadas, total = 0, 0
    for coluna in colunas:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
        alvo = df[coluna] == CODIGO_QT_EXTREMO_INEP

        if n:= int(alvo.sum()):
            df[coluna] = df[coluna].mask(alvo)
            marcada |= alvo
            afetadas += 1
            total += n
    df["qt_extremo_inep"] = marcada
    print(f"QT_*: {total} valores {CODIGO_QT_EXTREMO_INEP} -> ausente em "
          f"{afetadas} de {len(colunas)} colunas; "
          f"{int(marcada.sum())} escolas marcadas em qt_extremo_inep")
    return df, afetadas, total, int(marcada.sum())


def remover_coluna_constante(df, coluna="NU_ANO_CENSO", valor=2025):    #Remove a coluna NU_ANO_CENSO, mas só depois de confirmar 
    if coluna not in df.columns:                                        #que ela é constante e igual ao esperado
        return df, False
    unicos = df[coluna].dropna().unique()
    if len(unicos) == 1 and int(unicos[0]) == valor:
        print(f"{coluna} constante ({valor}): removida")
        return df.drop(columns=coluna), True
    print(f"aviso: {coluna} nao e constante ({unicos[:5]}), mantida")
    return df, False


def tipar_categorias(df):                                              #Converte TP_DEPENDENCIA, TP_SITUACAO_FUNCIONAMENTO e 
    total_fora = 0                                                     #TP_LOCALIZACAO de códigos numéricos para categorias com 
    for coluna, mapa in CATEGORIAS_TP.items():                         #rótulo legível.
        df, fora = limpeza.tipar_categoria(
            df, coluna, list(mapa.values()), mapa=mapa)
        total_fora += fora
    return df, total_fora


def derivar_infraestrutura(df):                                            #Cria 5 colunas novas: as 4 frações por bloco 
    todas = [c for cols in GRUPOS_INFRA.values() for c in cols]            #(infra_basica, infra_espacos_ensino, 
    assert len(todas) == len(set(todas)), "item repetido entre blocos"     #infra_acessibilidade, infra_tecnologia) e o 
    for bloco, colunas in GRUPOS_INFRA.items():                            #indice_infraestrutura geral.
        df[bloco] = limpeza.proporcao_presente(df, colunas)
    df["indice_infraestrutura"] = limpeza.proporcao_presente(df, todas)
    ativas = df["TP_SITUACAO_FUNCIONAMENTO"] == "em atividade"
    print(f"indice_infraestrutura: {len(todas)} itens em {len(GRUPOS_INFRA)} blocos")
    print("  escolas em atividade sem indice (ausente):",
          int(df.loc[ativas, "indice_infraestrutura"].isna().sum()))
    print("  sem indice fora de atividade:",
          int(df.loc[~ativas, "indice_infraestrutura"].isna().sum()),
          "de", int((~ativas).sum()))
    print(df.loc[ativas, "indice_infraestrutura"].describe().round(3).to_string())
    return df, len(todas)


def salvar(df):                                                     #Grava o resultado em Parquet, que preserva Int8, categorias e 
    PRATA.mkdir(parents=True, exist_ok=True)                        #booleanos, e devolve o caminho para a proveniência.
    destino = PRATA / "censo_escolas.parquet"
    df.to_parquet(destino, index=False)
    print("salvo em:", destino, df.shape)
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
            print("aviso: coluna nao encontrada:", coluna)
            continue
        df, n_iqr, _ = limpeza.marcar_extremos(df, coluna)
        if n_iqr is not None:
            decisoes.append(f"{coluna}: {n_iqr} extremos marcados por IQR, mantidos")

    # --- aula 6: tipos e atributos derivados
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
    main()