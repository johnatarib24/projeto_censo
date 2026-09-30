# Infraestrutura escolar e desempenho municipal no IDEB (2025)

**Autor:** Johnata Thyago Ribeiro — ECOX14

## Pergunta norteadora

Nos municípios brasileiros, existe associação entre a estrutura das escolas municipais e o desempenho educacional medido pelo IDEB dos anos iniciais do ensino fundamental em 2025?

## Fontes de dados

| Fonte | Formato | Acesso | Extraído | Link |
|---|---|---|---|---|
| IDEB - Anos Iniciais, Escolas 2025 | CSV | API (Base dos Dados / BigQuery) | 30/09/2026 | basedosdados.org (`br_inep_ideb.escola`) |
| Censo Escolar 2025 - Tabela_Escola | CSV | Arquivo baixado | 08/09/2026 | download.inep.gov.br/dados_abertos |

Chave de ligação entre as duas: `id_municipio` (IDEB) = `CO_MUNICIPIO` (Censo Escolar).

## Defeitos conhecidos das fontes

### IDEB (Base dos Dados)
- Tabela vem com todas as edições (2005-2025) e todos os níveis de ensino juntos; precisa filtrar `ano = 2025` e `anos_escolares = 'iniciais (1-5)'`.
- `taxa_aprovacao`, `indicador_rendimento`, notas do SAEB, `ideb` e `projecao` têm valores ausentes (escolas sem resultado calculado por sigilo estatístico).
- `ensino` é desbalanceado (59,2% numa única categoria).

### Censo Escolar (INEP)
- ~190 colunas `IN_*` (infraestrutura) são binárias e concentradas em zero — tratar como categórica, não numérica.
- Vários campos só se aplicam a um subconjunto de escolas e por isso têm muitos ausentes (ex.: `TP_CATEGORIA_ESCOLA_PRIVADA` 80,2%, `NO_SUBDISTRITO` 99,3%) — são condicionais, não erro de preenchimento.
- `NU_ANO_CENSO` é constante (2025) em todas as linhas.
- `CO_ENTIDADE` é a chave única (código da escola).

## Como rodar

```bash
pip install -r requirements.txt
python src/ingerir_ideb.py
python src/ingerir_censo_escolar.py
python src/explorar.py
```