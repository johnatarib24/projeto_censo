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
- 213 colunas IN_* convertidas para Int8. O código 9 ("Não informado" no dicionário do INEP)
  virou ausente: 539.938 valores em 16 colunas. Em 6 delas (IN_EDUC_AMB_*, 529.926 valores)
  o dicionário não define o 9; tratado como ausente.
- QT_*: o código 88888 ("registro com marcação de valor extremo", segundo o INEP) virou
  ausente: 10.137 valores em 26 colunas. 8.903 escolas marcadas em qt_extremo_inep.
- Todos os ausentes das IN_* (33.652) são de escolas paralisadas ou extintas.

## Como rodar

```bash
pip install -r requirements.txt
python src/ingerir_ideb.py
python src/ingerir_censo_escolar.py
python src/explorar.py
```
## Decisões de tratamento (camada prata)

Scripts: `src/transformar_ideb.py` e `src/transformar_censo_escolar.py`. Leem a extração mais
recente da bronze (que nunca é alterada), gravam Parquet em `dados/prata/` e registram cada
decisão, com números, em `dados/prata/proveniencia.jsonl`.

### IDEB (`dados/prata/ideb_escolas.parquet`)

**Chave:** `id_escola` (única após o recorte: 66.138 escolas, 0 repetições).
**Volume:** 1.300.821 linhas na bronze → 66.138 na prata.

| Defeito / questão | Decisão | Números |
|---|---|---|
| Tabela traz todas as edições e etapas | Recorte `ano = 2025` e `anos_escolares = 'iniciais (1-5)'` (recorte da pergunta, não limpeza de erro) | 1.234.683 linhas fora do recorte |
| Tipos das colunas numéricas | Conversão com `to_numeric`; o que não converte vira ausente | 0 valores perderam conteúdo |
| Valores impossíveis | Remoção só do que está fora do domínio: `ideb` fora de 0–10 e `taxa_aprovacao` fora de 0–100 | 0 linhas removidas |
| Ausentes em `ideb` (sigilo estatístico) | Mantidos e sinalizados em `ideb_disponivel`; o vazio tem significado | 23.684 escolas (35,8%) sem IDEB; 42.454 com IDEB |
| Extremos em `ideb` | Marcados, não removidos: `ideb_extremo` (IQR) e `ideb_z` (z-score > 3) | IQR: 802 (248 abaixo, 554 acima; limites 3,45 a 8,65). Z-score: 411 |
| Extremos em `taxa_aprovacao` | Marcados, não removidos: `taxa_aprovacao_extremo` e `taxa_aprovacao_z` | IQR: 3.992, todos abaixo (limites 93,25 a 104,05). Z-score: 971 |

Observação: a aprovação se concentra em 100% (mediana 99,5), então o IQR marca como extremas muitas
escolas com aprovação baixa, porém legítima (o limite superior, 104, nem é atingível). Por isso os
valores foram mantidos e os dois marcadores ficam disponíveis para sensibilidade.

### Censo Escolar (`dados/prata/censo_escolas.parquet`)

**Chave:** `CO_ENTIDADE` (0 repetições).
**Volume:** 214.192 linhas (nenhuma removida); 290 colunas na bronze → 291 na prata.

| Defeito / questão | Decisão | Números |
|---|---|---|
| Códigos lidos como número perderiam o zero à esquerda | `CO_ENTIDADE`, `CO_MUNICIPIO` e `CO_UF` lidos como texto; `CO_MUNICIPIO` com 7 dígitos, o mesmo formato de `id_municipio` do IDEB | 0 códigos com tamanho diferente de 7 |
| Colunas `IN_*` são binárias | Convertidas para `Int8` (0/1 com ausente), tratadas como categóricas | 213 colunas |
| Código `9` nas `IN_*` | `9` = "Não informado" (dicionário do INEP); vira ausente. Em 6 colunas `IN_EDUC_AMB_*` o dicionário não define o 9; também tratado como ausente | 539.938 valores em 16 colunas (529.926 nas `IN_EDUC_AMB_*`) |
| Código `88888` nas `QT_*` | Segundo o dicionário, "registro com marcação de valor extremo" feito pelo INEP; o valor real não está no arquivo. Vira ausente, e a escola fica marcada em `qt_extremo_inep` | 10.137 valores em 26 das 32 colunas `QT_*`; 8.903 escolas marcadas |
| Ausentes condicionais (`IN_*`) | Mantidos: significam "não se aplica", não erro de preenchimento. Todos os 33.652 ausentes das `IN_*` são de escolas paralisadas ou extintas | 29.780 paralisadas e 3.872 extintas |
| `NU_ANO_CENSO` constante | Conferida (todas as linhas = 2025) e removida | 1 coluna |
| Extremos em `QT_SALAS_UTILIZADAS` | Marcados por IQR em `QT_SALAS_UTILIZADAS_extremo`, mantidos | 7.602 escolas (limites −5,5 a 22,5); máximo 945 |
| Extremos em `QT_DESKTOP_ALUNO` | Não marcados: 43% das escolas têm zero, e o IQR marcaria cerca de 15% como extremo | — |

Efeito do tratamento do `88888`: em `QT_DESKTOP_ALUNO` o máximo caiu de 88.888 para 2.297 e a média
de 152 para 6,12.

### Consistência entre as fontes

- 63.373 das 66.138 escolas do IDEB (95,8%) aparecem no Censo pela chave `id_escola` = `CO_ENTIDADE`.
  As 2.765 sem par não têm IDEB calculado, então não afetam a análise.
- Em 46 escolas as duas fontes discordam da rede (ex.: municipal no IDEB e privada no Censo).

### Decisões pendentes para a integração

- Filtro de rede municipal (`rede = 'municipal'` no IDEB / `TP_DEPENDENCIA = 3` no Censo).
- Filtro de situação de funcionamento (`TP_SITUACAO_FUNCIONAMENTO = 1`, em atividade).
- Número mínimo de escolas por município para entrar na análise municipal: 5.451 municípios têm
  ao menos uma escola municipal com IDEB, mas só 2.030 têm 5 ou mais.

## Atributos derivados

### indice_infraestrutura
Fração (0 a 1) dos 25 itens de infraestrutura do Censo Escolar que a escola possui.
Serve para comparar escolas de tamanhos e tipos diferentes com uma única medida de estrutura,
que é o que a pergunta norteadora relaciona ao IDEB. Itens escolhidos pelo dicionário do INEP,
sem as colunas "inexistente", sem subconjuntos redundantes e sem o que não se aplica aos anos
iniciais. Ausente quando todos os itens são ausentes (escolas paralisadas ou extintas).

### infra_basica, infra_espacos_ensino, infra_acessibilidade, infra_tecnologia
A mesma fração, calculada por bloco (6, 7, 5 e 7 itens). Servem para ver se a associação com o
IDEB vem de um tipo específico de estrutura. Ausentes nas mesmas condições.

## Tipos
- `TP_DEPENDENCIA`, `TP_SITUACAO_FUNCIONAMENTO`, `TP_LOCALIZACAO`: categorias com os rótulos do
  dicionário do INEP (sem ordem natural). `rede` (IDEB): federal, estadual, municipal.
- `IN_*`: Int8 (0/1 com ausente). Códigos de identificação: texto.
- `regiao` (IBGE): categoria com 5 valores.