"""
Valida a camada prata: confere, depois de rodar os transformar_*, que os
invariantes prometidos no README continuam valendo.

    python src/validar_prata.py

Sai com codigo 1 se alguma checagem falhar. Rode a partir da raiz do projeto.
"""
import json
import sys
from pathlib import Path

import pandas as pd

PRATA = Path("dados/prata")
falhas = []


def checar(nome, condicao, detalhe=""):
    ok = bool(condicao)
    print(("OK      " if ok else "FALHOU  ") + nome + (f"  [{detalhe}]" if detalhe else ""))
    if not ok:
        falhas.append(nome)


def ler(nome):
    caminho = PRATA / nome
    if not caminho.exists():
        print(f"AVISO   {nome} nao encontrado: checagens dessa fonte puladas")
        return None
    return pd.read_parquet(caminho)


def validar_ideb(i):
    print("\n== IDEB ==")
    checar("id_escola unico (chave)", i["id_escola"].is_unique, f"{len(i)} linhas")
    checar("so ano 2025", (i["ano"] == 2025).all())
    checar("so anos iniciais", (i["anos_escolares"] == "iniciais (1-5)").all())
    checar("ideb dentro de 0-10", i["ideb"].dropna().between(0, 10).all())
    checar("taxa_aprovacao dentro de 0-100", i["taxa_aprovacao"].dropna().between(0, 100).all())
    checar("id_municipio com 7 digitos", (i["id_municipio"].str.len() == 7).all())
    checar("rede e categoria sem ausentes",
           str(i["rede"].dtype) == "category" and i["rede"].notna().all())
    checar("ideb_disponivel coerente com ideb",
           (i["ideb_disponivel"] == i["ideb"].notna()).all())
    for col in ["ideb_extremo", "ideb_z", "taxa_aprovacao_extremo", "taxa_aprovacao_z"]:
        checar(f"coluna {col} existe e e booleana",
               col in i.columns and str(i[col].dtype) == "bool")


def validar_censo(c):
    print("\n== Censo Escolar ==")
    checar("CO_ENTIDADE unico (chave)", c["CO_ENTIDADE"].is_unique, f"{len(c)} linhas")
    checar("CO_MUNICIPIO com 7 digitos", (c["CO_MUNICIPIO"].str.len() == 7).all())
    ins = [x for x in c.columns if x.startswith("IN_")]
    checar("todas as IN_* sao Int8", all(str(c[x].dtype) == "Int8" for x in ins),
           f"{len(ins)} colunas")
    checar("IN_* so com 0, 1 ou ausente",
           all(c[x].dropna().isin([0, 1]).all() for x in ins))
    qts = [x for x in c.columns if x.startswith("QT_") and not x.endswith("_extremo")]
    checar("nenhum 88888 sobrando nas QT_*", not (c[qts] == 88888).any().any())
    checar("qt_extremo_inep existe", "qt_extremo_inep" in c.columns,
           f"{int(c['qt_extremo_inep'].sum())} escolas")
    checar("NU_ANO_CENSO removida", "NU_ANO_CENSO" not in c.columns)
    for col in ["TP_DEPENDENCIA", "TP_SITUACAO_FUNCIONAMENTO", "TP_LOCALIZACAO"]:
        checar(f"{col} e categoria sem ausentes",
               str(c[col].dtype) == "category" and c[col].notna().all())
    ind = c["indice_infraestrutura"]
    checar("indice_infraestrutura entre 0 e 1", ind.dropna().between(0, 1).all())
    ativas = c["TP_SITUACAO_FUNCIONAMENTO"] == "em atividade"
    checar("toda escola em atividade tem indice", ind[ativas].notna().all())
    checar("escola fora de atividade fica sem indice (ausente, nao zero)",
           ind[~ativas].isna().all())
    for bloco in ["infra_basica", "infra_espacos_ensino",
                  "infra_acessibilidade", "infra_tecnologia"]:
        checar(f"{bloco} entre 0 e 1", c[bloco].dropna().between(0, 1).all())


def validar_ibge(m):
    print("\n== IBGE (municipios) ==")
    checar("id_municipio unico (chave)", m["id_municipio"].is_unique, f"{len(m)} linhas")
    checar("id_municipio com 7 digitos", (m["id_municipio"].str.len() == 7).all())
    checar("sem ausentes em nome, UF e regiao",
           m[["nome_municipio", "sigla_uf", "regiao"]].notna().all().all())
    checar("regiao tem as 5 regioes", m["regiao"].nunique() == 5,
           f"{m['regiao'].nunique()} encontradas")


def validar_entre_fontes(i, c, m):
    print("\n== Entre fontes ==")
    com_par = i["id_escola"].isin(set(c["CO_ENTIDADE"]))
    print(f"INFO    escolas do IDEB no Censo: {int(com_par.sum())} de {len(i)} "
          f"({com_par.mean():.1%})")
    checar("toda escola do IDEB que TEM ideb esta no Censo",
           com_par[i["ideb"].notna()].all(),
           f"{int((~com_par & i['ideb'].notna()).sum())} sem par")
    if m is not None:
        ibge = set(m["id_municipio"])
        fora_i = set(i["id_municipio"]) - ibge
        fora_c = set(c["CO_MUNICIPIO"]) - ibge
        checar("todo id_municipio do IDEB existe no IBGE", not fora_i, f"{len(fora_i)} fora")
        checar("todo CO_MUNICIPIO do Censo existe no IBGE", not fora_c, f"{len(fora_c)} fora")


def validar_proveniencia():
    print("\n== Proveniencia ==")
    caminho = PRATA / "proveniencia.jsonl"
    checar("proveniencia.jsonl existe", caminho.exists())
    if not caminho.exists():
        return
    linhas = [json.loads(x) for x in caminho.read_text(encoding="utf-8").splitlines() if x.strip()]
    gravados = {l["arquivo_prata"] for l in linhas}
    for arq in sorted(p.name for p in PRATA.glob("*.parquet")):
        n = sum(l["arquivo_prata"] == arq for l in linhas)
        checar(f"{arq} registrado na proveniencia", arq in gravados,
               f"{n} linha(s); so a ultima deve valer" if n > 1 else "")


def main():
    i, c, m = ler("ideb_escolas.parquet"), ler("censo_escolas.parquet"), ler("ibge_municipios.parquet")
    if i is not None:
        validar_ideb(i)
    if c is not None:
        validar_censo(c)
    if m is not None:
        validar_ibge(m)
    if i is not None and c is not None:
        validar_entre_fontes(i, c, m)
    validar_proveniencia()
    print("\n" + (f"{len(falhas)} CHECAGEM(NS) FALHOU: {falhas}" if falhas else "TUDO CERTO"))
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
