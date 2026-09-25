# DSL para prescrição de treinos

Implementação em Python e Lark com análise sintática, análise semântica,
escopos léxicos e herança de valores padrão.

## Estrutura

```text
.
├── grammar.lark             # gramática Lark/EBNF
├── parser.py                # criação e API do parser
├── checker.py               # checker, escopos e tabelas de símbolos
├── main.py                  # interface de linha de comando
├── requirements.txt
├── examples/
│   ├── valid.workout
│   ├── valid_nested_defaults.workout
│   ├── invalid_scope.workout
│   └── invalid_types.workout
└── tests/
    └── test_dsl.py
```

## Instalação e execução

Requer Python 3.10 ou mais recente.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py examples/valid.workout
```

Para visualizar a árvore sintática ou as tabelas de símbolos (incluindo os
atributos já resolvidos após a herança):

```bash
python main.py examples/valid.workout --show-tree
python main.py examples/valid_nested_defaults.workout --show-symbols
```

Um programa válido termina com código `0`; erros de sintaxe ou semântica
terminam com código `1`; falha de leitura termina com código `2`.

Os testes usam somente `unittest` da biblioteca padrão:

```bash
python -m unittest discover -s tests -v
```

## Decisões de projeto

- A gramática reconhece qualquer valor escalar (`string`, número ou `None`) nos
  atributos. Assim, `sets 2.5;` chega ao checker e produz um erro de tipo claro,
  em vez de apenas uma falha sintática genérica.
- `machines`, `personals` e workouts são tabelas globais. Máquinas e personals
  precisam aparecer textualmente antes do uso.
- Cada workout possui um escopo independente. Cada `superset` e `repeat` cria
  um escopo filho que consulta seus ancestrais, mas nunca exporta exercícios ao
  pai. Declarações são visíveis a partir do ponto em que aparecem.
- Defaults têm alcance no bloco inteiro, independentemente de sua posição
  textual. A precedência é: atributo explícito do exercício, padrão do bloco
  atual, padrão do ancestral.
- `sets` e `rest` escritos diretamente em `superset` são atributos do grupo e
  também defaults locais. Em caso de um atributo homônimo em `defaults`, o
  atributo direto do superset prevalece. Já `reps` e `rest` de `repeat`
  controlam o bloco e não são repassados aos exercícios.
- O checker acumula erros em uma passagem, permitindo corrigir vários problemas
  por execução. Cada diagnóstico contém código, linha, coluna e motivo.

## Exemplos de diagnóstico

Executar:

```bash
python main.py examples/invalid_scope.workout
```

produz uma mensagem equivalente a:

```text
Programa inválido: 1 erro(s) semântico(s).
- linha 10, coluna 14 [E_REFERENCIA]: exercício 'Crucifixo' não foi declarado anteriormente em um escopo visível
```

O arquivo `examples/invalid_types.workout` demonstra, em uma única execução,
erros de tipo, valores fora da faixa e referências não declaradas.

## API Python

```python
from parser import parse_source
from checker import check_tree

tree = parse_source('workout "A" { exercise "X" { sets 3; }; };')
result = check_tree(tree)

if result.ok:
    print(result.to_dict())
else:
    for error in result.errors:
        print(error)
```
