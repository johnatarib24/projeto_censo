"""
python src/explorar.py

"""

from datetime import datetime
from pathlib import Path

import pandas as pd
from data_profiling import ProfileReport

RELATORIOS = Path("relatorios")
FORMATO_PASTA = "%d%m%Y"


def mais_recente(bronze: Path) -> Path:

    candidatas = []
    for p in bronze.iterdir():
        if not p.is_dir():
            continue
        try:
            data = datetime.strptime(p.name, FORMATO_PASTA)
        except ValueError:
            continue
        candidatas.append((data, p))

    if not candidatas:
        raise FileNotFoundError(f"nenhuma pasta datada encontrada em {bronze}")

    candidatas.sort(key=lambda item: item[0])
    return candidatas[-1][1]


def localizar_arquivo(pasta: Path, padrao: str) -> Path:
    """Procura um arquivo por padrao de nome, em qualquer nivel dentro da
    pasta (Censo Escolar)."""
    encontrados = sorted(pasta.rglob(padrao))
    if not encontrados:
        raise FileNotFoundError(f"nenhum arquivo '{padrao}' encontrado em {pasta}")
    if len(encontrados) > 1:
        print(f"aviso: mais de um arquivo casou com '{padrao}', usando o primeiro:")
        for e in encontrados:
            print("  -", e)
    return encontrados[0]


def _ler(caminho: Path, sep: str = ",", encoding: str = "utf-8") -> pd.DataFrame:
    
    if caminho.suffix.lower() == ".csv":
        return pd.read_csv(caminho, sep=sep, encoding=encoding, low_memory=False)
    return pd.read_excel(caminho)


def gerar(caminho: Path, titulo: str, minimal: bool = False, **kwargs_leitura) -> Path:
    
    df = _ler(caminho, **kwargs_leitura)
    perfil = ProfileReport(df, title=titulo, minimal=minimal)
    RELATORIOS.mkdir(exist_ok=True)
    saida = RELATORIOS / f"{caminho.stem}.html"
    perfil.to_file(saida)
    return saida


def main():
    
    arquivo_ideb = localizar_arquivo_recente(
        "dados/bronze/ideb_anos_iniciais_escolas", "*.csv", "perfilando IDEB:"
    )
    print(gerar(arquivo_ideb, "IDEB - Anos Iniciais - Escolas 2025"))

    arquivo_censo = localizar_arquivo_recente(
        "dados/bronze/microdados_censo_escolar",
        "Tabela_Escola_2025_V2*.csv",
        "perfilando Censo Escolar (Tabela_Escola):",
    )
    print(gerar(
        arquivo_censo,
        "Censo Escolar 2025 - Estrutura Fisica das Escolas",
        minimal=True,
        sep=";",
        encoding="latin-1",
    ))

def localizar_arquivo_recente(arg0, arg1, arg2):
    pasta = mais_recente(Path(arg0))
    result = localizar_arquivo(pasta, arg1)
    print(arg2, result.name)
    return result


if __name__ == "__main__":
    main()
    