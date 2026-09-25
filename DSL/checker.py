"""Análise semântica e tabelas de símbolos da DSL de treinos."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Iterable

from lark import Token, Tree


EXERCISE_ATTRIBUTES = {
    "sets",
    "reps",
    "rest",
    "weight",
    "machine",
    "personal",
    "muscle",
}
SUPERSET_ATTRIBUTES = {"sets", "rest"}
REPEAT_ATTRIBUTES = {"reps", "rest"}
INTEGER_RE = re.compile(r"^[+-]?\d+$")


@dataclass(frozen=True)
class SemanticError:
    """Um erro semântico com código, posição e mensagem legível."""

    code: str
    message: str
    line: int
    column: int

    def __str__(self) -> str:
        return f"linha {self.line}, coluna {self.column} [{self.code}]: {self.message}"


class SemanticCheckError(Exception):
    """Exceção agregada opcional para clientes que preferem falhar rápido."""

    def __init__(self, errors: Iterable[SemanticError]) -> None:
        self.errors = list(errors)
        super().__init__("\n".join(str(error) for error in self.errors))


@dataclass(frozen=True)
class Value:
    """Valor da DSL acompanhado de seu local de origem."""

    value: str | int | float | None
    kind: str
    line: int
    column: int


@dataclass
class ExerciseSymbol:
    name: str
    line: int
    explicit_attributes: dict[str, Value]
    resolved_attributes: dict[str, Value]


@dataclass
class Scope:
    """Tabela de símbolos de exercícios para um bloco léxico."""

    label: str
    kind: str
    line: int
    parent: Scope | None = None
    defaults: dict[str, Value] = field(default_factory=dict)
    exercises: dict[str, ExerciseSymbol] = field(default_factory=dict)
    children: list[Scope] = field(default_factory=list)

    def lookup_exercise(self, name: str) -> ExerciseSymbol | None:
        """Procura no escopo atual e, depois, nos ancestrais."""

        scope: Scope | None = self
        while scope is not None:
            symbol = scope.exercises.get(name)
            if symbol is not None:
                return symbol
            scope = scope.parent
        return None


@dataclass
class WorkoutSymbol:
    name: str
    line: int
    scope: Scope


@dataclass
class CheckResult:
    machines: dict[str, int]
    personals: dict[str, int]
    workouts: dict[str, WorkoutSymbol]
    errors: list[SemanticError]

    @property
    def ok(self) -> bool:
        return not self.errors

    def raise_for_errors(self) -> None:
        if self.errors:
            raise SemanticCheckError(self.errors)

    def to_dict(self) -> dict[str, Any]:
        """Representação serializável das tabelas e atributos resolvidos."""

        return {
            "machines": sorted(self.machines),
            "personals": sorted(self.personals),
            "workouts": {
                name: {
                    "line": workout.line,
                    "scope": _scope_to_dict(workout.scope),
                }
                for name, workout in self.workouts.items()
            },
            "errors": [str(error) for error in self.errors],
        }


def _scope_to_dict(scope: Scope) -> dict[str, Any]:
    return {
        "kind": scope.kind,
        "label": scope.label,
        "line": scope.line,
        "defaults": {
            name: value.value for name, value in scope.defaults.items()
        },
        "exercises": {
            name: {
                "line": symbol.line,
                "explicit": {
                    key: value.value
                    for key, value in symbol.explicit_attributes.items()
                },
                "resolved": {
                    key: value.value
                    for key, value in symbol.resolved_attributes.items()
                },
            }
            for name, symbol in scope.exercises.items()
        },
        "children": [_scope_to_dict(child) for child in scope.children],
    }


class SemanticChecker:
    """Percorre uma árvore Lark e aplica as regras semânticas da DSL."""

    def __init__(self) -> None:
        self.machines: dict[str, int] = {}
        self.personals: dict[str, int] = {}
        self.workouts: dict[str, WorkoutSymbol] = {}
        self.errors: list[SemanticError] = []
        self._block_counts = {"superset": 0, "repeat": 0}

    def check(self, tree: Tree) -> CheckResult:
        """Verifica ``tree`` e retorna símbolos e todos os erros encontrados."""

        self.machines = {}
        self.personals = {}
        self.workouts = {}
        self.errors = []
        self._block_counts = {"superset": 0, "repeat": 0}

        if tree.data != "start":
            self._error("E_INTERNO", tree, "a árvore não começa pela regra 'start'")
        else:
            for statement in self._trees(tree.children):
                if statement.data == "machines_decl":
                    self._declare_string_symbols(statement, "machine")
                elif statement.data == "personals_decl":
                    self._declare_string_symbols(statement, "personal")
                elif statement.data == "workout_decl":
                    self._check_workout(statement)
                else:
                    self._error(
                        "E_ESTRUTURA",
                        statement,
                        f"'{statement.data}' não é permitido no escopo global",
                    )

        return CheckResult(
            machines=dict(self.machines),
            personals=dict(self.personals),
            workouts=dict(self.workouts),
            errors=list(self.errors),
        )

    @staticmethod
    def _trees(children: Iterable[Tree | Token]) -> Iterable[Tree]:
        return (child for child in children if isinstance(child, Tree))

    @staticmethod
    def _position(node: Tree | Token) -> tuple[int, int]:
        if isinstance(node, Token):
            return int(node.line or 1), int(node.column or 1)
        return int(getattr(node.meta, "line", 1)), int(
            getattr(node.meta, "column", 1)
        )

    def _error(self, code: str, node: Tree | Token, message: str) -> None:
        line, column = self._position(node)
        self.errors.append(SemanticError(code, message, line, column))

    @staticmethod
    def _decode_string(token: Token) -> str:
        return json.loads(str(token))

    def _first_string(self, tree: Tree) -> tuple[str, Token]:
        token = next(
            child
            for child in tree.children
            if isinstance(child, Token) and child.type == "STRING"
        )
        return self._decode_string(token), token

    def _declare_string_symbols(self, tree: Tree, symbol_kind: str) -> None:
        table = self.machines if symbol_kind == "machine" else self.personals
        singular = "máquina" if symbol_kind == "machine" else "personal"

        for child in self._trees(tree.children):
            if child.data != "string_list":
                continue
            for token in child.children:
                if not isinstance(token, Token) or token.type != "STRING":
                    continue
                name = self._decode_string(token)
                if name in table:
                    self._error(
                        "E_DUPLICADO",
                        token,
                        f"{singular} '{name}' já foi declarado na linha {table[name]}",
                    )
                else:
                    table[name] = int(token.line or 1)

    def _check_workout(self, tree: Tree) -> None:
        name, name_token = self._first_string(tree)
        if not name.strip():
            self._error("E_NOME", name_token, "workout deve possuir nome não vazio")
        if name in self.workouts:
            previous = self.workouts[name]
            self._error(
                "E_DUPLICADO",
                name_token,
                f"workout '{name}' já foi declarado na linha {previous.line}",
            )

        line, _ = self._position(tree)
        scope = Scope(label=name, kind="workout", line=line)
        items = list(self._trees(tree.children))
        scope.defaults = self._collect_defaults(items, {}, "workout")
        self._check_block_items(items, scope, "workout")

        if name not in self.workouts:
            self.workouts[name] = WorkoutSymbol(name=name, line=line, scope=scope)

    def _collect_defaults(
        self,
        items: list[Tree],
        inherited: dict[str, Value],
        owner_kind: str,
    ) -> dict[str, Value]:
        """Mescla defaults do bloco; sua posição textual não muda o alcance."""

        merged = dict(inherited)
        local_names: dict[str, Value] = {}
        for defaults in (item for item in items if item.data == "defaults_block"):
            for child in self._trees(defaults.children):
                if child.data != "attribute":
                    self._error(
                        "E_ESTRUTURA",
                        child,
                        f"somente atributos são permitidos em defaults de {owner_kind}",
                    )
                    continue
                name, value = self._read_attribute(child)
                if name not in EXERCISE_ATTRIBUTES:
                    self._error(
                        "E_ATRIBUTO",
                        child,
                        f"atributo '{name}' não é permitido em defaults",
                    )
                    continue
                if name in local_names:
                    self._error(
                        "E_DUPLICADO",
                        child,
                        f"atributo '{name}' aparece mais de uma vez nos defaults deste bloco",
                    )
                    continue
                local_names[name] = value
                self._validate_exercise_attribute(name, value)
        merged.update(local_names)
        return merged

    def _check_block_items(
        self, items: list[Tree], scope: Scope, owner_kind: str
    ) -> None:
        for item in items:
            if item.data == "defaults_block":
                continue
            if item.data == "exercise_decl":
                self._check_exercise_decl(item, scope)
            elif item.data == "exercise_ref":
                self._check_exercise_ref(item, scope)
            elif item.data == "superset_block":
                if owner_kind != "workout":
                    self._error(
                        "E_ESTRUTURA",
                        item,
                        f"superset não é permitido dentro de {owner_kind}",
                    )
                else:
                    self._check_superset(item, scope)
            elif item.data == "repeat_block":
                if owner_kind != "workout":
                    self._error(
                        "E_ESTRUTURA",
                        item,
                        f"repeat não é permitido dentro de {owner_kind}",
                    )
                else:
                    self._check_repeat(item, scope)
            elif item.data in {"machines_decl", "personals_decl"}:
                keyword = "machines" if item.data == "machines_decl" else "personals"
                self._error(
                    "E_ESCOPO",
                    item,
                    f"'{keyword}' só pode aparecer no escopo global",
                )
            elif item.data == "workout_decl":
                self._error(
                    "E_ESCOPO", item, "'workout' só pode aparecer no escopo global"
                )
            elif item.data == "attribute":
                name, _ = self._read_attribute(item)
                self._error(
                    "E_ATRIBUTO",
                    item,
                    f"atributo '{name}' não é permitido diretamente em {owner_kind}",
                )
            else:
                self._error(
                    "E_ESTRUTURA",
                    item,
                    f"construção '{item.data}' não é permitida em {owner_kind}",
                )

    def _check_exercise_decl(self, tree: Tree, scope: Scope) -> None:
        name, name_token = self._first_string(tree)
        if not name.strip():
            self._error("E_NOME", name_token, "exercise deve possuir nome não vazio")

        explicit: dict[str, Value] = {}
        for item in self._trees(tree.children):
            if item.data == "attribute":
                attr_name, value = self._read_attribute(item)
                if attr_name in explicit:
                    self._error(
                        "E_DUPLICADO",
                        item,
                        f"atributo '{attr_name}' aparece mais de uma vez no exercício '{name}'",
                    )
                    continue
                explicit[attr_name] = value
                self._validate_exercise_attribute(attr_name, value)
            elif item.data == "defaults_block":
                self._error(
                    "E_ESCOPO",
                    item,
                    f"defaults não pode aparecer dentro do exercício '{name}'",
                )
            else:
                self._error(
                    "E_ESTRUTURA",
                    item,
                    f"'{item.data}' não é permitido dentro do exercício '{name}'",
                )

        if name in scope.exercises:
            previous = scope.exercises[name]
            self._error(
                "E_DUPLICADO",
                name_token,
                f"exercício '{name}' já foi declarado neste bloco na linha {previous.line}",
            )
            return

        resolved = dict(scope.defaults)
        resolved.update(explicit)
        line, _ = self._position(tree)
        scope.exercises[name] = ExerciseSymbol(
            name=name,
            line=line,
            explicit_attributes=explicit,
            resolved_attributes=resolved,
        )

    def _check_exercise_ref(self, tree: Tree, scope: Scope) -> None:
        name, token = self._first_string(tree)
        if not name.strip():
            self._error("E_NOME", token, "referência de exercise deve possuir nome não vazio")
            return
        if scope.lookup_exercise(name) is None:
            self._error(
                "E_REFERENCIA",
                token,
                f"exercício '{name}' não foi declarado anteriormente em um escopo visível",
            )

    def _check_superset(self, tree: Tree, parent: Scope) -> None:
        self._block_counts["superset"] += 1
        number = self._block_counts["superset"]
        line, _ = self._position(tree)
        scope = Scope(
            label=f"superset#{number}", kind="superset", line=line, parent=parent
        )
        parent.children.append(scope)
        items = list(self._trees(tree.children))

        # sets/rest declarados diretamente no superset são atributos do grupo e
        # também defaults locais para os seus exercícios.
        structural = self._collect_structural_attributes(
            items, SUPERSET_ATTRIBUTES, "superset"
        )
        scope.defaults = self._collect_defaults(
            items, parent.defaults, "superset"
        )
        scope.defaults.update(structural)

        nested_items = [item for item in items if item.data != "attribute"]
        self._check_block_items(nested_items, scope, "superset")

    def _check_repeat(self, tree: Tree, parent: Scope) -> None:
        self._block_counts["repeat"] += 1
        number = self._block_counts["repeat"]
        line, _ = self._position(tree)
        scope = Scope(label=f"repeat#{number}", kind="repeat", line=line, parent=parent)
        parent.children.append(scope)
        items = list(self._trees(tree.children))

        # reps/rest do repeat controlam a repetição e não viram atributos dos
        # exercícios. Defaults explícitos continuam herdando do bloco externo.
        self._collect_structural_attributes(items, REPEAT_ATTRIBUTES, "repeat")
        scope.defaults = self._collect_defaults(items, parent.defaults, "repeat")

        nested_items = [item for item in items if item.data != "attribute"]
        self._check_block_items(nested_items, scope, "repeat")

    def _collect_structural_attributes(
        self, items: list[Tree], allowed: set[str], owner_kind: str
    ) -> dict[str, Value]:
        result: dict[str, Value] = {}
        for item in (candidate for candidate in items if candidate.data == "attribute"):
            name, value = self._read_attribute(item)
            if name not in allowed:
                self._error(
                    "E_ATRIBUTO",
                    item,
                    f"atributo '{name}' não é permitido diretamente em {owner_kind}",
                )
                continue
            if name in result:
                self._error(
                    "E_DUPLICADO",
                    item,
                    f"atributo '{name}' aparece mais de uma vez em {owner_kind}",
                )
                continue
            result[name] = value
            self._validate_structural_attribute(owner_kind, name, value)
        return result

    def _read_attribute(self, tree: Tree) -> tuple[str, Value]:
        name_token = next(
            child
            for child in tree.children
            if isinstance(child, Token) and child.type == "ATTRIBUTE"
        )
        value_tree = next(child for child in self._trees(tree.children))
        value_token = next(
            child for child in value_tree.children if isinstance(child, Token)
        )

        if value_tree.data == "string_value":
            value = Value(
                self._decode_string(value_token),
                "string",
                int(value_token.line or 1),
                int(value_token.column or 1),
            )
        elif value_tree.data == "none_value":
            value = Value(
                None,
                "none",
                int(value_token.line or 1),
                int(value_token.column or 1),
            )
        else:
            raw = str(value_token)
            parsed: int | float
            if INTEGER_RE.fullmatch(raw):
                parsed = int(raw)
                kind = "integer"
            else:
                parsed = float(raw)
                kind = "number"
            value = Value(
                parsed,
                kind,
                int(value_token.line or 1),
                int(value_token.column or 1),
            )
        return str(name_token), value

    def _validate_exercise_attribute(self, name: str, value: Value) -> None:
        if name in {"sets", "reps"}:
            self._require_integer(name, value, minimum=1)
        elif name == "rest":
            self._require_integer(name, value, minimum=0)
        elif name == "weight":
            if value.kind not in {"integer", "number"}:
                self._type_error(name, value, "número inteiro ou decimal positivo")
            elif value.value is None or value.value <= 0:
                self._error(
                    "E_VALOR",
                    self._value_token_proxy(value),
                    f"'{name}' deve ser positivo; recebido {value.value!r}",
                )
        elif name == "machine":
            if value.kind not in {"string", "none"}:
                self._type_error(name, value, "string ou None")
            elif value.kind == "string" and value.value not in self.machines:
                self._error(
                    "E_REFERENCIA",
                    self._value_token_proxy(value),
                    f"máquina '{value.value}' não foi declarada anteriormente em machines",
                )
        elif name == "personal":
            if value.kind != "string":
                self._type_error(name, value, "string")
            elif value.value not in self.personals:
                self._error(
                    "E_REFERENCIA",
                    self._value_token_proxy(value),
                    f"personal '{value.value}' não foi declarado anteriormente em personals",
                )
        elif name == "muscle" and value.kind != "string":
            self._type_error(name, value, "string")

    def _validate_structural_attribute(
        self, owner_kind: str, name: str, value: Value
    ) -> None:
        if name in {"sets", "reps"}:
            self._require_integer(f"{owner_kind}.{name}", value, minimum=1)
        else:
            self._require_integer(f"{owner_kind}.{name}", value, minimum=0)

    def _require_integer(self, name: str, value: Value, minimum: int) -> None:
        if value.kind != "integer":
            requirement = "inteiro positivo" if minimum == 1 else "inteiro não negativo"
            self._type_error(name, value, requirement)
        elif value.value is None or value.value < minimum:
            requirement = "positivo" if minimum == 1 else "não negativo"
            self._error(
                "E_VALOR",
                self._value_token_proxy(value),
                f"'{name}' deve ser {requirement}; recebido {value.value!r}",
            )

    def _type_error(self, name: str, value: Value, expected: str) -> None:
        shown = "None" if value.kind == "none" else repr(value.value)
        self._error(
            "E_TIPO",
            self._value_token_proxy(value),
            f"'{name}' deve receber {expected}; recebido {shown}",
        )

    @staticmethod
    def _value_token_proxy(value: Value) -> Token:
        """Cria um Token leve apenas para reaproveitar o tratamento de posição."""

        token = Token("VALUE", "")
        token.line = value.line
        token.column = value.column
        return token


def check_tree(tree: Tree, *, raise_on_error: bool = False) -> CheckResult:
    """API funcional do checker."""

    result = SemanticChecker().check(tree)
    if raise_on_error:
        result.raise_for_errors()
    return result
