# Infraestrutura escolar e desempenho estadual no IDEB (2025)

**Autor:** Johnata Thyago Ribeiro — ECOX14

## Pergunta norteadora

Nos estados brasileiros (26 UFs), existe associação entre a estrutura das escolas municipais e o
desempenho educacional medido pelo IDEB dos anos iniciais do ensino fundamental em 2025?

**Nível de análise.** A Entrega 1 propunha o nível municipal. A análise principal passou a ser
por UF (26 observações): média do IDEB dos anos iniciais contra média do `indice_infraestrutura`
das escolas municipais de cada UF. A comparação mostra **associação, não causa**: UFs mais ricas
tendem a ter melhor estrutura e melhor IDEB ao mesmo tempo. A tabela por município fica prevista
como análise complementar (ver "Decisões para a integração").

**O Distrito Federal fica de fora.** A pergunta é sobre escolas municipais, e o DF não tem rede
municipal: suas 335 escolas com IDEB aparecem como `estadual`. Por isso a análise cobre 26 UFs,
e não 27.

## Fontes de dados

| Fonte | Formato | Acesso | Extraído | Link |
|---|---|---|---|---|
| IDEB - Anos Iniciais, Escolas 2025 | CSV | API (Base dos Dados / BigQuery) | 30/09/2026 | basedosdados.org (`br_inep_ideb.escola`) |
| Censo Escolar 2025 - Tabela_Escola | CSV | Arquivo baixado | 30/09/2026 | download.inep.gov.br/dados_abertos |

**Chaves de ligação**
- Escola: `id_escola` (IDEB) = `CO_ENTIDADE` (Censo Escolar).
- Município: `id_municipio` (IDEB) = `CO_MUNICIPIO` (Censo), com 7 dígitos.
- UF: `sigla_uf` (IDEB) e `SG_UF` (Censo).

**Fonte retirada: IBGE (Localidades).** Ela entraria só para fornecer a região (5 grupos) e para
conferir os códigos de município. Como IDEB e Censo já trazem UF e município, e a análise principal
é por UF, a fonte foi retirada do projeto. A linha dela em `dados/prata/proveniencia.jsonl` é
registro histórico da primeira versão da prata.

**Limitação de tempo.** As duas fontes descrevem 2025, sem série temporal. A dimensão de tempo, se
necessária, viria das edições anteriores do IDEB (2005-2023), que já estão na bronze e foram
deixadas fora do recorte da pergunta.

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

## Como rodar

```bash
pip install -r requirements.txt

# pipeline inteiro (de qualquer pasta)
python src/pipeline.py

# a partir de uma etapa: ingestao, transformacao, enriquecimento
python src/pipeline.py transformacao

# conferência da prata (sai com erro se algum invariante falhar)
python src/validar_prata.py

# perfilamento das fontes (fora do pipeline: gera HTML em relatorios/)
python src/explorar.py
```

Cada script também roda sozinho (`python src/transformar_ideb.py`, por exemplo). Como os caminhos
saem de `src/config.py`, não importa de qual pasta o comando é dado.

A ingestão do IDEB abre uma janela de login do Google na primeira vez, e o download do Censo é
demorado. Se a ingestão já foi feita, retome de `transformacao` para não baixar tudo de novo.

**Log.** Cada execução escreve na tela e em `pipeline.log` (ignorado pelo Git), com hora, nível e
módulo. `INFO` registra o andamento, `WARNING` o que é estranho mas seguiu (ex.: valores fora da
faixa removidos) e `ERROR` uma etapa que falhou; nesse caso o pipeline para, com o erro completo
no log.

**Etapas sem função ainda.** `carga` e `modelagem` aparecem como "puladas" no log: são as próximas
etapas do pipeline.

## Estrutura de `src/`

| Arquivo | Papel |
|---|---|
| `config.py` | Caminhos, parâmetros (ano, recorte, URL) e configuração do log. Não importa nenhum outro módulo do projeto |
| `pipeline.py` | Ponto de entrada: roda as etapas em ordem, ou a partir de uma delas |
| `ingerir_*.py` | Bronze: baixa a fonte crua e registra proveniência |
| `explorar.py` | Perfilamento das fontes |
| `limpeza.py` | Funções de limpeza genéricas (não mencionam nenhuma fonte) |
| `transformar_*.py` | Prata: decisões específicas de cada fonte |
| `enriquecer.py` | Prata: junção do IDEB com o Censo e atributos que só existem depois dela |
| `validar_prata.py` | Asserts sobre a prata, por fonte e entre fontes |

Quem importa quem: `pipeline` chama as etapas; as etapas usam `limpeza` e `config`; `limpeza`
não conhece nenhuma etapa; `config` não importa ninguém. A seta nunca volta.

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

