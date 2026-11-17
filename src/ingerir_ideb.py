"""
Bronze do IDEB (Base dos Dados: br_inep_ideb.escola).

Pre-requisitos (uma vez so):
    Ter um projeto no Google Cloud.
    Na primeira execucao, uma janela do navegador deve abrir pedindo
    login com uma conta Google.

    python src/ingerir_ideb.py
"""
import json
import logging
from datetime import date, datetime

import basedosdados as bd

import config

log = logging.getLogger(__name__)

BRONZE = config.BRONZE_IDEB


def baixar():
    hoje = date.today().strftime("%d%m%Y")
    pasta_destino = BRONZE / hoje
    pasta_destino.mkdir(parents=True, exist_ok=True)

    destino_csv = pasta_destino / f"{config.DATASET_ID}_{config.TABLE_ID}.csv"
    query = f"SELECT * FROM `basedosdados.{config.DATASET_ID}.{config.TABLE_ID}`"

    log.info("consultando a tabela do IDEB via Base dos Dados")
    df = bd.read_sql(query, billing_project_id=config.BILLING_PROJECT_ID)

    df.to_csv(destino_csv, index=False, encoding="utf-8")
    log.info("baixado em %s: %d linhas x %d colunas",
             destino_csv, df.shape[0], df.shape[1])
    return pasta_destino, [destino_csv.name]


def registrar(pasta_destino, arquivos):
    info = {
        "fonte": f"basedosdados:{config.DATASET_ID}.{config.TABLE_ID}",
        "pasta_bronze": str(pasta_destino),
        "quantidade_arquivos": len(arquivos),
        "arquivos": arquivos,
        "extraido_em": datetime.now().isoformat(),
    }
    caminho = BRONZE / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(info, ensure_ascii=False) + "\n")
    log.info("proveniencia registrada em: %s", caminho)


def main():
    pasta_destino, arquivos = baixar()
    registrar(pasta_destino, arquivos)


if __name__ == "__main__":
    config.configurar_log()
    main()
