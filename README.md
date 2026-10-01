# Infraestrutura escolar e desempenho estadual no IDEB (2025)

**Autor:** Johnata Thyago Ribeiro — ECOX14

## Pergunta norteadora

Nos estados brasileiros (26 UFs e o Distrito Federal), existe associação entre a estrutura das
escolas municipais e o desempenho educacional medido pelo IDEB dos anos iniciais do ensino
fundamental em 2025?

**Nível de análise.** A Entrega 1 propunha o nível municipal. A análise principal passou a ser
por UF (27 observações): média do IDEB dos anos iniciais contra média do `indice_infraestrutura`
das escolas municipais de cada UF. A comparação mostra **associação, não causa**: UFs mais ricas
tendem a ter melhor estrutura e melhor IDEB ao mesmo tempo. A tabela por município fica prevista
como análise complementar (ver "Decisões para a integração").

## Fontes de dados

| Fonte | Formato | Acesso | Extraído | Link |
|---|---|---|---|---|
| IDEB - Anos Iniciais, Escolas 2025 | CSV | API (Base dos Dados / BigQuery) | 30/09/2026 | basedosdados.org (`br_inep_ideb.escola`) |
| Censo Escolar 2025 - Tabela_Escola | CSV | Arquivo baixado | 30/09/2026 | download.inep.gov.br/dados_abertos |
| Localidades do IBGE - Municípios | JSON | API aberta (sem chave) | 30/09/2026 | servicodados.ibge.gov.br/api/v1/localidades/municipios |

**Chaves de ligação**
- Escola: `id_escola` (IDEB) = `CO_ENTIDADE` (Censo Escolar).
- Município: `id_municipio` (IDEB) = `CO_MUNICIPIO` (Censo) = `id` (IBGE), todos com 7 dígitos.
- UF: `sigla_uf` (IDEB) e `SG_UF` (Censo).

**Por que o IBGE está no projeto.** IDEB e Censo já trazem a UF, então o IBGE não é necessário
para a junção principal. Ele entra para (1) fornecer a região (5 grupos), que permite agrupar e
controlar as 27 UFs em blocos comparáveis, e (2) conferir os códigos de município das outras duas
fontes contra uma lista oficial. **Limitação:** ele descreve um retrato, sem série temporal. A
dimensão de tempo, se necessária, viria das edições anteriores do IDEB (2005-2023), que já estão na
bronze e foram deixadas fora do recorte da pergunta.

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
- O servidor do INEP derruba a conexão durante o download do arquivo grande (visto na extração
  de 30/09/2026: `curl: (35) Recv failure`); o script usa `--retry` e retomada (`-C -`) e o ZIP
  extraiu sem erro, com as mesmas 214.192 linhas e 290 colunas da extração anterior.

### IBGE (API de Localidades)
- A resposta é um JSON aninhado (município > microrregião > mesorregião > UF > região), que
  precisa ser achatado em tabela.
- A API não pagina e não informa total. A conferência possível é: veio uma lista, com volume
  plausível (mais de 5.000 municípios) e sem `id` repetido.
- A API não informa quando a base foi atualizada; a proveniência guarda o `Date` HTTP (quando o
  servidor respondeu).

## Como rodar

```bash
pip install -r requirements.txt

# bronze
python src/ingerir_ideb.py
python src/ingerir_censo_escolar.py
python src/ingerir_ibge_municipios.py
python src/explorar.py

# prata (rode a partir da raiz do projeto: o import de limpeza depende disso)
python src/transformar_ideb.py
python src/transformar_censo_escolar.py
python src/transformar_ibge_municipios.py

# conferência da prata (sai com erro se algum invariante falhar)
python src/validar_prata.py
```

## Estrutura de `src/`

