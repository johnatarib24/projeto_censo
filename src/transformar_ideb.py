"""
Camada prata do IDEB (Base dos Dados: br_inep_ideb.escola).

    python src/transformar_ideb.py
"""
import logging

import pandas as pd

import config
import limpeza

log = logging.getLogger(__name__)

BRONZE = config.BRONZE_IDEB
PRATA = config.PRATA

ANO = config.ANO
ANOS_ESCOLARES = config.ANOS_ESCOLARES

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

FAIXAS_VALIDAS = {
    "ideb": (0, 10),
    "taxa_aprovacao": (0, 100),
}

COLUNAS_EXTREMOS = ["ideb", "taxa_aprovacao"]

CATEGORIAS_REDE = ["federal", "estadual", "municipal"]


def carregar():
    """Carrega o CSV mais recente da pasta."""
    pasta = limpeza.mais_recente(BRONZE)
    arquivos = sorted(pasta.glob("*.csv"))
    if not arquivos:
        raise FileNotFoundError(f"nenhum CSV em {pasta}")
    caminho = arquivos[-1]
    df = pd.read_csv(caminho, dtype=COLUNAS_TEXTO_ID, low_memory=False)
    log.info("lido: %s %s", caminho, df.shape)
    log.debug("colunas: %s", df.columns.tolist())
    log.debug("ausentes por coluna:\n%s", df.isna().sum().to_string())
    return df, caminho


def filtrar_recorte(df):
    """Filtra a base para so conter o ano e os anos escolares da pergunta."""
    antes = len(df)
    mascara = (df["ano"] == ANO) & (df["anos_escolares"] == ANOS_ESCOLARES)
    if not mascara.any():
        log.error("valores de anos_escolares: %s", df["anos_escolares"].unique())
        raise ValueError("o recorte nao casou com nenhuma linha")
    log.info("recorte ano=%s, anos_escolares='%s': %d de %d linhas",
             ANO, ANOS_ESCOLARES, mascara.sum(), antes)
    return df[mascara].copy(), antes - int(mascara.sum())


def converter_tipos(df):
    """Garante que numeros sejam numeros e conta quantos valores perderam o
    conteudo na conversao."""
    total_novos_ausentes = 0
    for coluna in NUMERICAS:
        if coluna not in df.columns:
            log.warning("coluna ausente: %s", coluna)
            continue
        antes = df[coluna].isna().sum()
        df[coluna] = pd.to_numeric(df[coluna], errors="coerce")
        novos = int(df[coluna].isna().sum() - antes)
        nivel = log.warning if novos else log.info
        nivel("%s: %d valores viraram ausentes na conversao", coluna, novos)
        total_novos_ausentes += novos
    return df, total_novos_ausentes


def sinalizar_ausentes(df):
    """ideb_disponivel: True quando a escola tem IDEB calculado."""
    df["ideb_disponivel"] = df["ideb"].notna()
    log.info("escolas com IDEB: %d | sem IDEB: %d",
             int(df["ideb_disponivel"].sum()), int((~df["ideb_disponivel"]).sum()))
    return df


def salvar(df):
    PRATA.mkdir(parents=True, exist_ok=True)
    destino = PRATA / "ideb_escolas.parquet"
    df.to_parquet(destino, index=False)
    log.info("salvo em: %s %s", destino, df.shape)
    return destino


def main():
    df, origem = carregar()
    antes = len(df)

    df = limpeza.tirar_espacos(df)
    df, fora_recorte = filtrar_recorte(df)
    df, novos_ausentes = converter_tipos(df)
    df, repetidas = limpeza.conferir_chave(df, CHAVE)

    removidas = 0
    for coluna, (minimo, maximo) in FAIXAS_VALIDAS.items():
        df, n = limpeza.remover_fora_da_faixa(df, coluna, minimo, maximo)
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
        df, n_iqr, n_z = limpeza.marcar_extremos(df, coluna, com_z=True)
        decisoes.append(f"{coluna}: extremos marcados (IQR={n_iqr}, z={n_z}), mantidos")

    df = sinalizar_ausentes(df)
    decisoes.append("ausentes de ideb mantidos e sinalizados em ideb_disponivel")

    df, fora_rede = limpeza.tipar_categoria(df, "rede", CATEGORIAS_REDE)
    decisoes.append(f"rede tipada como categoria {CATEGORIAS_REDE}: "
                    f"{fora_rede} valores fora da lista viraram ausentes")

    destino = salvar(df)
    limpeza.registrar(PRATA, {
        "origem": origem.relative_to(config.RAIZ).as_posix(),
        "arquivo_prata": destino.name,
        "linhas_antes": antes,
        "linhas_depois": len(df),
        "decisoes": decisoes,
    })


if __name__ == "__main__":
    config.configurar_log()
    main()
