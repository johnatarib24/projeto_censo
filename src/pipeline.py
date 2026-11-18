"""
Roda o pipeline inteiro, ou a partir de uma etapa.

    python src/pipeline.py
    python src/pipeline.py transformacao
"""
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import config

log = logging.getLogger("pipeline")


# Cada etapa importa seus modulos so quando roda: erro de import em uma
# etapa nao impede as outras.
def ingerir_todas():
    import ingerir_censo_escolar
    import ingerir_ideb
    ingerir_ideb.main()
    ingerir_censo_escolar.main()


def transformar_todas():
    import transformar_censo_escolar
    import transformar_ideb
    transformar_ideb.main()
    transformar_censo_escolar.main()


def enriquecer():
    import enriquecer as etapa
    etapa.main()


def etapa_carga():
    import carga
    carga.main()


def _comando_dbt():
    """O dbt instalado no mesmo ambiente do Python que roda o pipeline."""
    pasta = Path(sys.executable).parent
    for nome in ("dbt.exe", "dbt"):
        if (pasta / nome).exists():
            return [str(pasta / nome)]
    if achado := shutil.which("dbt"):
        return [achado]
    raise FileNotFoundError("dbt nao encontrado: pip install dbt-core dbt-duckdb")


def etapa_modelagem():
    """dbt run constroi a Ouro; depois as conferencias confirmam o resultado."""
    import carga
    ambiente = {**os.environ, "DBT_DUCKDB_PATH": str(config.BANCO)}
    resultado = subprocess.run(
        _comando_dbt() + ["run", "--no-use-colors"],
        cwd=config.DBT_PROJETO, env=ambiente, capture_output=True, text=True,
    )
    for linha in resultado.stdout.splitlines():
        log.info("dbt: %s", linha)
    if resultado.returncode != 0:
        log.error("dbt run falhou (codigo %d)\n%s", resultado.returncode,
                  (resultado.stdout[-2000:] + resultado.stderr).strip())
        # sem isso o pipeline diria que terminou bem com a Ouro quebrada
        raise subprocess.CalledProcessError(resultado.returncode, "dbt run")
    carga.conferir_ouro()


ETAPAS = [
    ("ingestao", ingerir_todas),
    ("transformacao", transformar_todas),
    ("enriquecimento", enriquecer),
    ("carga", etapa_carga),
    ("modelagem", etapa_modelagem),
]


def executar(nome, funcao):
    log.info("etapa %s: inicio", nome)
    comeco = time.perf_counter()
    try:
        funcao()
    except Exception:
        log.exception("etapa %s falhou", nome)
        raise
    log.info("etapa %s: fim em %.0fs", nome, time.perf_counter() - comeco)


def main(a_partir_de=None):
    config.configurar_log()
    nomes = [nome for nome, _ in ETAPAS]
    if a_partir_de is not None and a_partir_de not in nomes:
        log.error("etapa '%s' nao existe; opcoes: %s", a_partir_de, nomes)
        raise SystemExit(1)

    comecou = a_partir_de is None
    for nome, funcao in ETAPAS:
        if nome == a_partir_de:
            comecou = True
        if not comecou or funcao is None:
            log.info("etapa %s: pulada", nome)
            continue
        executar(nome, funcao)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