### Consistência entre as fontes

- 63.373 das 66.138 escolas do IDEB (95,8%) aparecem no Censo pela chave `id_escola` = `CO_ENTIDADE`.
  As 2.765 sem par não têm IDEB calculado, então não afetam a análise.
- Em 46 escolas as duas fontes discordam da rede (ex.: municipal no IDEB e privada no Censo).
- `src/validar_prata.py` confere esses invariantes (chaves únicas, faixas, tipos, cobertura
  entre fontes e proveniência) e falha com código de saída 1 se algum deixar de valer.

## Enriquecimento (`src/enriquecer.py`)

Saída: `dados/prata/ideb_censo_enriquecido.parquet`.
**Grão:** uma linha por escola do IDEB (anos iniciais, 2025). O resultado precisa ter as mesmas
66.138 linhas da tabela do IDEB.

**Junção:** IDEB (esquerda) com Censo (direita), por `id_escola = CO_ENTIDADE`, `how="left"` e
`validate="one_to_one"`. O `left` parte do IDEB porque a pergunta é sobre escolas com IDEB; antes
da junção, o script reduz o Censo às colunas que interessam (tipo de rede, situação, localização,
índices de infraestrutura e `qt_extremo_inep`).

| Conferência | Resultado |
|---|---|
| Linhas no IDEB | 66.138 |
| Linhas após a junção | 66.138 |
| IDEB sem par no Censo | 2.765 |

### Quem não casou

As 2.765 escolas do IDEB sem par no Censo são 1.597 municipais e 1.168 estaduais (nenhuma
federal). Todas estão sem IDEB calculado (0 com IDEB), então saem da análise de qualquer forma e
nenhuma escola com IDEB se perdeu na junção.

### Discordâncias entre as fontes

Entre as escolas que casaram: 0 com UF diferente, 0 com município diferente e 46 com rede
diferente (as mesmas 46 já registradas na prata).

### Atributos que só existem depois da junção

- `na_analise`: verdadeiro para escolas municipais (`rede` no IDEB e `TP_DEPENDENCIA` no Censo),
  em atividade, com IDEB calculado e com `indice_infraestrutura`. Garante as mesmas escolas nos
  dois lados da comparação. São **36.731 escolas em 26 UFs**. De 51.733 escolas municipais no IDEB,
  36.731 têm IDEB; nenhum dos outros critérios elimina escola adicional. O menor grupo é RR, com 105
  escolas.
- `infra_dif_mediana_uf`: índice de infraestrutura da escola menos a mediana da sua UF, entre as
  escolas de `na_analise`. Só existe depois da junção porque o índice vem do Censo.
- `ideb_dif_mediana_uf`: IDEB da escola menos a mediana da sua UF, também entre as escolas de
  `na_analise`. Mostra se a escola está acima ou abaixo do padrão do próprio estado, que é a
  unidade da pergunta. Fica vazio nas escolas do DF (335 com IDEB), que não entram na análise.

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

### na_analise, infra_dif_mediana_uf, ideb_dif_mediana_uf
Ver "Atributos que só existem depois da junção".

## Tipos
- `TP_DEPENDENCIA`, `TP_SITUACAO_FUNCIONAMENTO`, `TP_LOCALIZACAO`: categorias com os rótulos do
  dicionário do INEP (sem ordem natural). `rede` (IDEB): federal, estadual, municipal.
  Os filtros usam o rótulo (`TP_DEPENDENCIA == "municipal"`), não o código.
- `IN_*`: Int8 (0/1 com ausente). Códigos de identificação: texto.

## Decisões para a integração (próxima etapa)

- **Mesmas escolas nos dois lados.** As duas médias por UF devem usar as mesmas escolas, e isso já
  está pronto na coluna `na_analise` (municipais, em atividade, com IDEB). Sem isso, a média de
  infraestrutura e a do IDEB descreveriam grupos diferentes.
- **Média simples ou ponderada.** Uma escola pequena pesa o mesmo que uma grande na média simples.
  A ideia era calcular também a média ponderada por matrículas, mas a tabela enriquecida não traz
  coluna de matrículas (a `QT_MAT_FUND_AI` não existe na prata do Censo). Decisão: usar a média
  simples; se uma coluna de matrículas estiver disponível na hora da integração, calcular a
  ponderada como sensibilidade.
- **Poucas observações.** São 26 pontos, e uma associação entre UFs não vale para cada escola.
  Mostrar também os quatro blocos `infra_*` para ver qual associa mais.
- **Análise complementar por município.** 5.451 municípios têm ao menos uma escola municipal com
  IDEB, mas só 2.030 têm 5 ou mais; esse é o corte mínimo natural para a tabela municipal.
- **Associação não é causa.** O texto final deve dizer isso explicitamente.
