from __future__ import annotations

import unittest

from checker import SemanticChecker
from parser import parse_source


def check(source: str):
    return SemanticChecker().check(parse_source(source))


class DSLTests(unittest.TestCase):
    def test_complete_valid_program(self) -> None:
        result = check(
            r'''
            machines { "Supino", "Hack" };
            personals { "Junior", "Caio" };
            workout "Treino A" {
                < comentário em
                  mais de uma linha >
                defaults {
                    reps 20;
                    personal "Junior";
                    muscle "Peito";
                };
                exercise "Supino Reto" {
                    sets 4;
                    rest 20;
                    weight 60.0;
                    machine "Supino";
                    personal "Caio";
                };
                exercise "Agachamento" {
                    sets 3;
                    reps 12;
                    rest 90;
                    machine None;
                };
                superset {
                    sets 3;
                    rest 90;
                    exercise "Supino Reto";
                    exercise "Crucifixo" {
                        reps 12;
                        machine None;
                    };
                };
                repeat {
                    reps 2;
                    rest 60;
                    exercise "Supino Reto";
                };
            };
            '''
        )
        self.assertTrue(result.ok, [str(error) for error in result.errors])

    def test_defaults_follow_lexical_hierarchy(self) -> None:
        result = check(
            '''
            workout "A" {
                defaults { reps 12; rest 60; muscle "Peito"; };
                superset {
                    defaults { rest 90; };
                    exercise "Supino" { sets 4; reps 10; };
                };
            };
            '''
        )
        self.assertTrue(result.ok, [str(error) for error in result.errors])
        child = result.workouts["A"].scope.children[0]
        attrs = child.exercises["Supino"].resolved_attributes
        self.assertEqual(attrs["sets"].value, 4)
        self.assertEqual(attrs["reps"].value, 10)
        self.assertEqual(attrs["rest"].value, 90)
        self.assertEqual(attrs["muscle"].value, "Peito")

    def test_superset_fields_are_local_defaults(self) -> None:
        result = check(
            '''
            workout "A" {
                superset {
                    sets 3;
                    rest 90;
                    exercise "Novo" { reps 12; };
                };
            };
            '''
        )
        self.assertTrue(result.ok, [str(error) for error in result.errors])
        attrs = result.workouts["A"].scope.children[0].exercises[
            "Novo"
        ].resolved_attributes
        self.assertEqual(attrs["sets"].value, 3)
        self.assertEqual(attrs["rest"].value, 90)

    def test_child_declaration_does_not_escape(self) -> None:
        result = check(
            '''
            workout "A" {
                superset { exercise "Local" { sets 3; }; };
                exercise "Local";
            };
            '''
        )
        self.assertFalse(result.ok)
        self.assertIn("E_REFERENCIA", {error.code for error in result.errors})

    def test_parent_declaration_is_visible_in_children(self) -> None:
        result = check(
            '''
            workout "A" {
                exercise "Base" { sets 3; };
                repeat { reps 2; exercise "Base"; };
            };
            '''
        )
        self.assertTrue(result.ok, [str(error) for error in result.errors])

    def test_reference_must_follow_declaration(self) -> None:
        result = check(
            '''
            workout "A" {
                exercise "Futuro";
                exercise "Futuro" { sets 3; };
            };
            '''
        )
        self.assertEqual([error.code for error in result.errors], ["E_REFERENCIA"])

    def test_type_value_and_global_reference_errors_are_aggregated(self) -> None:
        result = check(
            '''
            workout "A" {
                exercise "X" {
                    sets 0;
                    reps 2.5;
                    rest -1;
                    weight "muito";
                    machine "Fantasma";
                    personal None;
                    muscle 42;
                };
            };
            '''
        )
        codes = [error.code for error in result.errors]
        self.assertEqual(codes.count("E_VALOR"), 2)
        self.assertEqual(codes.count("E_TIPO"), 4)
        self.assertEqual(codes.count("E_REFERENCIA"), 1)

    def test_global_declarations_inside_workout_are_rejected(self) -> None:
        result = check(
            '''
            workout "A" {
                machines { "Hack" };
                personals { "Ana" };
            };
            '''
        )
        self.assertEqual([error.code for error in result.errors], ["E_ESCOPO", "E_ESCOPO"])

    def test_defaults_inside_exercise_are_rejected(self) -> None:
        result = check(
            '''
            workout "A" {
                exercise "X" { defaults { reps 10; }; };
            };
            '''
        )
        self.assertEqual([error.code for error in result.errors], ["E_ESCOPO"])


if __name__ == "__main__":
    unittest.main()
