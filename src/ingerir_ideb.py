"""
Pre-requisitos (uma vez so):
    Ter um projeto no Google Cloud.
    Na primeira execucao, uma janela do navegador deve abrir pedindo
    login com uma conta Google.

python src/ingerir_ideb.py

"""

import json
from datetime import date, datetime
from pathlib import Path

import basedosdados as bd

DATASET_ID = "br_inep_ideb"
TABLE_ID = "escola"
BILLING_PROJECT_ID = "topicos-510201"

BRONZE = Path("dados/bronze/ideb_escolas")


def baixar():
    
    hoje = date.today().strftime("%d%m%Y")
    pasta_destino = BRONZE / hoje
    pasta_destino.mkdir(parents=True, exist_ok=True)

    destino_csv = pasta_destino / f"{DATASET_ID}_{TABLE_ID}.csv"
    query = f"SELECT * FROM `basedosdados.{DATASET_ID}.{TABLE_ID}`"

    print("Consultando a tabela do IDEB via Base dos Dados...")
    df = bd.read_sql(query, billing_project_id=BILLING_PROJECT_ID)

    df.to_csv(destino_csv, index=False, encoding="utf-8")
    print("baixado em:", destino_csv, "-", df.shape[0], "linhas x", df.shape[1], "colunas")
    return pasta_destino, [destino_csv.name]


def registrar(pasta_destino, arquivos):
    
    info = {
        "fonte": f"basedosdados:{DATASET_ID}.{TABLE_ID}",
        "pasta_bronze": str(pasta_destino),
        "quantidade_arquivos": len(arquivos),
        "arquivos": arquivos,
        "extraido_em": datetime.now().isoformat(),
    }

    caminho = BRONZE / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(info, ensure_ascii=False) + "\n")

    print("proveniencia registrada em:", caminho)


def main():
    pasta_destino, arquivos = baixar()
    registrar(pasta_destino, arquivos)


if __name__ == "__main__":
    main()
    