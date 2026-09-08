from pathlib import Path
from datetime import date, datetime
import json
import zipfile

import requests

URL = "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2025_.zip"
BRONZE = Path("dados/bronze/microdados_censo_escolar")


def baixar():
    """Baixa o zip da fonte em stream (arquivo grande) para um temporario."""
    BRONZE.mkdir(parents=True, exist_ok=True)
    destino_zip = BRONZE / "_download_temp.zip"
    with requests.get(URL, stream=True, timeout=300) as r:
        r.raise_for_status()
        with destino_zip.open("wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    print("baixado em:", destino_zip)
    return destino_zip


def extrair(zip_path):
    """Extrai o zip para uma pasta datada dentro da bronze e apaga o zip."""
    hoje = date.today().strftime("%Y%m%d")
    pasta_destino = BRONZE / hoje
    pasta_destino.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as z:
        arquivos = z.namelist()
        z.extractall(pasta_destino)
    zip_path.unlink()
    print("extraidos:", len(arquivos), "arquivo(s) em", pasta_destino)
    return pasta_destino, arquivos


def registrar(pasta_destino, arquivos):
    """Registra a proveniencia (append, nunca sobrescreve)."""
    info = {
        "fonte": URL,
        "pasta_bronze": str(pasta_destino),
        "quantidade_arquivos": len(arquivos),
        "arquivos": arquivos,
        "extraido_em": datetime.now().isoformat(),
    }
    caminho = BRONZE / "proveniencia.jsonl"
    with caminho.open("a", encoding="utf-8") as f:
        f.write(json.dumps(info, ensure_ascii=False) + "\n")
    print("proveniencia registrada em:", caminho)


def main():
    zip_path = baixar()
    pasta_destino, arquivos = extrair(zip_path)
    registrar(pasta_destino, arquivos)


if __name__ == "__main__":
    main()
