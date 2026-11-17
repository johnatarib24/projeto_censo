"""
Roda o pipeline inteiro, ou a partir de uma etapa.

    python src/pipeline.py
    python src/pipeline.py transformacao
"""
import logging
import sys
import time

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


ETAPAS = [
    ("ingestao", ingerir_todas),
    ("transformacao", transformar_todas),
    ("enriquecimento", enriquecer),
    ("carga", etapa_carga),
    ("modelagem", None),   # proxima aula
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
