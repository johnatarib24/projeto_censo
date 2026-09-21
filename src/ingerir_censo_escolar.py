"""
Ingestao da fonte secundaria: Microdados do Censo Escolar 2025 (INEP)

Baixa o zip do link direto, extrai para a camada bronze (sem alterar o
conteudo) e registra a proveniencia. Este arquivo e grande (varios GB de
zip), entao o download pode demorar bastante. Rode com:
    python src/ingerir_censo_escolar.py

O download usa o curl instalado no sistema (via subprocess) em vez do
pacote requests: o servidor do INEP falha o handshake TLS especificamente
com a stack OpenSSL do Python, mas funciona normalmente com o schannel
(TLS nativo do Windows) que o curl usa. E automatico do mesmo jeito, so
que delegando a parte de rede pra uma ferramenta que essa fonte aceita.
"""
import json
import os
import shutil
import subprocess
import zipfile
from datetime import date, datetime
from pathlib import Path

URL = "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2025_.zip"
BRONZE = Path("dados/bronze/microdados_censo_escolar")


def _caminho_estendido(caminho: Path) -> Path:
    """No Windows, caminhos com mais de 260 caracteres quebram a extracao
    (alguns nomes de arquivo do Censo Escolar sao bem longos, e o
    OneDrive ja adiciona varias pastas antes do projeto). O prefixo \\?\
    pede ao Windows para usar o modo de caminho estendido, que nao tem
    esse limite."""
    if os.name == "nt":
        caminho = caminho.resolve()
        texto = str(caminho)
        if not texto.startswith("\\\\?\\"):
            return Path("\\\\?\\" + texto)
    return caminho


def baixar():
    """Baixa o zip da fonte usando o curl do sistema."""
    if shutil.which("curl") is None:
        raise RuntimeError(
            "curl nao encontrado no PATH. Instale o curl ou baixe o "
            f"arquivo manualmente em {URL}."
        )

    BRONZE.mkdir(parents=True, exist_ok=True)
    destino_zip = BRONZE / "_download_temp.zip"

    print("Baixando Microdados do Censo Escolar (via curl, pode demorar bastante)...")
    subprocess.run(
        [
            "curl", "-sS", "-L", "--fail",
            "--connect-timeout", "30",
            "--retry", "10",
            "--retry-delay", "5",
            "--retry-all-errors",
            "--retry-max-time", "3600",
            "-C", "-",
            URL, "-o", str(destino_zip),
        ],
        check=True,
    )

    print("baixado em:", destino_zip)
    return destino_zip


def extrair(zip_path):
    """Extrai o zip para uma pasta datada dentro da bronze e apaga o zip."""
    hoje = date.today().strftime("%d%m%Y")
    pasta_destino = BRONZE / hoje
    pasta_destino.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path) as z:
        arquivos = z.namelist()
        z.extractall(_caminho_estendido(pasta_destino))

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
    with caminho.open("a", encoding="utf-8") as arquivo:
        arquivo.write(json.dumps(info, ensure_ascii=False) + "\n")

    print("proveniencia registrada em:", caminho)


def main():
    zip_path = baixar()
    pasta_destino, arquivos = extrair(zip_path)
    registrar(pasta_destino, arquivos)


if __name__ == "__main__":
    main()
