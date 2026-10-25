"""Regression checks for visual-plan enforcement and existing rendering paths."""
import json
from pathlib import Path
import tempfile
import unittest

from components import blocks_html
from render_report import render
from visual_plan import validate_page

ASSETS = Path(__file__).resolve().parents[1] / 'assets'
NETWORK = '''<figure id="graphic" data-visual="network">
<div data-node="buyer">机器人公司支付采集费。</div>
<div data-node="supplier">采集企业交付数据。</div>
<svg viewBox="0 0 600 200"><path data-from="buyer" data-to="supplier" d="M10 20 H500" stroke="blue"/></svg>
<p>验收条件和付款时间按合同分别确认，完整解释保留。</p></figure>'''


def page(form='network', relation='flow'):
    return {'kind': 'content', 'title': '采集费与数据交付', 'lead': '采购方支付费用，采集企业按约定交付数据。',
            'body': NETWORK, 'visual_plan': {'relation': relation, 'message': '机器人公司付款，采集企业交付数据。',
            'form': form, 'target': 'graphic', 'explanation': '节点保留职责，图下保留验收说明。'}}


class VisualPlanTests(unittest.TestCase):
    def test_network(self):
        validate_page(page(), NETWORK, 1)

    def test_missing_plan(self):
        p = page(); del p['visual_plan']
        with self.assertRaisesRegex(ValueError, '缺少 visual_plan'):
            validate_page(p, NETWORK, 1)

    def test_table_and_icon_cannot_replace_network(self):
        alternatives = [
            '<figure id="graphic" data-visual="network"><table><tr><td>付款</td><td>交付</td></tr></table></figure>',
            '<div id="graphic" data-visual="network"><p>付款与交付。</p><svg><path d="M0 0 L3 3"/><circle r="2"/></svg></div>',
            '<div id="graphic" data-visual="network"><p>流程说明</p><svg></svg></div>',
            '<div id="graphic" data-visual="network"><div data-node="a">甲方</div><div data-node="b">乙方</div></div>',
        ]
        for body in alternatives:
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, '未实现该图式'):
                validate_page(page(), body, 1)

    def test_broken_edge(self):
        with self.assertRaisesRegex(ValueError, '未实现该图式'):
            validate_page(page(), NETWORK.replace('data-to="supplier"', 'data-to="missing"'), 1)

    def test_empty_path_is_not_a_connector(self):
        with self.assertRaisesRegex(ValueError, '未实现该图式'):
            validate_page(page(), NETWORK.replace('M10 20 H500', ''), 1)

    def test_hidden_or_duplicate_target(self):
        for body in [NETWORK.replace('id="graphic"', 'id="graphic" hidden'), NETWORK + NETWORK]:
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, '未唯一对应可见对象'):
                validate_page(page(), body, 1)

    def test_hidden_edges_and_defs_do_not_count(self):
        for body in [NETWORK.replace('<svg ', '<svg hidden '), NETWORK.replace('<path ', '<defs><path ').replace('</svg>', '</defs></svg>')]:
            with self.subTest(body=body), self.assertRaisesRegex(ValueError, '未实现该图式'):
                validate_page(page(), body, 1)

    def test_relation_form_mismatch(self):
        with self.assertRaisesRegex(ValueError, '不能由'):
            validate_page(page('table'), '<table id="graphic"><tr><td>文字</td></tr></table>', 1)

    def test_legitimate_prose_and_lookup(self):
        for form, relation, body in [('prose', 'narrative', '<p id="graphic">该结果适用于所述研究对象，理由如下。</p>'),
                                     ('table', 'lookup', '<table id="graphic"><tr><td>数量</td><td>价格</td></tr></table>')]:
            p = page(form, relation)
            with self.assertRaisesRegex(ValueError, 'reason'):
                validate_page(p, body, 1)
            p['visual_plan']['reason'] = '读者需要核对完整条件或逐项明细。'
            validate_page(p, body, 1)

    def test_decision_needs_visible_branch_conditions(self):
        body = NETWORK.replace('data-visual="network"', 'data-visual="decision"')
        body = body.replace('<p>', '<div data-node="third">反馈通过，继续交付。</div><p>', 1)
        body = body.replace('<p>', '<span data-connector="true" data-from="buyer" data-to="third" data-condition="反馈通过">反馈通过 →</span><p>', 1)
        body = body.replace('data-to="supplier"', 'data-to="supplier" data-condition="反馈失败"')
        with self.assertRaisesRegex(ValueError, '未实现该图式'):
            validate_page(page('decision', 'decision'), body, 1)
        validate_page(page('decision', 'decision'), body.replace('机器人公司支付采集费。', '反馈失败，进入适配。'), 1)

    def test_custom_numeric_marks(self):
        body = '<figure id="graphic" data-visual="waterfall" data-unit="万元"><svg><rect width="20" height="10" data-value="10"/><rect width="20" height="20" data-value="-20"/></svg><p>现金由10万元减至负10万元。</p></figure>'
        validate_page(page('waterfall', 'change'), body, 1)
        with self.assertRaisesRegex(ValueError, '未实现该图式'):
            validate_page(page('waterfall', 'change'), body.replace('data-value="10"', 'data-value="NaN"'), 1)

    def test_malformed_svg_nesting_is_not_visible_data(self):
        body = '<figure id="graphic" data-visual="waterfall" data-unit="万元"><svg><rect width="20" height="10"/ data-value="10"><text>10</text><rect width="20" height="20"/ data-value="-20"><text>-20</text></svg><p>完整解释。</p></figure>'
        with self.assertRaisesRegex(ValueError, '未实现该图式'):
            validate_page(page('waterfall', 'change'), body, 1)

    def test_bundled_examples_in_all_canvases(self):
        for file in ASSETS.glob('*.json'):
            data = json.loads(file.read_text(encoding='utf8'))
            for canvas in ['16:9', '9:16', 'A4', 'scroll']:
                for i, slide in enumerate(data.get('slides', []), 1):
                    with self.subTest(file=file.name, canvas=canvas, page=i):
                        body = blocks_html(slide['blocks'], canvas) if 'blocks' in slide else slide['body']
                        validate_page(slide, body, i)

    def test_render_gate_and_preserved_conversion(self):
        with tempfile.TemporaryDirectory(prefix='report-visual-plan-') as directory:
            root = Path(directory).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            source, out = root/'source.json', root/'report.html'
            data = {'title': '测试', 'slides': [page()]}
            del data['slides'][0]['visual_plan']
            source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
            with self.assertRaisesRegex(ValueError, 'visual_plan'):
                render(source, out)
            self.assertFalse(out.exists())
            render(source, out, preserve_layout=True)
            self.assertIn('preserved-layout', out.read_text(encoding='utf8'))
            data['slides'] = [page()]
            source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
            render(source, out, replace=True)
            self.assertIn('visual-plan-checked', out.read_text(encoding='utf8'))
            original = out.read_bytes()
            del data['slides'][0]['visual_plan']
            source.write_text(json.dumps(data, ensure_ascii=False), encoding='utf8')
            with self.assertRaises(ValueError):
                render(source, out, replace=True)
            self.assertEqual(original, out.read_bytes())

    def test_markdown_sidebar_and_full_text(self):
        with tempfile.TemporaryDirectory(prefix='report-visual-md-') as directory:
            root = Path(directory).resolve()
            self.assertTrue(root.is_relative_to(Path(tempfile.gettempdir()).resolve()))
            source, out = root/'source.md', root/'report.html'
            source.write_text('# 采购研究\n\n## 采购条件\n\n这是完整条件说明，保留全部主语、条件和原因。\n\n[来源](https://example.com)\n', encoding='utf8')
            render(source, out)
            html = out.read_text(encoding='utf8')
            for text in ['report-sidebar', '这是完整条件说明，保留全部主语、条件和原因。', 'https://example.com', 'preserved-layout']:
                self.assertIn(text, html)
            self.assertNotIn('id="download"', html)


if __name__ == '__main__':
    unittest.main(verbosity=2)
