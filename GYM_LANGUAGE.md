# Linguagem `.gym`

## 1. Visão geral

A `.gym` é uma linguagem específica de domínio (DSL) para descrever prescrições de treino de academia de forma textual, legível e organizada. Ela permite declarar catálogos de máquinas e profissionais, treinos, exercícios, valores padrão e dois tipos de agrupamento: `superset` e `repeat`.

A implementação atual usa [Lark](https://github.com/lark-parser/lark) em duas etapas:

1. `DSL/grammar.lark` reconhece a sintaxe e produz uma árvore sintática do Lark.
2. `DSL/checker.py` percorre essa árvore, valida tipos, valores, referências e escopos e monta tabelas de símbolos.

Não se trata de uma linguagem de programação de propósito geral: não há variáveis, expressões, funções, condições, execução de exercícios, compilação ou runtime. O resultado principal do processamento atual é uma árvore sintática e, depois da validação semântica, um `CheckResult` com catálogos, treinos, escopos e exercícios declarados.

Exemplo mínimo válido:

```gym
workout "Treino A" {
    exercise "Supino reto" {
        sets 4;
        reps 10;
        rest 60;
    };
};
```

> **Extensão dos exemplos atuais:** embora esta documentação chame a DSL de `.gym`, os arquivos incluídos no repositório usam a extensão `.workout`. Nem o parser nem a gramática verificam a extensão do arquivo; eles processam o conteúdo textual recebido.

## 2. Estrutura básica de um treino

Um arquivo é formado por zero ou mais declarações globais. No escopo global são válidos `machines`, `personals` e `workout`:

```gym
machines { "Supino articulado" };
personals { "Ana" };

workout "Treino de peito" {
    defaults {
        reps 10;
        rest 60;
        personal "Ana";
        muscle "Peito";
    };

    exercise "Supino reto" {
        sets 4;
        weight 60.0;
        machine "Supino articulado";
    };
};
```

Nesse exemplo:

- `machines` declara nomes que podem ser usados pelo atributo `machine`;
- `personals` declara nomes que podem ser usados pelo atributo `personal`;
- `workout "Treino de peito"` cria um treino e seu escopo próprio;
- `defaults` define atributos herdados pelos exercícios do bloco;
- `exercise "Supino reto"` declara um exercício;
- os atributos explícitos do exercício (`sets`, `weight` e `machine`) prevalecem sobre defaults de mesmo nome;
- os atributos ausentes (`reps`, `rest`, `personal` e `muscle`) são herdados do `defaults`.

Chaves delimitam blocos. Todo atributo e toda declaração terminam obrigatoriamente com `;`, inclusive depois da chave `}`. Listas em `machines` e `personals` usam vírgulas.

Não existe uma quantidade mínima de declarações: pela gramática, até um arquivo vazio é sintaticamente e semanticamente aceito. Blocos também podem estar vazios.

## 3. Palavras-chave da linguagem

### 3.1 Declarações e blocos

| Palavra-chave | Finalidade e local válido | Sintaxe válida | Obrigatoriedade | Exemplo |
|---|---|---|---|---|
| `machines` | Declara nomes de máquinas no escopo global. Os nomes entram na tabela global na ordem em que são lidos. | `machines { STRING ("," STRING)* ","? };` ou lista vazia | Opcional | `machines { "Hack", "Cabo" };` |
| `personals` | Declara nomes de profissionais no escopo global. | `personals { STRING ("," STRING)* ","? };` ou lista vazia | Opcional | `personals { "Ana" };` |
| `workout` | Declara um treino no escopo global. O nome deve ser uma string não vazia/não composta apenas de espaços. | `workout STRING { ... };` | Opcional; o arquivo pode não ter treinos | `workout "A" { };` |
| `defaults` | Define atributos padrão para exercícios no `workout`, `superset` ou `repeat` que o contém. | `defaults { atributo* };` | Opcional | `defaults { reps 12; rest 60; };` |
| `exercise` | Declara um exercício com bloco ou referencia pelo nome um exercício já visível. É válido diretamente em `workout`, `superset` e `repeat`. | `exercise STRING { atributo* };` ou `exercise STRING;` | Opcional | `exercise "Remada" { sets 4; };` |
| `superset` | Cria um escopo filho do treino. Aceita exercícios, referências e defaults; `sets` e `rest` podem ser atributos diretos do grupo. | `superset { ... };` | Opcional | `superset { sets 3; exercise "A" { reps 10; }; };` |
| `repeat` | Cria um escopo filho do treino. `reps` controla a quantidade de repetições do grupo e `rest`, seu descanso. | `repeat { ... };` | Opcional | `repeat { reps 2; exercise "A"; };` |
| `None` | Representa ausência de valor. Semanticamente, só é válido para `machine`. | `machine None;` | Opcional | `machine None;` |

As declarações `machines`, `personals` e `workout` podem aparecer mais de uma vez. Repetir um nome já declarado produz erro semântico; vários blocos com nomes distintos são aceitos.

### 3.2 Atributos

A gramática reconhece todos os atributos abaixo com qualquer valor escalar (`STRING`, `SIGNED_NUMBER` ou `None`). É o checker semântico que restringe o tipo, a faixa e o contexto de cada um.

| Palavra-chave | Uso válido | Tipo e restrição | Obrigatória? | Exemplo válido |
|---|---|---|---|---|
| `sets` | Exercício ou `defaults`; diretamente em `superset` | Inteiro maior ou igual a 1 | Não | `sets 4;` |
| `reps` | Exercício ou `defaults`; diretamente em `repeat` | Inteiro maior ou igual a 1 | Não | `reps 12;` |
| `rest` | Exercício ou `defaults`; diretamente em `superset` ou `repeat` | Inteiro maior ou igual a 0 | Não | `rest 60;` |
| `weight` | Exercício ou `defaults` | Número inteiro ou decimal maior que 0 | Não | `weight 42.5;` |
| `machine` | Exercício ou `defaults` | String previamente declarada em `machines`, ou `None` | Não | `machine "Cabo";` |
| `personal` | Exercício ou `defaults` | String previamente declarada em `personals`; `None` não é aceito | Não | `personal "Ana";` |
| `muscle` | Exercício ou `defaults` | String | Não | `muscle "Costas";` |

Todos os atributos de um exercício são opcionais na implementação atual. Não há verificação de que um exercício resolvido possua `sets`, `reps` ou qualquer outro conjunto mínimo de propriedades.

### 3.3 Elementos lexicais

- **Strings:** usam `ESCAPED_STRING` do Lark, portanto são delimitadas por aspas duplas e admitem escapes compatíveis com a decodificação JSON usada pelo checker. Aspas simples não são aceitas.
- **Números:** usam `SIGNED_NUMBER` do Lark. Para atributos inteiros, o checker só considera inteiro o texto que corresponde a `[+-]?\d+`; assim, `2.0` e `2e0` não são aceitos em `sets`, `reps` ou `rest`, embora sejam números sintaticamente válidos.
- **Comentários:** qualquer trecho de `<` até o próximo `>` é ignorado, inclusive em várias linhas: `< comentário >`. Não há suporte específico a comentários aninhados.
- **Espaços em branco:** são ignorados; quebras de linha não têm significado estrutural.
- **Ponto e vírgula:** é obrigatório após atributos, referências e todos os blocos/declarações.

## 4. `exercise`

Existem duas formas de `exercise`.

### 4.1 Declaração

```gym
exercise "Supino reto" {
    sets 4;
    reps 10;
    rest 60;
    weight 70.5;
    machine None;
    personal "Ana";
    muscle "Peito";
};
```

A declaração cria um `ExerciseSymbol` no escopo atual. Seu nome deve ser não vazio e não pode repetir outro exercício declarado no mesmo bloco. Um exercício em escopo filho pode ter o mesmo nome de um exercício ancestral; nesse caso, a declaração local passa a ser encontrada primeiro pelas referências seguintes naquele escopo.

Somente atributos podem ficar dentro do bloco de um exercício em um programa semanticamente válido. `defaults`, outro `exercise`, `superset`, `repeat`, declarações globais e `workout` são rejeitados pelo checker.

Cada atributo pode aparecer no máximo uma vez no exercício. Os valores finais são resolvidos nesta ordem de precedência, da maior para a menor:

1. atributo explícito do exercício;
2. default do bloco atual;
3. default herdado do bloco ancestral mais próximo;
4. ausência do atributo.

### 4.2 Referência

```gym
exercise "Supino reto";
```

Essa forma não declara nem copia um exercício. Ela apenas verifica se já existe uma declaração com o mesmo nome no escopo atual ou em algum ancestral. A declaração precisa aparecer antes da referência. Referências futuras e referências a exercícios declarados em escopos filhos ou irmãos são inválidas.

No resultado serializável atual (`CheckResult.to_dict()`), referências validadas não são armazenadas: apenas declarações de exercícios aparecem na tabela `exercises`. A árvore do Lark ainda contém os nós `exercise_ref`.

## 5. `superset`

`superset` representa um agrupamento dentro de um treino e cria um escopo filho:

```gym
workout "Peito" {
    exercise "Supino reto" {
        sets 4;
        reps 10;
    };

    superset {
        sets 3;
        rest 90;

        exercise "Supino reto";
        exercise "Crucifixo" {
            reps 12;
            machine None;
        };
    };
};
```

Dentro de um `superset` válido podem existir:

- declarações e referências de `exercise`;
- um ou mais blocos `defaults`;
- `sets` e `rest` diretamente no bloco.

Os atributos diretos `sets` e `rest` são validados como propriedades estruturais do grupo e também se tornam defaults locais dos exercícios declarados no `superset`. Eles prevalecem sobre `sets` ou `rest` escritos em `defaults` no mesmo grupo. Outros atributos diretos, como `reps` e `weight`, geram `E_ATRIBUTO`.

O grupo herda os defaults do `workout`. Exercícios declarados no grupo permanecem locais e não ficam visíveis no treino pai nem em outro grupo. Exercícios já declarados no treino pai ficam visíveis dentro do grupo, desde que a declaração venha antes do `superset`.

Um `superset` só é semanticamente permitido diretamente em `workout`; grupos aninhados são rejeitados.

## 6. `repeat`

`repeat` agrupa itens que conceitualmente devem ser repetidos:

```gym
workout "Condicionamento" {
    exercise "Burpee" {
        sets 1;
        reps 10;
    };

    repeat {
        reps 3;
        rest 60;
        exercise "Burpee";
    };
};
```

Dentro de um `repeat` válido podem existir:

- declarações e referências de `exercise`;
- um ou mais blocos `defaults`;
- `reps` e `rest` diretamente no bloco.

`reps` deve ser inteiro positivo e indica a quantidade do grupo; `rest` deve ser inteiro não negativo. Nenhum deles é obrigatório. Diferentemente dos atributos diretos do `superset`, `reps` e `rest` de `repeat` **não** são herdados pelos exercícios internos. Defaults explícitos do grupo continuam sendo herdados normalmente.

O checker valida esses dois atributos estruturais, mas atualmente não os guarda no `Scope` nem na saída de `CheckResult.to_dict()`. Portanto, a árvore sintática retém `repeat.reps` e `repeat.rest`, enquanto a estrutura semântica serializada não preserva esses valores. Isso torna o suporte ao significado operacional de `repeat` parcial.

Um `repeat` só é semanticamente permitido diretamente em `workout`; grupos aninhados são rejeitados.

## 7. `circuit`

`circuit` **não está implementado**. A palavra não aparece na gramática, no parser nem no checker. Qualquer tentativa de usar `circuit { ... };` resulta em erro sintático.

Não existe, portanto, sintaxe válida, regra de agrupamento ou diferença operacional implementada entre `circuit` e os demais blocos.

## 8. Regras de aninhamento

Considerando o programa completo — gramática mais checker semântico — a estrutura válida é:

```text
arquivo / start
├── machines
├── personals
└── workout
    ├── defaults
    │   └── atributo
    ├── exercise (declaração)
    │   └── atributo
    ├── exercise (referência)
    ├── superset
    │   ├── sets / rest
    │   ├── defaults
    │   │   └── atributo
    │   ├── exercise (declaração)
    │   │   └── atributo
    │   └── exercise (referência)
    └── repeat
        ├── reps / rest
        ├── defaults
        │   └── atributo
        ├── exercise (declaração)
        │   └── atributo
        └── exercise (referência)
```

Combinações não aceitas pela implementação completa incluem:

- `machines`, `personals` ou `workout` dentro de qualquer bloco;
- atributos diretamente em `workout`;
- `defaults` dentro de `exercise` ou de outro `defaults`;
- qualquer item que não seja atributo dentro de `defaults`;
- blocos ou exercícios dentro de uma declaração de `exercise`;
- `superset` ou `repeat` dentro de `superset` ou `repeat`;
- `superset` ou `repeat` no escopo global (erro sintático);
- `circuit` em qualquer posição (erro sintático).

Há uma diferença intencional entre reconhecimento sintático e validade semântica. A regra ampla `block_item` deixa o parser reconhecer, por exemplo, `machines` dentro de `workout` ou `repeat` dentro de `superset`; depois o checker produz um erro de escopo/estrutura mais específico. Por isso, “o parser gerou uma árvore” não significa que o programa `.gym` seja válido.

### Escopos e visibilidade

- Cada `workout` cria um escopo independente.
- Cada `superset` e `repeat` cria um escopo filho.
- Uma referência procura primeiro no escopo atual e depois nos ancestrais.
- Declarações no pai são visíveis no filho somente a partir do ponto textual em que foram declaradas.
- Declarações do filho não escapam para o pai e não são visíveis em irmãos.
- Defaults, ao contrário das declarações, valem para o bloco inteiro independentemente de aparecerem antes ou depois do exercício.

## 9. Gramática Lark

A gramática atual completa de `DSL/grammar.lark` é:

```lark
// Gramática da DSL de prescrição de treinos.
//
// A gramática aceita valores escalares em todos os atributos para que erros de
// tipo sejam relatados pelo checker semântico com mensagens específicas.

start: global_statement*

?global_statement: machines_decl
                 | personals_decl
                 | workout_decl

machines_decl: "machines" "{" string_list? "}" ";"
personals_decl: "personals" "{" string_list? "}" ";"
string_list: STRING ("," STRING)* ","?

workout_decl: "workout" STRING "{" block_item* "}" ";"
superset_block: "superset" "{" block_item* "}" ";"
repeat_block: "repeat" "{" block_item* "}" ";"
defaults_block: "defaults" "{" block_item* "}" ";"

exercise_decl: "exercise" STRING "{" block_item* "}" ";"
exercise_ref: "exercise" STRING ";"

// Uma regra de item ampla permite ao checker explicar construções que são
// sintaticamente reconhecíveis, mas inválidas no contexto em que aparecem
// (por exemplo, defaults dentro de exercise ou machines dentro de workout).
?block_item: exercise_decl
           | exercise_ref
           | defaults_block
           | superset_block
           | repeat_block
           | machines_decl
           | personals_decl
           | workout_decl
           | attribute

attribute: ATTRIBUTE value ";"

?value: STRING         -> string_value
      | SIGNED_NUMBER  -> number_value
      | NONE           -> none_value

ATTRIBUTE: /(sets|reps|rest|weight|machine|personal|muscle)\b/
NONE: "None"

%import common.ESCAPED_STRING -> STRING
%import common.SIGNED_NUMBER
%import common.WS

%ignore WS
%ignore /<[\s\S]*?>/
```

Em linguagem simples:

- `start` aceita uma sequência, possivelmente vazia, de declarações globais.
- `global_statement` limita o topo do arquivo a catálogos e treinos.
- `string_list` admite zero itens quando usada pelas declarações, vários itens separados por vírgula e vírgula final opcional.
- os quatro tipos de bloco usam `{ ... }` e exigem `;` depois de `}`;
- `exercise_decl` cria uma declaração com corpo; `exercise_ref` é a forma curta sem corpo;
- `block_item` é propositalmente permissivo para permitir diagnósticos semânticos específicos;
- `attribute` associa uma das sete palavras de atributo a um valor escalar;
- os aliases `string_value`, `number_value` e `none_value` identificam o tipo de nó na árvore;
- whitespace e comentários entre `<` e `>` são descartados pelo lexer.

## 10. Como o parsing funciona

```text
Texto da DSL (`.gym` ou qualquer extensão)
                    ↓
          `DSL/grammar.lark`
                    ↓
 `WorkoutParser.parse()` / `parse_source()`
                    ↓
       `lark.Tree` com posições
                    ↓
 `SemanticChecker.check()` / `check_tree()`
                    ↓
 `CheckResult`: símbolos, escopos, atributos resolvidos e erros
```

### Componentes

1. **`DSL/parser.py`** lê `grammar.lark` ao construir `WorkoutParser` e cria um parser LALR com lexer contextual, regra inicial `start` e propagação de linha/coluna. `parse_source()` reutiliza uma instância global preguiçosa do parser.
2. **Lark** realiza análise léxica e sintática. Erros nessa etapa são `UnexpectedInput`. O resultado válido é uma `lark.Tree`; não existe um `Transformer` na implementação atual.
3. **`DSL/checker.py`** percorre a árvore. Primeiro processa declarações globais em ordem. Para cada treino, coleta defaults do bloco inteiro e então verifica os itens sequencialmente, criando escopos para grupos e símbolos para exercícios.
4. **`CheckResult`** expõe `machines`, `personals`, `workouts` e a lista agregada de `SemanticError`. A propriedade `ok` é verdadeira quando não há erros. `raise_for_errors()` opcionalmente lança `SemanticCheckError`, e `to_dict()` produz uma representação serializável.
5. **`DSL/main.py`** é uma interface de linha de comando já presente no projeto para diagnóstico: lê um arquivo, mostra opcionalmente árvore/símbolos e informa erros. Ela é uma ferramenta de acesso ao parser/checker, não um runtime da DSL.

O checker acumula múltiplos erros semânticos em uma execução. Cada erro registra código, mensagem, linha e coluna. Entre os códigos produzidos estão `E_DUPLICADO`, `E_NOME`, `E_ESTRUTURA`, `E_ESCOPO`, `E_ATRIBUTO`, `E_REFERENCIA`, `E_TIPO` e `E_VALOR`.

### Ordem das declarações globais

Máquinas e profissionais precisam ser declarados antes do treino que os referencia, porque o checker percorre o escopo global em ordem. Isto é inválido mesmo que `machines` apareça depois:

```gym
workout "A" {
    exercise "X" { machine "Cabo"; };
};
machines { "Cabo" };
```

## 11. Exemplos completos

### Exemplo 1 — treino simples

```gym
machines { "Banco livre" };
personals { "Ana" };

workout "Treino A" {
    exercise "Supino reto" {
        sets 4;
        reps 10;
        rest 60;
        weight 50.0;
        machine "Banco livre";
        personal "Ana";
        muscle "Peito";
    };

    exercise "Flexão" {
        sets 3;
        reps 12;
        rest 45;
        machine None;
        muscle "Peito";
    };
};
```

### Exemplo 2 — treino com agrupamentos

```gym
workout "Treino B" {
    defaults {
        reps 12;
        rest 60;
    };

    exercise "Agachamento livre" {
        sets 4;
        muscle "Pernas";
    };

    superset {
        sets 3;
        rest 90;

        exercise "Afundo" {
            reps 10;
            muscle "Pernas";
        };

        exercise "Panturrilha" {
            reps 15;
            muscle "Panturrilhas";
        };
    };

    repeat {
        reps 2;
        rest 120;
        exercise "Agachamento livre";
    };
};
```

### Exemplo 3 — treino com catálogos, defaults e referências

```gym
machines {
    "Cabo",
    "Remada articulada",
};

personals { "Bruna", "Caio" };

workout "Costas completo" {
    defaults {
        reps 12;
        rest 60;
        personal "Bruna";
        muscle "Costas";
    };

    exercise "Remada sentada" {
        sets 4;
        weight 45.5;
        machine "Remada articulada";
    };

    exercise "Puxada alta" {
        sets 4;
        reps 10;
        machine "Cabo";
        personal "Caio";
    };

    superset {
        sets 3;
        rest 75;
        defaults { weight 20; };

        exercise "Puxada alta";
        exercise "Pullover no cabo" {
            reps 15;
            machine "Cabo";
        };
    };

    repeat {
        reps 2;
        rest 90;
        defaults { reps 8; };
        exercise "Remada sentada";
    };
};
```

No último `repeat`, o default interno `reps 8` seria aplicado a exercícios **declarados** dentro do grupo, mas não altera o exercício ancestral apenas referenciado. A referência só é validada; ela não cria uma cópia com atributos recalculados.

## 12. Exemplos inválidos

### 12.1 Ponto e vírgula ausente — erro sintático

```gym
workout "A" {
    exercise "X" { sets 3; }
};
```

Falta `;` depois de `}` na declaração do exercício.

### 12.2 `circuit` inexistente — erro sintático

```gym
workout "A" {
    circuit {
        exercise "X" { sets 3; };
    };
};
```

`circuit` não é reconhecido pela gramática.

### 12.3 Grupo aninhado — erro semântico

```gym
workout "A" {
    superset {
        repeat { reps 2; };
    };
};
```

A gramática ampla reconhece o texto, mas o checker produz `E_ESTRUTURA`, pois `repeat` só pode estar diretamente em `workout`.

### 12.4 Referência antes da declaração — erro semântico

```gym
workout "A" {
    exercise "Futuro";
    exercise "Futuro" { sets 3; };
};
```

A primeira ocorrência é uma referência e ainda não existe uma declaração visível chamada `Futuro`; o checker produz `E_REFERENCIA`.

### 12.5 Tipos e faixas inválidos — erros semânticos

```gym
workout "A" {
    exercise "X" {
        sets 0;
        reps 10.5;
        rest -1;
        weight "pesado";
        personal None;
    };
};
```

`sets` deve ser positivo, `reps` deve ser inteiro, `rest` não pode ser negativo, `weight` deve ser numérico e `personal` deve ser string declarada.

### 12.6 Declaração global em escopo local — erro semântico

```gym
workout "A" {
    machines { "Hack" };
};
```

O parser aceita a construção para possibilitar um diagnóstico específico, mas o checker produz `E_ESCOPO`: `machines` só pode aparecer no escopo global.

## 13. Estado atual da DSL

| Funcionalidade | Status | Observação |
|---|---|---|
| Gramática Lark/LALR | Implementado | Carregada de `DSL/grammar.lark`; produz `lark.Tree` com posições. |
| `machines` | Implementado | Tabela global; permite lista vazia e vírgula final; duplicatas são rejeitadas. |
| `personals` | Implementado | Tabela global; `personal` não aceita `None`. |
| `workout` | Implementado | Escopo independente, nome não vazio e detecção de duplicatas. |
| `exercise` — declaração | Implementado | Atributos explícitos e resolvidos por herança; nenhum atributo é obrigatório. |
| `exercise` — referência | Parcial | Escopo e ordem são validados, mas a referência não é preservada em `CheckResult.to_dict()`. |
| Atributos e tipos | Implementado | Validação de contexto, tipo, faixa e duplicidade no checker. |
| `defaults` | Implementado | Herança léxica, alcance no bloco inteiro e precedência definida. |
| `superset` | Parcial | Escopo, itens e atributos são validados; `sets`/`rest` viram defaults, mas não há representação operacional separada do grupo. |
| `repeat` | Parcial | Escopo e atributos são validados, porém `reps`/`rest` estruturais não são guardados no resultado semântico serializado. |
| `circuit` | Não implementado | Não aparece na gramática ou no checker. |
| Comentários `< ... >` | Implementado | Ignorados pelo lexer, inclusive em várias linhas. |
| Mensagens semânticas agregadas | Implementado | Erros incluem código, linha, coluna e mensagem. |
| Transformer/AST de domínio completa | Não implementado | O projeto usa percurso manual da árvore e tabelas de símbolos. |
| Execução de treino/runtime | Não implementado | A DSL apenas descreve e valida; não executa o treino. |
| CLI de diagnóstico | Implementado | `DSL/main.py` já existe como invólucro do parser/checker; não constitui runtime. |
| Extensão `.gym` obrigatória | Não implementado | Os exemplos atuais usam `.workout`; o conteúdo é independente da extensão. |

## 14. Limitações atuais

- `circuit` não existe.
- `superset` e `repeat` não podem ser aninhados entre si nem neles mesmos.
- Nenhum atributo é obrigatório em `exercise`, `superset` ou `repeat`; blocos vazios são aceitos.
- Um arquivo vazio e catálogos vazios são aceitos.
- Nomes vazios ou apenas com espaços são rejeitados para `workout` e `exercise`, mas não há validação equivalente para strings de `machines` e `personals`.
- Máquinas e profissionais devem ser declarados globalmente antes do treino que os usa.
- Referências de exercício dependem da ordem textual e não podem apontar para declarações futuras.
- Referências são apenas validadas e não aparecem na representação serializada do checker.
- O checker não conserva a ordem completa dos itens do treino em `CheckResult`; ele armazena dicionários de declarações e uma lista de escopos filhos.
- Atributos estruturais de `repeat` são descartados após validação na estrutura semântica; em `superset`, `sets` e `rest` ficam apenas como defaults do escopo.
- Não existe `Transformer`, AST de domínio completa, executor, compilador ou runtime.
- A gramática aceita tipos escalares amplamente; vários erros só aparecem na análise semântica, não no parsing.
- Como `block_item` é amplo, algumas combinações estruturalmente erradas ainda geram árvore sintática e só depois são rejeitadas.
- Ao encontrar um grupo aninhado inválido, o checker relata o grupo, mas não percorre semanticamente o conteúdo desse grupo inválido.
- A saída `to_dict()` inclui valores resolvidos, mas não oferece uma representação executável da sequência de exercícios/grupos.

## 15. Arquivos importantes do projeto

```text
DSL-GymLang/
├── GYM_LANGUAGE.md
└── DSL/
    ├── grammar.lark
    ├── parser.py
    ├── checker.py
    ├── main.py
    ├── README.md
    ├── requirements.txt
    ├── examples/
    │   ├── valid.workout
    │   ├── valid_nested_defaults.workout
    │   ├── invalid_scope.workout
    │   └── invalid_types.workout
    └── tests/
        └── test_dsl.py
```

- **`DSL/grammar.lark`** — fonte da sintaxe: declarações, blocos, atributos, escalares, whitespace e comentários.
- **`DSL/parser.py`** — carrega a gramática e oferece `WorkoutParser.parse()` e `parse_source()`.
- **`DSL/checker.py`** — implementa validação semântica, escopos léxicos, tabelas de símbolos, herança de defaults, resolução de atributos e diagnósticos.
- **`DSL/main.py`** — utilitário de linha de comando existente para ler um arquivo, executar parser/checker e mostrar árvore, símbolos ou erros.
- **`DSL/tests/test_dsl.py`** — testes da implementação atual: programa completo, defaults aninhados, atributos de `superset`, visibilidade, ordem de referências, tipos e escopos inválidos.
- **`DSL/examples/valid.workout`** — exemplo válido com catálogos, defaults, exercícios, `superset` e `repeat`.
- **`DSL/examples/valid_nested_defaults.workout`** — exemplo de herança e sobrescrita de defaults.
- **`DSL/examples/invalid_scope.workout`** — demonstra que uma declaração do escopo filho não fica visível no pai.
- **`DSL/examples/invalid_types.workout`** — reúne erros de tipo, faixa e referências globais.
- **`DSL/README.md`** — instruções atuais de instalação, execução, API e decisões de projeto.
- **`DSL/requirements.txt`** — fixa a dependência do Lark na faixa `>=1.1,<2`.

Esta documentação descreve exclusivamente o comportamento observado na gramática e no código atuais. Menções conceituais a recursos futuros não devem ser interpretadas como sintaxe suportada.
