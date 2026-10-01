"""
Bronze da terceira fonte: API de Localidades do IBGE (municipios).

    python src/ingerir_ibge_municipios.py.
"""
import json
from datetime import date, datetime
from pathlib import Path

import requests

URL = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios"
BRONZE = Path("dados/bronze/ibge_municipios")
MINIMO_ESPERADO = 5000  # o Brasil tem ~5.570 municipios; bem menos que isso e erro


def baixar():
    print("Consultando a API de Localidades do IBGE...")
    resposta = requests.get(URL, timeout=60)
    resposta.raise_for_status()
    dados = resposta.json()

    if not isinstance(dados, list):
        raise ValueError(f"resposta inesperada: {type(dados)}")
    ids = [m["id"] for m in dados]
    print("municipios recebidos:", len(ids), "| ids unicos:", len(set(ids)))
    if len(ids) < MINIMO_ESPERADO:
        raise ValueError(f"so {len(ids)} municipios: resposta incompleta?")
    if len(ids) != len(set(ids)):
        raise ValueError("ids repetidos na resposta")

    pasta = BRONZE / date.today().strftime("%d%m%Y")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / "localidades_municipios.json"
    with destino.open("w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False)
    print("baixado em:", destino)
    return pasta, [destino.name], len(ids), resposta.headers.get("Date")


def registrar(pasta, arquivos, n_municipios, data_http):
    info = {
        "fonte": URL,
        "pasta_bronze": str(pasta),
        "quantidade_arquivos": len(arquivos),
        "arquivos": arquivos,
        "municipios_recebidos": n_municipios,
        "resposta_http_date": data_http,
        "extraido_em": datetime.now().isoformat(),
    }
    caminho = BRONZE / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")
    print("proveniencia registrada em:", caminho)


def main():
    pasta, arquivos, n, data_http = baixar()
    registrar(pasta, arquivos, n, data_http)


if __name__ == "__main__":
    main()