| Arquivo | Papel |
|---|---|
| `ingerir_*.py` | Bronze: baixa a fonte crua e registra proveniência |
| `explorar.py` | Perfilamento das fontes |
| `limpeza.py` | Funções de limpeza genéricas (não mencionam nenhuma fonte) |
| `transformar_*.py` | Prata: decisões específicas de cada fonte |
| `validar_prata.py` | Asserts sobre a prata, por fonte e entre fontes |

## Decisões de tratamento (camada prata)

Scripts: `src/transformar_ideb.py`, `src/transformar_censo_escolar.py` e
`src/transformar_ibge_municipios.py`. Leem a extração mais recente da bronze (que nunca é
alterada), gravam Parquet em `dados/prata/` e registram cada decisão, com números, em
`dados/prata/proveniencia.jsonl`.

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
**Volume:** 214.192 linhas (nenhuma removida); 290 colunas na bronze → 296 na prata
(+ `qt_extremo_inep`, os 4 blocos `infra_*` e `indice_infraestrutura`; − `NU_ANO_CENSO`; mais a
coluna `QT_SALAS_UTILIZADAS_extremo`).

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

### IBGE (`dados/prata/ibge_municipios.parquet`)

**Chave:** `id_municipio` (0 repetições). **Volume:** 5.571 municípios (5.570 dos estados + o Distrito Federal), 4 colunas
(`id_municipio`, `nome_municipio`, `sigla_uf`, `regiao`).

| Defeito / questão | Decisão | Números |
|---|---|---|
| JSON aninhado | Achatado em uma linha por município; UF e região lidas de microrregião > mesorregião > UF | 5.571 municípios |
| Microrregião vazia em alguns municípios | Caminho alternativo: UF lida de região imediata > região intermediária | 1 município |
| `id` como número perderia zero à esquerda | `id_municipio` lido como texto; tamanho de 7 dígitos conferido | 0 fora do tamanho |
| Região como texto livre | Tipada como categoria com 5 valores (Norte, Nordeste, Centro-Oeste, Sudeste, Sul) | 0 valores fora da lista |
| Ausentes em nome, UF e região | Conferidos | 0 ausentes |

### Consistência entre as fontes

- 63.373 das 66.138 escolas do IDEB (95,8%) aparecem no Censo pela chave `id_escola` = `CO_ENTIDADE`.
  As 2.765 sem par não têm IDEB calculado, então não afetam a análise.
- Em 46 escolas as duas fontes discordam da rede (ex.: municipal no IDEB e privada no Censo).
- `src/validar_prata.py` confere esses invariantes (chaves únicas, faixas, tipos, cobertura
  entre fontes e proveniência) e falha com código de saída 1 se algum deixar de valer.

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
  Os filtros usam o rótulo (`TP_DEPENDENCIA == "municipal"`), não o código.
- `IN_*`: Int8 (0/1 com ausente). Códigos de identificação: texto.
- `regiao` (IBGE): categoria com 5 valores.

## Decisões para a integração (próxima etapa)

- **Mesmas escolas nos dois lados.** As duas médias por UF devem usar as mesmas escolas:
  municipais (`rede = 'municipal'` no IDEB / `TP_DEPENDENCIA == "municipal"` no Censo), em
  atividade (`TP_SITUACAO_FUNCIONAMENTO == "em atividade"`) e com IDEB calculado. Sem isso,
  a média de infraestrutura e a do IDEB descreveriam grupos diferentes.
- **Média simples ou ponderada.** Uma escola pequena pesa o mesmo que uma grande na média simples.
  Calcular também a média ponderada por matrículas e comparar os resultados.
- **Poucas observações.** São 27 pontos, e uma associação entre UFs não vale para cada escola.
  Mostrar também os quatro blocos `infra_*` para ver qual associa mais.
- **Análise complementar por município.** 5.451 municípios têm ao menos uma escola municipal com
  IDEB, mas só 2.030 têm 5 ou mais; esse é o corte mínimo natural para a tabela municipal.
- **Associação não é causa.** O texto final deve dizer isso explicitamente.