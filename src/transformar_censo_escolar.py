"""
Camada prata do Censo Escolar 2025 (Tabela_Escola).

    python src/transformar_censo_escolar.py

Le a extracao mais recente da bronze, aplica as decisoes de tratamento e grava
dados/prata/censo_escolas.parquet. A bronze nunca e alterada.
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

BRONZE = Path("dados/bronze/microdados_censo_escolar")
PRATA = Path("dados/prata")
FORMATO_PASTA = "%d%m%Y"
PADRAO = "Tabela_Escola_2025_V2*.csv"

# O que e uma linha? Uma escola. CO_ENTIDADE e o codigo unico dela.
CHAVE = ["CO_ENTIDADE"]

# Codigos sao identificadores, nao numeros: sem isso perdem o zero a esquerda
COLUNAS_ID = ["CO_ENTIDADE", "CO_MUNICIPIO", "CO_UF"]
TAMANHO_CO_MUNICIPIO = 7

# Codigos de "sem resposta" do Censo (conferir no dicionario de dados do INEP)
CODIGO_IN_SEM_RESPOSTA = 9
CODIGO_QT_SEM_INFORMACAO = 88888

# Colunas com contagem em que vale marcar extremos. QT_DESKTOP_ALUNO ficou
# de fora: 75% das escolas tem 0 ou poucos, o IQR marcaria 15% como extremo.
COLUNAS_EXTREMOS = ["QT_SALAS_UTILIZADAS"]


def mais_recente(bronze: Path) -> Path:
    candidatas = []
    for p in bronze.iterdir():
        if not p.is_dir():
            continue
        try:
            candidatas.append((datetime.strptime(p.name, FORMATO_PASTA), p))
        except ValueError:
            continue
    if not candidatas:
        raise FileNotFoundError(f"nenhuma pasta datada em {bronze}")
    return max(candidatas, key=lambda item: item[0])[1]


def carregar():
    pasta = mais_recente(BRONZE)
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


def tirar_espacos(df):
    df.columns = df.columns.str.strip()
    for coluna in df.select_dtypes(include=["object", "string"]):
        df[coluna] = df[coluna].str.strip()
    return df


def padronizar_codigo_municipio(df):
    """Mesmo formato do id_municipio do IDEB: 7 digitos, texto."""
    df["CO_MUNICIPIO"] = df["CO_MUNICIPIO"].str.zfill(TAMANHO_CO_MUNICIPIO)
    fora = int((df["CO_MUNICIPIO"].str.len() != TAMANHO_CO_MUNICIPIO).sum())
    print(f"CO_MUNICIPIO com tamanho diferente de {TAMANHO_CO_MUNICIPIO}:", fora)
    return df


def conferir_chave(df, chave=CHAVE):
    repetidas = int(df.duplicated(subset=chave).sum())
    print("chaves repetidas:", repetidas)
    if repetidas:
        print(df[df.duplicated(subset=chave, keep=False)]
              .sort_values(chave).head(20)[chave + ["NO_ENTIDADE"]])
    return df.drop_duplicates(subset=chave).copy(), repetidas


def tipar_indicadores(df):
    """Colunas IN_* sao 0/1. O valor 9 e codigo de 'sem resposta' (nao e
    'sim' nem 'nao'), entao vira ausente. Qualquer outro valor fora de 0/1
    tambem vira ausente, contado. Int8 aceita ausente sem virar zero."""
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
    print(f"{len(colunas)} colunas IN_* convertidas; "
          f"codigo 9 -> ausente: {n_nove}; outros fora de 0/1 -> ausente: {n_outros}")
    return df, len(colunas), n_nove, n_outros


def tratar_sentinela_qt(df):
    """Colunas QT_* usam 88888 como codigo de 'nao informado'. Se ficar,
    vira contagem gigante e destroi media, IQR e z-score."""
    colunas = [c for c in df.columns if c.startswith("QT_")]
    afetadas, total = 0, 0
    for coluna in colunas:
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
        n = int((df[coluna] == CODIGO_QT_SEM_INFORMACAO).sum())
        if n:
            df[coluna] = df[coluna].mask(df[coluna] == CODIGO_QT_SEM_INFORMACAO)
            afetadas += 1
            total += n
    print(f"QT_*: {total} valores {CODIGO_QT_SEM_INFORMACAO} -> ausente "
          f"em {afetadas} de {len(colunas)} colunas")
    return df, afetadas, total


def remover_coluna_constante(df, coluna="NU_ANO_CENSO", valor=2025):
    """Confere antes de apagar: so sai se for constante e igual ao esperado."""
    if coluna not in df.columns:
        return df, False
    unicos = df[coluna].dropna().unique()
    if len(unicos) == 1 and int(unicos[0]) == valor:
        print(f"{coluna} constante ({valor}): removida")
        return df.drop(columns=coluna), True
    print(f"aviso: {coluna} nao e constante ({unicos[:5]}), mantida")
    return df, False


def limites_iqr(serie):
    q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def marcar_extremos(df, coluna):
    """Se o IQR for zero (coluna concentrada em um valor), todo valor
    diferente viraria 'extremo': nesse caso nao se marca."""
    serie = pd.to_numeric(df[coluna], errors="coerce")
    baixo, alto = limites_iqr(serie.dropna())
    if alto == baixo:
        print(f"{coluna}: IQR = 0, extremos nao marcados")
        return df, None
    df[coluna + "_extremo"] = (serie < baixo) | (serie > alto)
    n = int(df[coluna + "_extremo"].sum())
    print(f"{coluna}: IQR marcou {n} (limites {baixo:.2f} a {alto:.2f})")
    return df, n


def salvar(df):
    PRATA.mkdir(parents=True, exist_ok=True)
    destino = PRATA / "censo_escolas.parquet"
    df.to_parquet(destino, index=False)
    print("salvo em:", destino, df.shape)
    return destino


def registrar(origem, destino, antes, depois, decisoes):
    info = {
        "origem": origem.name,
        "arquivo_prata": destino.name,
        "linhas_antes": antes,
        "linhas_depois": depois,
        "decisoes": decisoes,
        "transformado_em": datetime.now().isoformat(timespec="seconds"),
    }
    caminho = PRATA / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")
    print("proveniencia registrada em:", caminho)


def main():
    df, origem = carregar()
    antes = len(df)

    df = tirar_espacos(df)
    df = padronizar_codigo_municipio(df)
    df, repetidas = conferir_chave(df)
    df, n_indicadores, n_nove, n_outros = tipar_indicadores(df)
    df, qt_afetadas, qt_sentinelas = tratar_sentinela_qt(df)
    df, removeu_ano = remover_coluna_constante(df)

    decisoes = [
        "espacos removidos de nomes de coluna e de texto",
        "codigos (CO_ENTIDADE, CO_MUNICIPIO, CO_UF) lidos como texto; "
        "CO_MUNICIPIO com 7 digitos",
        f"chave {CHAVE}: {repetidas} repeticoes removidas",
        f"{n_indicadores} colunas IN_* convertidas para Int8; codigo 9 "
        f"(sem resposta) virou ausente: {n_nove}; outros fora de 0/1: {n_outros}",
        f"QT_*: codigo {CODIGO_QT_SEM_INFORMACAO} (nao informado) virou ausente: "
        f"{qt_sentinelas} valores em {qt_afetadas} colunas",
        "ausentes de colunas condicionais mantidos (nao se aplica, nao e erro)",
    ]
    if removeu_ano:
        decisoes.append("NU_ANO_CENSO removida: constante (2025) em todas as linhas")

    for coluna in COLUNAS_EXTREMOS:
        if coluna not in df.columns:
            print("aviso: coluna nao encontrada:", coluna)
            continue
        df, n = marcar_extremos(df, coluna)
        if n is not None:
            decisoes.append(f"{coluna}: {n} extremos marcados por IQR, mantidos")

    destino = salvar(df)
    registrar(origem, destino, antes, len(df), decisoes)


if __name__ == "__main__":
    main()