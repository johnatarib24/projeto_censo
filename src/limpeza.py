from datetime import datetime
from pathlib import Path

import pandas as pd

FORMATO_PASTA = "%d%m%Y"


# ---------------------------------------------------------------- bronze
def mais_recente(bronze: Path) -> Path:
    """Pasta datada (DDMMYYYY) mais recente dentro de uma pasta da bronze."""
    candidatas = []
    for p in Path(bronze).iterdir():
        if not p.is_dir():
            continue
        try:
            candidatas.append((datetime.strptime(p.name, FORMATO_PASTA), p))
        except ValueError:
            continue
    if not candidatas:
        raise FileNotFoundError(f"nenhuma pasta datada em {bronze}")
    return max(candidatas, key=lambda item: item[0])[1]


# ----------------------------------------------------------------- texto
def tirar_espacos(df):
    """Espacos nas pontas, em nomes de coluna e em colunas de texto."""
    df.columns = df.columns.str.strip()
    for coluna in df.select_dtypes(include=["object", "string"]):
        df[coluna] = df[coluna].str.strip()
    return df


def chave_texto(serie):
    """Versao comparavel de um texto: sem acento, sem espaco sobrando e em
    minuscula."""
    s = serie.str.strip().str.lower()
    s = s.str.normalize("NFKD")
    s = s.str.encode("ascii", errors="ignore")
    return s.str.decode("utf-8")


def aplicar_mapa(serie, mapa):
    return serie.replace(mapa)


# ------------------------------------------------------------------ tipos
def tipar_categoria(df, coluna, categorias, nova=None, ordenada=False, mapa=None):

    antes = int(df[coluna].isna().sum())  # ausentes que ja existiam, antes do mapa
    origem = df[coluna].map(mapa) if mapa else df[coluna]
    tipada = pd.Categorical(origem, categories=list(categorias), ordered=ordenada)
    fora = int(pd.isna(tipada).sum()) - antes
    df[nova or coluna] = tipada
    print(f"{nova or coluna}: {fora} valores fora das categorias viraram ausentes")
    return df, fora


# ------------------------------------------------------- chave e extremos
def conferir_chave(df, chave, mostrar=()):
    """Conta repeticoes da chave, mostra exemplos e remove as repetidas."""
    repetidas = int(df.duplicated(subset=chave).sum())
    print("chaves repetidas:", repetidas)
    if repetidas:
        ver = list(chave) + [c for c in mostrar if c in df.columns]
        print(df[df.duplicated(subset=chave, keep=False)]
              .sort_values(chave).head(20)[ver])
    return df.drop_duplicates(subset=chave).copy(), repetidas


def remover_fora_da_faixa(df, coluna, minimo, maximo):
    """Remove so o que esta fora da faixa do dominio. Ausente nao e erro."""
    invalido = df[coluna].notna() & ~df[coluna].between(minimo, maximo)
    print(f"{coluna} fora de [{minimo}, {maximo}] removidas:", int(invalido.sum()))
    return df[~invalido].copy(), int(invalido.sum())


def limites_iqr(serie):
    q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def marcar_extremos(df, coluna, com_z=False):

    serie = pd.to_numeric(df[coluna], errors="coerce")
    baixo, alto = limites_iqr(serie.dropna())
    n_iqr = n_z = None
    if alto == baixo:
        print(f"{coluna}: IQR = 0, extremos por IQR nao marcados")
    else:
        df[coluna + "_extremo"] = (serie < baixo) | (serie > alto)
        n_iqr = int(df[coluna + "_extremo"].sum())
        print(f"{coluna}: IQR marcou {n_iqr} (limites {baixo:.2f} a {alto:.2f})")
    if com_z:
        z = (serie - serie.mean()) / serie.std()
        df[coluna + "_z"] = z.abs() > 3
        n_z = int(df[coluna + "_z"].sum())
        print(f"{coluna}: z-score marcou {n_z}")
    return df, n_iqr, n_z


# ------------------------------------------------------ atributos derivados
def proporcao_presente(df, colunas):
    """Fracao (0 a 1) das colunas 0/1 que valem 1, por linha. Ausente nao
    conta nem a favor nem contra; se todas forem ausentes, o resultado e
    ausente. Exige que todas as colunas existam."""

    if faltando:= [c for c in colunas if c not in df.columns]:
        raise KeyError(f"colunas inexistentes: {faltando}")
    return df[list(colunas)].astype("float64").mean(axis=1)


# ------------------------------------------------------------ persistencia
def registrar(pasta_prata, info):
    """Acrescenta uma linha em proveniencia.jsonl da prata."""
    import json
    pasta_prata = Path(pasta_prata)
    pasta_prata.mkdir(parents=True, exist_ok=True)
    caminho = pasta_prata / "proveniencia.jsonl"
    info = {**info, "transformado_em": datetime.now().isoformat(timespec="seconds")}
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")
    print("proveniencia registrada em:", caminho)