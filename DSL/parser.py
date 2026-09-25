"""Parser da DSL de treinos.

Este módulo cuida apenas da análise léxica/sintática. As regras de tipos,
referências, escopos e defaults ficam em :mod:`checker`.
"""

from __future__ import annotations

from pathlib import Path

from lark import Lark, Tree


DEFAULT_GRAMMAR_PATH = Path(__file__).with_name("grammar.lark")


class WorkoutParser:
    """Carrega a gramática e produz árvores Lark com posição nos nós."""

    def __init__(self, grammar_path: str | Path = DEFAULT_GRAMMAR_PATH) -> None:
        path = Path(grammar_path)
        grammar = path.read_text(encoding="utf-8")
        self._parser = Lark(
            grammar,
            parser="lalr",
            lexer="contextual",
            start="start",
            propagate_positions=True,
        )

    def parse(self, source: str) -> Tree:
        """Analisa ``source`` e devolve sua árvore sintática."""

        return self._parser.parse(source)


_default_parser: WorkoutParser | None = None


def parse_source(source: str) -> Tree:
    """Atalho que reutiliza uma instância do parser padrão."""

    global _default_parser
    if _default_parser is None:
        _default_parser = WorkoutParser()
    return _default_parser.parse(source)
