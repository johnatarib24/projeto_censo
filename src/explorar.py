"""
Perfilamento das fontes da bronze (gera HTML em relatorios/).

    python src/explorar.py
"""
import logging
from pathlib import Path

import pandas as pd
from data_profiling import ProfileReport

import config
import limpeza

log = logging.getLogger(__name__)


def localizar_arquivo(pasta: Path, padrao: str) -> Path:
    """Procura um arquivo por padrao de nome, em qualquer nivel dentro da
    pasta (Censo Escolar)."""
    encontrados = sorted(pasta.rglob(padrao))
    if not encontrados:
        raise FileNotFoundError(f"nenhum arquivo '{padrao}' encontrado em {pasta}")
    if len(encontrados) > 1:
        log.warning("mais de um arquivo casou com '%s', usando o primeiro: %s",
                    padrao, [str(e) for e in encontrados])
    return encontrados[0]


def localizar_arquivo_recente(bronze: Path, padrao: str, rotulo: str) -> Path:
    pasta = limpeza.mais_recente(bronze)
    arquivo = localizar_arquivo(pasta, padrao)
    log.info("%s %s", rotulo, arquivo.name)
    return arquivo


def _ler(caminho: Path, sep: str = ",", encoding: str = "utf-8") -> pd.DataFrame:
    if caminho.suffix.lower() == ".csv":
        return pd.read_csv(caminho, sep=sep, encoding=encoding, low_memory=False)
    return pd.read_excel(caminho)


def gerar(caminho: Path, titulo: str, minimal: bool = False, **kwargs_leitura) -> Path:
    df = _ler(caminho, **kwargs_leitura)
    perfil = ProfileReport(df, title=titulo, minimal=minimal)
    config.RELATORIOS.mkdir(exist_ok=True)
    saida = config.RELATORIOS / f"{caminho.stem}.html"
    perfil.to_file(saida)
    return saida


def main():
    arquivo_ideb = localizar_arquivo_recente(
        config.BRONZE_IDEB, "*.csv", "perfilando IDEB:")
    log.info("relatorio: %s",
             gerar(arquivo_ideb, "IDEB - Anos Iniciais - Escolas 2025"))

    arquivo_censo = localizar_arquivo_recente(
        config.BRONZE_CENSO, config.PADRAO_CENSO,
        "perfilando Censo Escolar (Tabela_Escola):")
    log.info("relatorio: %s", gerar(
        arquivo_censo,
        "Censo Escolar 2025 - Estrutura Fisica das Escolas",
        minimal=True,
        sep=";",
        encoding="latin-1",
    ))


if __name__ == "__main__":
    config.configurar_log()
    main()
