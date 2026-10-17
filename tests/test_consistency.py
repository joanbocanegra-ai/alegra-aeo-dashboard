"""Execute the actual dashboard KPI/detail expressions without network/DB."""
import ast
import pathlib
import unittest
import pandas as pd

APP=pathlib.Path(__file__).resolve().parents[1]/'app.py'

def expressions():
    tree=ast.parse(APP.read_text(encoding='utf-8'))
    kpi=next(n.value for n in ast.walk(tree) if isinstance(n,ast.Assign)
             and any(isinstance(t,ast.Name) and t.id=='avg_cs' for t in n.targets))
    detail=next(n.args[1].test for n in ast.walk(tree) if isinstance(n,ast.Call)
                and isinstance(n.func,ast.Name) and n.func.id=='metric_row' and len(n.args)>1
                and isinstance(n.args[0],ast.Constant) and n.args[0].value=='Consistency Score')
    scope={}
    for n in tree.body:
        if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='CONSISTENCY_MIN_RATE' for t in n.targets):
            scope['CONSISTENCY_MIN_RATE']=eval(compile(ast.Expression(n.value),str(APP),'eval'))
    return kpi,detail,scope

def evaluate(node,scope):
    return eval(compile(ast.Expression(node),str(APP),'eval'),scope)

class ConsistencyTests(unittest.TestCase):
    def test_actual_kpi_counts_two_of_three(self):
        kpi,_,scope=expressions()
        scope['fm']=pd.DataFrame({'mention_rate':[0.6667]})
        self.assertEqual(evaluate(kpi,scope),100.0)

    def test_actual_detail_counts_two_of_three(self):
        _,detail,scope=expressions()
        scope['m']={'mention_rate':0.6667}
        self.assertTrue(evaluate(detail,scope))

    def test_both_expressions_preserve_boundaries(self):
        kpi,detail,scope=expressions()
        for rate,expected in [(0.0,False),(1/3,False),(0.5,False),(2/3,True),(0.6667,True),(1.0,True)]:
            with self.subTest(rate=rate):
                scope.update(fm=pd.DataFrame({'mention_rate':[rate]}),m={'mention_rate':rate})
                self.assertEqual(evaluate(kpi,scope),100.0 if expected else 0.0)
                self.assertEqual(bool(evaluate(detail,scope)),expected)

    def test_empty_selection_returns_zero(self):
        kpi,_,scope=expressions()
        scope['fm']=pd.DataFrame({'mention_rate':[]})
        self.assertEqual(evaluate(kpi,scope),0)

    def test_tooltip_does_not_document_rounded_threshold(self):
        source=APP.read_text(encoding='utf-8')
        self.assertNotIn('mention_rate ≥ 0.67',source)
        self.assertIn('réplicas válidas',source)
