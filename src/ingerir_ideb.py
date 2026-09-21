"""
Ingestao da fonte primaria: IDEB - Anos Iniciais - Escolas 2025 (INEP)

NOTA(para eu não esquecer): para rodar a ingestao usar o comando:

    python src/ingerir_ideb.py

O download usa o curl instalado no sistema (via subprocess) em vez do
pacote requests: o servidor do INEP falha o handshake TLS especificamente
com a stack OpenSSL do Python, mas funciona normalmente com o schannel
(TLS nativo do Windows) que o curl usa.
"""
import json
import shutil
import subprocess
import zipfile
from datetime import date, datetime
from pathlib import Path

URL = "https://download.inep.gov.br/ideb/resultados/divulgacao_anos_iniciais_escolas_2025.zip"
BRONZE = Path("dados/bronze/ideb_anos_iniciais_escolas")


def baixar():
    if shutil.which("curl") is None:
        raise RuntimeError(
            "curl nao encontrado no PATH. Instale o curl ou baixe o "
            f"arquivo manualmente em {URL}."
        )

    BRONZE.mkdir(parents=True, exist_ok=True)
    destino_zip = BRONZE / "_download_temp.zip"

    print("Baixando arquivo do IDEB (via curl)...")
    subprocess.run(
        [
            "curl", "-sS", "-L", "--fail",
            "--connect-timeout", "30",
            "--retry", "8",
            "--retry-delay", "5",
            "--retry-all-errors",
            "--retry-max-time", "600",
            "-C", "-",
            URL, "-o", str(destino_zip),
        ],
        check=True,
    )

    print("baixado em:", destino_zip)
    return destino_zip


def extrair(zip_path):
    hoje = date.today().strftime("%d%m%Y")
    pasta_destino = BRONZE / hoje
    pasta_destino.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as z:
        arquivos = z.namelist()
        z.extractall(pasta_destino)

    zip_path.unlink()
    print("extraidos:", len(arquivos), "arquivo(s) em", pasta_destino)
    return pasta_destino, arquivos


def registrar(pasta_destino, arquivos):
    info = {
        "fonte": URL,
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
    zip_path = baixar()
    pasta_destino, arquivos = extrair(zip_path)
    registrar(pasta_destino, arquivos)


if __name__ == "__main__":
    main()
