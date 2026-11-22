"""País = "Todos": la vista usa la corrida más reciente de CADA país, no solo el último batch."""
import ast
import pathlib
import unittest

import pandas as pd

APP = pathlib.Path(__file__).resolve().parents[1] / 'app.py'
NAMES = {'MONTH_LABELS', 'ensure_batch_time_cols', 'format_batch_label',
         'resolve_effective_period_and_batch', 'resolve_effective_batches', 'format_batches_label'}


def load():
    tree = ast.parse(APP.read_text(encoding='utf-8'))
    body = [n for n in tree.body
            if (isinstance(n, ast.FunctionDef) and n.name in NAMES)
            or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in NAMES for t in n.targets))]
    scope = {'pd': pd}
    exec(compile(ast.Module(body=body, type_ignores=[]), str(APP), 'exec'), scope)
    return scope


def met(rows):
    return pd.DataFrame([{'batch_id': b, 'country_id': c, 'batch_month': m} for b, c, m in rows])


# Noviembre real: un batch por país. Julio real: cada país corrió dos veces.
DATA = met([
    ('20261117T222306Z', 'CO', '2026-11'), ('20261118T235826Z', 'CR', '2026-11'),
    ('20261118T224547Z', 'DO', '2026-11'), ('20261119T155506Z', 'MX', '2026-11'),
    ('20260721T201913Z', 'CO', '2026-07'), ('20260722T202437Z', 'CO', '2026-07'),
    ('20260721T220545Z', 'MX', '2026-07'), ('20260722T222936Z', 'MX', '2026-07'),
])


class TodosBatches(unittest.TestCase):
    def setUp(self):
        self.s = load()

    def resolve(self, country='', period='', run=''):
        return self.s['resolve_effective_batches'](DATA, country, period, run)

    def test_todos_takes_latest_run_of_every_country(self):
        period, batches, _, _ = self.resolve()
        self.assertEqual(period, '2026-11')
        self.assertEqual(sorted(batches), ['20261117T222306Z', '20261118T224547Z',
                                           '20261118T235826Z', '20261119T155506Z'])

    def test_todos_with_reruns_keeps_only_last_run_per_country(self):
        _, batches, run_count, _ = self.resolve(period='2026-07')
        self.assertEqual(sorted(batches), ['20260722T202437Z', '20260722T222936Z'])
        self.assertEqual(run_count, 4)

    def test_single_country_unchanged(self):
        for country, batch in [('CO', '20261117T222306Z'), ('MX', '20261119T155506Z')]:
            with self.subTest(country=country):
                legacy = self.s['resolve_effective_period_and_batch'](DATA, country, '', '')[1]
                self.assertEqual(self.resolve(country)[1], [legacy])
                self.assertEqual(legacy, batch)

    def test_explicit_run_under_todos_is_respected(self):
        self.assertEqual(self.resolve(run='20261118T224547Z')[1], ['20261118T224547Z'])

    def test_label_names_included_countries(self):
        _, batches, _, _ = self.resolve()
        self.assertEqual(self.s['format_batches_label'](batches, DATA, ''),
                         'Última corrida de cada país (CO, CR, DO, MX)')
        self.assertEqual(self.s['format_batches_label']([], DATA, ''), 'Más reciente')


if __name__ == '__main__':
    unittest.main()
