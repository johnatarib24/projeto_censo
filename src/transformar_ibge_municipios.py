"""
Camada prata da API de Localidades do IBGE (municipios).

    python src/transformar_ibge_municipios.py
"""
import json
from pathlib import Path

import pandas as pd

import limpeza

BRONZE = Path("dados/bronze/ibge_municipios")
PRATA = Path("dados/prata")

CHAVE = ["id_municipio"]
TAMANHO_ID = 7
REGIOES = ["Norte", "Nordeste", "Centro-Oeste", "Sudeste", "Sul"]


def carregar():
    pasta = limpeza.mais_recente(BRONZE)
    caminho = pasta / "localidades_municipios.json"
    with caminho.open(encoding="utf-8") as f:
        dados = json.load(f)
    print("lido:", caminho, len(dados), "municipios")
    return dados, caminho


def achatar(dados):
    """O JSON traz UF e regiao dentro de microrregiao > mesorregiao > UF.
    Se a microrregiao vier vazia, cai para regiao-imediata > intermediaria."""
    linhas, sem_caminho_principal = [], 0
    for m in dados:
        uf = ((m.get("microrregiao") or {}).get("mesorregiao") or {}).get("UF")
        if not uf:
            sem_caminho_principal += 1
            uf = (((m.get("regiao-imediata") or {})
                   .get("regiao-intermediaria") or {}).get("UF")) or {}
        regiao = uf.get("regiao") or {}
        linhas.append({
            "id_municipio": str(m["id"]),
            "nome_municipio": m.get("nome"),
            "sigla_uf": uf.get("sigla"),
            "regiao": regiao.get("nome"),
        })
    print("municipios sem microrregiao (usado o caminho alternativo):",
          sem_caminho_principal)
    return pd.DataFrame(linhas), sem_caminho_principal


def conferir_ids(df):
    fora = int((df["id_municipio"].str.len() != TAMANHO_ID).sum())
    print(f"id_municipio com tamanho diferente de {TAMANHO_ID}:", fora)
    return fora


def conferir_preenchimento(df):
    ausentes = df[["nome_municipio", "sigla_uf", "regiao"]].isna().sum()
    print("ausentes:", ausentes.to_dict())
    return int(ausentes.sum())


def salvar(df):
    PRATA.mkdir(parents=True, exist_ok=True)
    destino = PRATA / "ibge_municipios.parquet"
    df.to_parquet(destino, index=False)
    print("salvo em:", destino, df.shape)
    return destino


def main():
    dados, origem = carregar()
    antes = len(dados)

    df, sem_micro = achatar(dados)
    df = limpeza.tirar_espacos(df)
    fora_id = conferir_ids(df)
    df, repetidas = limpeza.conferir_chave(df, CHAVE, mostrar=["nome_municipio"])
    n_ausentes = conferir_preenchimento(df)
    df, fora_regiao = limpeza.tipar_categoria(df, "regiao", REGIOES)
    print(df.groupby("regiao", observed=True).size().to_string())

    destino = salvar(df)
    limpeza.registrar(PRATA, {
        "origem": str(origem),
        "arquivo_prata": destino.name,
        "linhas_antes": antes,
        "linhas_depois": len(df),
        "decisoes": [
            "JSON aninhado achatado: id, nome, sigla da UF e regiao por municipio",
            f"{sem_micro} municipios sem microrregiao: UF lida de regiao-imediata",
            "id_municipio lido como texto; conferido o tamanho de 7 digitos "
            f"({fora_id} fora)",
            f"chave {CHAVE}: {repetidas} repeticoes removidas",
            f"ausentes nas colunas de interesse: {n_ausentes}",
            f"regiao tipada como categoria {REGIOES} "
            f"({fora_regiao} fora da lista)",
            "sem coluna temporal: fonte descreve um retrato, nao uma serie",
        ],
    })


if __name__ == "__main__":
    main()
