"""
Exploracao automatizada das fontes (Aula 4).

Gera um relatorio de profiling (fg-data-profiling) para o arquivo mais
relevante de cada fonte na camada bronze. As constantes de cada fonte
viram parametro das funcoes, entao adicionar uma terceira fonte no
futuro e so mais uma chamada em main(), sem editar o resto do script.

Rode com:
    python src/explorar.py
"""
from datetime import datetime
from pathlib import Path

import pandas as pd
from data_profiling import ProfileReport

RELATORIOS = Path("relatorios")
FORMATO_PASTA = "%d%m%Y"


def mais_recente(bronze: Path) -> Path:
    """Retorna a pasta datada (ddmmaaaa) mais recente dentro da bronze de
    uma fonte. Nesse formato a ordem alfabetica NAO coincide com a ordem
    cronologica (ex: '01012026' vem antes de '31122025' no alfabeto, mas
    depois no calendario), entao a data e interpretada de verdade em vez
    de comparada como texto."""
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
    pasta (util quando o zip extraido tem varias subpastas, como o do
    Censo Escolar)."""
    encontrados = sorted(pasta.rglob(padrao))
    if not encontrados:
        raise FileNotFoundError(f"nenhum arquivo '{padrao}' encontrado em {pasta}")
    if len(encontrados) > 1:
        print(f"aviso: mais de um arquivo casou com '{padrao}', usando o primeiro:")
        for e in encontrados:
            print("  -", e)
    return encontrados[0]


def _ler(caminho: Path) -> pd.DataFrame:
    """Le xlsx ou csv. Dados abertos de orgaos do governo (INEP incluido)
    costumam vir em csv com separador ';' e codificacao latin-1, em vez
    do padrao ',' + utf-8 do pandas."""
    if caminho.suffix.lower() == ".csv":
        return pd.read_csv(caminho, sep=";", encoding="latin-1", low_memory=False)
    return pd.read_excel(caminho)


def gerar(caminho: Path, titulo: str, minimal: bool = False) -> Path:
    """Le a fonte (xlsx ou csv) e gera o relatorio de profiling em
    relatorios/. minimal=True pula os calculos mais pesados (correlacoes
    par a par, interacoes), recomendado para datasets com muitas colunas
    e muitas linhas -- sem isso, o calculo de correlacao pode demorar
    tanto que parece que o script travou."""
    df = _ler(caminho)
    perfil = ProfileReport(df, title=titulo, minimal=minimal)
    RELATORIOS.mkdir(exist_ok=True)
    saida = RELATORIOS / f"{caminho.stem}.html"
    perfil.to_file(saida)
    return saida


def main():
    # Fonte 1: IDEB - Anos Iniciais - Escolas 2025 (um unico xlsx no topo
    # da pasta extraida)
    pasta_ideb = mais_recente(Path("dados/bronze/ideb_anos_iniciais_escolas"))
    arquivo_ideb = localizar_arquivo(pasta_ideb, "*.xlsx")
    print("perfilando IDEB:", arquivo_ideb.name)
    print(gerar(arquivo_ideb, "IDEB - Anos Iniciais - Escolas 2025"))

    # Fonte 2: Microdados do Censo Escolar 2025 - dentro da pasta "dados"
    # extraida ha varios xlsx; so nos interessa a Tabela_Escola_2025_V2,
    # que traz a estrutura fisica de cada escola.
    pasta_censo = mais_recente(Path("dados/bronze/microdados_censo_escolar"))
    arquivo_censo = localizar_arquivo(pasta_censo, "Tabela_Escola_2025_V2*.csv")
    print("perfilando Censo Escolar (Tabela_Escola):", arquivo_censo.name)
    print(gerar(arquivo_censo, "Censo Escolar 2025 - Estrutura Fisica das Escolas", minimal=True))


if __name__ == "__main__":
    main()