"""
Caminhos, parametros e log do projeto.

Regra: este arquivo nao importa nenhum outro modulo do projeto, e nao guarda
segredo (senha, token, chave). Segredo vai em variavel de ambiente.
"""
import logging
import os
from pathlib import Path

# ---------------------------------------------------------------- caminhos
# Calculados a partir deste arquivo: nao dependem de onde o comando foi dado.
RAIZ = Path(__file__).resolve().parent.parent
DADOS = RAIZ / "dados"
BRONZE = DADOS / "bronze"
PRATA = DADOS / "prata"
OURO = DADOS / "ouro"
RELATORIOS = RAIZ / "relatorios"
DBT_PROJETO = RAIZ / "ecox14"
ARQUIVO_LOG = RAIZ / "pipeline.log"
BANCO = OURO / "projeto.duckdb"

BRONZE_IDEB = BRONZE / "ideb_escolas"
BRONZE_CENSO = BRONZE / "microdados_censo_escolar"

# ---------------------------------------------------------------- parametros
ANO = 2025
ANOS_ESCOLARES = "iniciais (1-5)"
N_UFS_ANALISE = 26  # 27 UFs menos o DF, que nao tem rede municipal

# IDEB (Base dos Dados). O projeto de cobranca do Google Cloud pode ser
# trocado por variavel de ambiente, sem editar o codigo.
DATASET_ID = "br_inep_ideb"
TABLE_ID = "escola"
BILLING_PROJECT_ID = os.getenv("BILLING_PROJECT_ID", "topicos-510201")

# Censo Escolar (INEP)
URL_CENSO = "https://download.inep.gov.br/dados_abertos/microdados_censo_escolar_2025_.zip"
PADRAO_CENSO = "Tabela_Escola_2025_V2*.csv"


# ---------------------------------------------------------------- log
def configurar_log():
    """Log na tela e em pipeline.log, com hora, nivel e modulo."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        handlers=[
            logging.FileHandler(ARQUIVO_LOG, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
