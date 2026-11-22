"""Columna 'Menciones %' del detalle por prompt: mismo valor que 'Consist.' + ✓ si cumple 2/3."""
import ast
import pathlib
import unittest

APP = pathlib.Path(__file__).resolve().parents[1] / 'app.py'
SRC = APP.read_text(encoding='utf-8')


def cell_expr():
    tree = ast.parse(SRC)
    for n in ast.walk(tree):
        if isinstance(n, ast.Dict):
            for k, v in zip(n.keys, n.values):
                if isinstance(k, ast.Constant) and k.value == 'consistency_score' and isinstance(v, (ast.JoinedStr, ast.BinOp)):
                    return v
    raise AssertionError('no encontré la celda consistency_score')


def render(score, rate):
    scope = {'CONSISTENCY_MIN_RATE': 2 / 3, 'r': {'consistency_score': score, 'mention_rate': rate}}
    return eval(compile(ast.Expression(cell_expr()), str(APP), 'eval'), scope)


class MencionesColumn(unittest.TestCase):
    def test_header_renamed_and_id_kept(self):
        self.assertIn('{"name": "Menciones %", "id": "consistency_score"}', SRC)
        self.assertNotIn('"name": "Consist."', SRC)

    def test_value_unchanged_and_check_only_at_two_thirds(self):
        for score, rate, text in [(0.0, 0.0, '0'), (33.33, 0.3333, '33'), (50.0, 0.5, '50'),
                                  (66.67, 0.6667, '67 \u2713'), (100.0, 1.0, '100 \u2713')]:
            with self.subTest(rate=rate):
                self.assertEqual(render(score, rate), text)


if __name__ == '__main__':
    unittest.main()
