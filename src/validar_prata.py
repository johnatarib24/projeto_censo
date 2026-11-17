"""
Confere os invariantes da prata. Sai com codigo 1 se algum deixar de valer.

    python src/validar_prata.py
"""
import json
import logging
import re
import sys

import pandas as pd

import config

log = logging.getLogger(__name__)

REDES = {"federal", "estadual", "municipal"}
CODIGO_QT_EXTREMO_INEP = 88888
CAMPOS_PROVENIENCIA = {"origem", "arquivo_prata", "linhas_antes", "linhas_depois",
                       "decisoes", "transformado_em"}


class Conferencia:
    def __init__(self):
        self.total = 0
        self.falhas = []

    def exigir(self, condicao, mensagem):
        self.total += 1
        if bool(condicao):
            log.info("ok: %s", mensagem)
        else:
            log.error("FALHOU: %s", mensagem)
            self.falhas.append(mensagem)


def validar_ideb(c, df):
    c.exigir(df["id_escola"].is_unique, "ideb: id_escola e unica")
    c.exigir(df["id_municipio"].str.len().eq(7).all(), "ideb: id_municipio com 7 digitos")
    c.exigir((df["ano"] == config.ANO).all(), f"ideb: ano = {config.ANO} em todas as linhas")
    c.exigir((df["anos_escolares"] == config.ANOS_ESCOLARES).all(),
             f"ideb: anos_escolares = '{config.ANOS_ESCOLARES}' em todas as linhas")
    c.exigir(df["ideb"].dropna().between(0, 10).all(), "ideb: ideb dentro de [0, 10]")
    c.exigir(df["taxa_aprovacao"].dropna().between(0, 100).all(),
             "ideb: taxa_aprovacao dentro de [0, 100]")
    c.exigir((df["ideb_disponivel"] == df["ideb"].notna()).all(),
             "ideb: ideb_disponivel confere com ideb preenchido")
    c.exigir(df["rede"].notna().all() and set(df["rede"].unique()) <= REDES,
             "ideb: rede so com federal, estadual ou municipal")


def validar_censo(c, df):
    c.exigir(df["CO_ENTIDADE"].is_unique, "censo: CO_ENTIDADE e unica")
    c.exigir(df["CO_MUNICIPIO"].str.len().eq(7).all(), "censo: CO_MUNICIPIO com 7 digitos")
    c.exigir("NU_ANO_CENSO" not in df.columns, "censo: NU_ANO_CENSO (constante) removida")

    em = [x for x in df.columns if x.startswith("IN_")]
    c.exigir(all(str(df[x].dtype) == "Int8" for x in em), f"censo: {len(em)} colunas IN_* em Int8")
    c.exigir(all(df[x].dropna().isin([0, 1]).all() for x in em),
             "censo: IN_* so com 0, 1 ou ausente")

    qt = [x for x in df.columns if x.startswith("QT_")]
    c.exigir(not any((df[x] == CODIGO_QT_EXTREMO_INEP).any() for x in qt),
             f"censo: nenhum QT_* com o codigo {CODIGO_QT_EXTREMO_INEP}")

    for x in ["TP_DEPENDENCIA", "TP_SITUACAO_FUNCIONAMENTO", "TP_LOCALIZACAO"]:
        c.exigir(isinstance(df[x].dtype, pd.CategoricalDtype), f"censo: {x} e categoria")

    for x in ["indice_infraestrutura", "infra_basica", "infra_espacos_ensino",
              "infra_acessibilidade", "infra_tecnologia"]:
        c.exigir(df[x].dropna().between(0, 1).all(), f"censo: {x} dentro de [0, 1]")
    ativas = df["TP_SITUACAO_FUNCIONAMENTO"] == "em atividade"
    c.exigir(df.loc[ativas, "indice_infraestrutura"].notna().all(),
             "censo: toda escola em atividade tem indice_infraestrutura")


