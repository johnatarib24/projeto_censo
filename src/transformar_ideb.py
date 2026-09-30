"""
Camada prata do IDEB (Base dos Dados: br_inep_ideb.escola).

    python src/transformar_ideb.py

Le a extracao mais recente da bronze, aplica as decisoes de tratamento e grava
dados/prata/ideb_escolas.parquet. A bronze nunca e alterada.
"""
import json
from datetime import datetime
from pathlib import Path

import pandas as pd

BRONZE = Path("dados/bronze/ideb_anos_iniciais_escolas")
PRATA = Path("dados/prata")
FORMATO_PASTA = "%d%m%Y"

# Recorte da pergunta norteadora (ver README)
ANO = 2025
ANOS_ESCOLARES = "iniciais (1-5)"

# O que e uma linha? Uma escola. Depois do recorte (ano 2025, anos iniciais)
# so sobra uma linha por escola: id_escola e unico (66.138 de 66.138).
CHAVE = ["id_escola"]

COLUNAS_TEXTO_ID = {"id_municipio": str, "id_escola": str}
NUMERICAS = [
    "taxa_aprovacao",
    "indicador_rendimento",
    "nota_saeb_matematica",
    "nota_saeb_lingua_portuguesa",
    "nota_saeb_media_padronizada",
    "ideb",
    "projecao",
]

# Faixas validas vindas do dominio (nao da estatistica). So entra aqui o que
# eu consigo justificar: IDEB vai de 0 a 10 e aprovacao e um percentual.
FAIXAS_VALIDAS = {
    "ideb": (0, 10),
    "taxa_aprovacao": (0, 100),
}

# Colunas em que vale marcar valores extremos (ajuste apos ler o relatorio)
COLUNAS_EXTREMOS = ["ideb", "taxa_aprovacao"]


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
    arquivos = sorted(pasta.glob("*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"nenhum CSV em {pasta}")
    caminho = arquivos[-1]
    # ids como texto: codigo de municipio/escola nao e numero
    df = pd.read_csv(caminho, dtype=COLUNAS_TEXTO_ID, low_memory=False)
    print("lido:", caminho, df.shape)
    print(df.columns.tolist())
    print(df.isna().sum())
    return df, caminho


def tirar_espacos(df):
    df.columns = df.columns.str.strip()
    for coluna in df.select_dtypes(include=["object", "string"]):
        df[coluna] = df[coluna].str.strip()
    return df


def filtrar_recorte(df):
    """Nao e limpeza de erro: e o recorte da pergunta (ano e etapa)."""
    antes = len(df)
    mascara = (df["ano"] == ANO) & (df["anos_escolares"] == ANOS_ESCOLARES)
    if not mascara.any():
        print("valores de anos_escolares:", df["anos_escolares"].unique())
        raise ValueError("o recorte nao casou com nenhuma linha")
    print(f"recorte ano={ANO}, anos_escolares='{ANOS_ESCOLARES}': "
          f"{mascara.sum()} de {antes} linhas")
    return df[mascara].copy(), antes - int(mascara.sum())


def converter_tipos(df):
    total_novos_ausentes = 0
    for coluna in NUMERICAS:
        if coluna not in df.columns:
            print("aviso: coluna ausente:", coluna)
            continue
        antes = df[coluna].isna().sum()
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
        novos = int(df[coluna].isna().sum() - antes)
        print(f"{coluna}: {novos} valores viraram ausentes na conversao")
        total_novos_ausentes += novos
    return df, total_novos_ausentes


def conferir_chave(df, chave=CHAVE):
    repetidas = int(df.duplicated(subset=chave).sum())
    print("chaves repetidas:", repetidas)
    if repetidas:
        print(df[df.duplicated(subset=chave, keep=False)]
              .sort_values(chave).head(20))
    identicas = int(df.duplicated().sum())
    print("linhas totalmente identicas:", identicas)
    return df.drop_duplicates(subset=chave).copy(), repetidas


def remover_erros(df, coluna, minimo, maximo):
    """Remove so o que esta fora da faixa do dominio. Ausente nao e erro."""
    invalido = df[coluna].notna() & ~df[coluna].between(minimo, maximo)
    print(f"{coluna} fora de [{minimo}, {maximo}] removidas:", int(invalido.sum()))
    return df[~invalido].copy(), int(invalido.sum())


def limites_iqr(serie):
    q1, q3 = serie.quantile(0.25), serie.quantile(0.75)
    iqr = q3 - q1
    return q1 - 1.5 * iqr, q3 + 1.5 * iqr


def marcar_extremos(df, coluna):
    baixo, alto = limites_iqr(df[coluna].dropna())
    df[coluna + "_extremo"] = (df[coluna] < baixo) | (df[coluna] > alto)
    z = (df[coluna] - df[coluna].mean()) / df[coluna].std()
    df[coluna + "_z"] = z.abs() > 3
    n_iqr, n_z = int(df[coluna + "_extremo"].sum()), int(df[coluna + "_z"].sum())
    print(f"{coluna}: IQR marcou {n_iqr}, z-score marcou {n_z} "
          f"(limites IQR: {baixo:.2f} a {alto:.2f})")
    return df, n_iqr, n_z


def sinalizar_ausentes(df):
    """Ausente de ideb = escola sem resultado calculado (sigilo estatistico).
    Nao se remove: sinaliza, porque o vazio tem significado."""
    df["ideb_disponivel"] = df["ideb"].notna()
    print("escolas com IDEB:", int(df["ideb_disponivel"].sum()),
          "| sem IDEB:", int((~df["ideb_disponivel"]).sum()))
    return df


def salvar(df):
    PRATA.mkdir(parents=True, exist_ok=True)
    destino = PRATA / "ideb_escolas.parquet"
    df.to_parquet(destino, index=False)
    print("salvo em:", destino, df.shape)
    return destino


def registrar(origem, destino, antes, depois, decisoes):
    info = {
        "origem": str(origem),
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
    df, fora_recorte = filtrar_recorte(df)
    df, novos_ausentes = converter_tipos(df)
    df, repetidas = conferir_chave(df)

    removidas = 0
    for coluna, (minimo, maximo) in FAIXAS_VALIDAS.items():
        df, n = remover_erros(df, coluna, minimo, maximo)
        removidas += n

    decisoes = [
        "espacos removidos de nomes de coluna e de texto",
        f"recorte ano={ANO} e anos_escolares='{ANOS_ESCOLARES}': "
        f"{fora_recorte} linhas fora do recorte",
        f"colunas numericas convertidas: {novos_ausentes} valores viraram ausentes",
        f"chave {CHAVE}: {repetidas} repeticoes removidas",
        f"valores fora da faixa do dominio removidos: {removidas}",
    ]

    for coluna in COLUNAS_EXTREMOS:
        df, n_iqr, n_z = marcar_extremos(df, coluna)
        decisoes.append(f"{coluna}: extremos marcados (IQR={n_iqr}, z={n_z}), mantidos")

    df = sinalizar_ausentes(df)
    decisoes.append("ausentes de ideb mantidos e sinalizados em ideb_disponivel")

    destino = salvar(df)
    registrar(origem, destino, antes, len(df), decisoes)


if __name__ == "__main__":
    main()