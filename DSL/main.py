"""Interface de linha de comando da DSL de treinos."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from lark.exceptions import UnexpectedInput

from checker import check_tree
from parser import WorkoutParser


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analisa sintática e semanticamente um programa de treino."
    )
    parser.add_argument("arquivo", type=Path, help="arquivo fonte da DSL")
    parser.add_argument(
        "--show-symbols",
        action="store_true",
        help="exibe tabelas de símbolos e atributos herdados em JSON",
    )
    parser.add_argument(
        "--show-tree", action="store_true", help="exibe a árvore sintática do Lark"
    )
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_argument_parser().parse_args(argv)

    try:
        source = args.arquivo.read_text(encoding="utf-8")
    except OSError as error:
        print(f"erro ao ler '{args.arquivo}': {error}", file=sys.stderr)
        return 2

    try:
        tree = WorkoutParser().parse(source)
    except UnexpectedInput as error:
        print(
            f"Erro sintático na linha {error.line}, coluna {error.column}:",
            file=sys.stderr,
        )
        print(error.get_context(source, span=60).rstrip(), file=sys.stderr)
        return 1

    if args.show_tree:
        print(tree.pretty().rstrip())

    result = check_tree(tree)
    if not result.ok:
        print(f"Programa inválido: {len(result.errors)} erro(s) semântico(s).")
        for error in result.errors:
            print(f"- {error}")
        return 1

    print("Programa válido.")
    if args.show_symbols:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