def validar_entre_fontes(c, ideb, censo):
    com_ideb = ideb[ideb["ideb_disponivel"]]
    c.exigir(com_ideb["id_escola"].isin(censo["CO_ENTIDADE"]).all(),
             "entre fontes: toda escola com IDEB esta no Censo")
    cobertura = ideb["id_escola"].isin(censo["CO_ENTIDADE"]).mean() * 100
    log.info("cobertura do IDEB no Censo: %.1f%% das escolas", cobertura)


def validar_enriquecido(c, df, ideb):
    c.exigir(len(df) == len(ideb), "enriquecido: mesmo numero de linhas do IDEB (grao preservado)")
    c.exigir(df["id_escola"].is_unique, "enriquecido: id_escola e unica")

    casou = df["CO_ENTIDADE"].notna()
    c.exigir((df.loc[casou, "sigla_uf"] == df.loc[casou, "SG_UF"]).all(),
             "enriquecido: UF igual no IDEB e no Censo")
    c.exigir((df.loc[casou, "id_municipio"] == df.loc[casou, "CO_MUNICIPIO"]).all(),
             "enriquecido: municipio igual no IDEB e no Censo")

    na = df["na_analise"]
    criterios = ((df["rede"] == "municipal") & (df["TP_DEPENDENCIA"] == "municipal")
                 & (df["TP_SITUACAO_FUNCIONAMENTO"] == "em atividade")
                 & df["ideb_disponivel"] & df["indice_infraestrutura"].notna())
    c.exigir((na == criterios).all(), "enriquecido: na_analise segue os 5 criterios")

    ufs = set(df.loc[na, "sigla_uf"].unique())
    c.exigir(len(ufs) == config.N_UFS_ANALISE and "DF" not in ufs,
             f"enriquecido: na_analise cobre {config.N_UFS_ANALISE} UFs, sem o DF")


def validar_proveniencia(c, tamanhos):
    caminho = config.PRATA / "proveniencia.jsonl"
    c.exigir(caminho.exists(), "proveniencia: arquivo existe")
    if not caminho.exists():
        return
    registros = []
    for i, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
        if not linha.strip():
            continue  # linha em branco e inofensiva num .jsonl
        try:
            registros.append(json.loads(linha))
        except json.JSONDecodeError as erro:
            c.exigir(False, f"proveniencia: linha {i} e JSON valido "
                            f"({erro.msg}; comeca com {linha[:50]!r})")
    c.exigir(all(CAMPOS_PROVENIENCIA <= set(r) for r in registros),
             "proveniencia: todas as linhas com os campos esperados")
    absoluto = re.compile(r"^([A-Za-z]:[\\/]|/)")
    c.exigir(not any(absoluto.match(r["origem"]) for r in registros if "origem" in r),
             "proveniencia: nenhuma origem com caminho absoluto")

    ultimo = {r["arquivo_prata"]: r for r in registros if "arquivo_prata" in r}
    for nome, linhas in tamanhos.items():
        c.exigir(nome in ultimo and ultimo[nome]["linhas_depois"] == linhas,
                 f"proveniencia: ultima linha de {nome} confere com o parquet ({linhas} linhas)")


def main():
    ideb = pd.read_parquet(config.PRATA / "ideb_escolas.parquet")
    censo = pd.read_parquet(config.PRATA / "censo_escolas.parquet")
    enriquecido = pd.read_parquet(config.PRATA / "ideb_censo_enriquecido.parquet")

    c = Conferencia()
    validar_ideb(c, ideb)
    validar_censo(c, censo)
    validar_entre_fontes(c, ideb, censo)
    validar_enriquecido(c, enriquecido, ideb)
    validar_proveniencia(c, {
        "ideb_escolas.parquet": len(ideb),
        "censo_escolas.parquet": len(censo),
        "ideb_censo_enriquecido.parquet": len(enriquecido),
    })

    if c.falhas:
        log.error("%d de %d conferencias falharam", len(c.falhas), c.total)
        sys.exit(1)
    log.info("todas as %d conferencias passaram", c.total)


if __name__ == "__main__":
    config.configurar_log()
    main()
