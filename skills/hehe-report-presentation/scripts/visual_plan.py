"""Check a page's declared relationship against its rendered objects (stdlib only)."""
from html.parser import HTMLParser
import json
import math
import re


RELATIONS = {
    'flow': {'network', 'flow'},
    'sequence': {'flow', 'timeline', 'gantt'},
    'convergence': {'branch_merge'},
    'decision': {'decision'},
    'structure': {'structure'},
    'change': {'waterfall'},
    'comparison': {'bar', 'hbar', 'table'},
    'trend': {'line'},
    'composition': {'stacked', 'structure'},
    'distribution': {'distribution'},
    'calculation': {'calculation'},
    'coordination': {'swimlane', 'journey'},
    'lookup': {'table'},
    'narrative': {'prose'},
}
VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}


class Node:
    def __init__(self, tag='', attrs=(), parent=None):
        self.tag, self.attrs, self.parent = tag, dict(attrs), parent
        self.children, self.data = [], []

    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

    def visible(self):
        node = self
        while node:
            style = re.sub(r'\s+', '', node.attrs.get('style', '')).lower()
            if (node.tag in {'defs', 'marker', 'clippath', 'symbol', 'script', 'style', 'title', 'desc'}
                    or 'hidden' in node.attrs or 'display:none' in style or 'visibility:hidden' in style):
                return False
            # SVG primitives do not render nested graphics or text as a group does.
            if node is not self and node.tag in {'rect', 'circle', 'ellipse', 'path', 'line', 'polyline', 'polygon'}:
                return False
            node = node.parent
        return True

    def text(self):
        return ' '.join(s for n in self.walk() if n.visible() for s in n.data).strip()

    def has_class(self, name):
        return name in self.attrs.get('class', '').split()


class Document(HTMLParser):
    def __init__(self, body):
        super().__init__(convert_charrefs=True)
        self.root = self.current = Node()
        self.feed(body)

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_endtag(self, tag):
        node = self.current
        while node.parent:
            if node.tag == tag:
                self.current = node.parent
                return
            node = node.parent

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_data(self, data):
        self.current.data.append(data)


def _drawn_line(node):
    if node.tag == 'path':
        return bool(re.search(r'[LlHhVvCcSsQqTtAa]', node.attrs.get('d', '')))
    if node.tag == 'polyline':
        return len(re.findall(r'-?(?:\d+(?:\.\d*)?|\.\d+)', node.attrs.get('points', ''))) >= 4
    if node.tag == 'line':
        return (node.attrs.get('x1', '0'), node.attrs.get('y1', '0')) != (node.attrs.get('x2', '0'), node.attrs.get('y2', '0'))
    return False


def _data_mark(node):
    try:
        if node.tag == 'rect':
            return float(node.attrs.get('width', '0')) > 0 and float(node.attrs.get('height', '0')) >= 0 and 'height' in node.attrs
        if node.tag == 'circle':
            return float(node.attrs.get('r', '0')) > 0
    except ValueError:
        return False
    return _drawn_line(node)


def _custom_graph(target, form, nodes):
    if target.attrs.get('data-visual') != form:
        return False
    if form in {'bar', 'hbar', 'line', 'stacked', 'waterfall', 'distribution'}:
        marks = [n for n in nodes if 'data-value' in n.attrs and _data_mark(n)]
        try:
            return (bool(target.attrs.get('data-unit')) and len(marks) >= 2
                    and all(math.isfinite(float(n.attrs['data-value'])) for n in marks)
                    and bool(target.text()))
        except (TypeError, ValueError):
            return False
    points = [n for n in nodes if n.attrs.get('data-node') and n.text()]
    ids = [n.attrs['data-node'] for n in points]
    if len(ids) < 2 or len(ids) != len(set(ids)):
        return False
    if form == 'timeline':
        try:
            order = [float(n.attrs['data-order']) for n in points]
            return (all(math.isfinite(v) for v in order) and len(order) == len(set(order))
                    and any(_drawn_line(n) for n in nodes))
        except (KeyError, TypeError, ValueError):
            return False
    edges = [n for n in nodes if n.attrs.get('data-from') and n.attrs.get('data-to')
             and (_drawn_line(n) or (n.attrs.get('data-connector') == 'true' and n.text()))]
    if not edges or any(n.attrs['data-from'] not in ids or n.attrs['data-to'] not in ids for n in edges):
        return False
    if set(ids) != {n.attrs[k] for n in edges for k in ('data-from', 'data-to')}:
        return False
    if form == 'decision':
        return any(len({n.attrs['data-to'] for n in edges if n.attrs['data-from'] == key
                        and n.attrs.get('data-condition') and n.attrs['data-condition'] in target.text()}) >= 2 for key in ids)
    return True


def _implemented(target, form):
    nodes = [n for n in target.walk() if n.visible()]
    count = lambda cls: sum(n.has_class(cls) for n in nodes)
    if form == 'table':
        return any(n.tag == 'table' and n.text() for n in nodes)
    if form == 'prose':
        return any(n.tag == 'p' and n.text() for n in nodes)
    if form in {'bar', 'hbar', 'line', 'stacked', 'waterfall'}:
        for node in nodes:
            if node.has_class('native-chart') and node.attrs.get('data-chart'):
                chart = json.loads(node.attrs['data-chart'])
                if chart.get('chart_type') == form and any(n.tag == 'svg' for n in node.walk()):
                    return True
    native = {
        'flow': (count('report-flow') and count('flow-step') >= 2) or (count('analysis-path') and count('analysis-stage') >= 2),
        'timeline': count('report-timeline') and count('timeline-row') >= 2,
        'gantt': count('business-gantt') and count('gantt-bar') >= 1,
        'branch_merge': count('branch-map') and count('branch-row') >= 2 and count('merge-result'),
        'swimlane': count('swimlane-grid') or (count('portrait-matrix') and count('portrait-phase') >= 2),
        'journey': count('journey-grid') or (count('portrait-matrix') and count('portrait-phase') >= 2),
    }
    return bool(native.get(form)) or _custom_graph(target, form, nodes)


def validate_page(slide, body, index):
    """Raise before output is written. Covers/navigation are not analytical pages."""
    if slide.get('kind') != 'content':
        return
    plans = slide.get('visual_plan')
    if isinstance(plans, dict):
        plans = [plans]
    prefix = f'第{index}页「{slide.get("title", "")}」'
    if not isinstance(plans, list) or not plans:
        raise ValueError(prefix + '缺少 visual_plan：先确定关系、图式及完整解释位置。')
    nodes = list(Document(body).root.walk())
    for plan in plans:
        if not isinstance(plan, dict):
            raise ValueError(prefix + '的 visual_plan 须为对象或对象列表。')
        for key in ('relation', 'message', 'form', 'target', 'explanation'):
            if not isinstance(plan.get(key), str) or not plan[key].strip():
                raise ValueError(prefix + f'的图形方案缺少 {key}。')
        relation, form = plan['relation'], plan['form']
        if relation not in RELATIONS or form not in RELATIONS[relation]:
            raise ValueError(prefix + f'的 {relation} 关系不能由 {form} 承担；按关系选图。')
        if form in {'table', 'prose'} and not str(plan.get('reason', '')).strip():
            raise ValueError(prefix + '选表格或正文时，需写明其查阅、比较或论证作用 reason。')
        targets = [n for n in nodes if n.attrs.get('id') == plan['target']]
        if len(targets) != 1 or not targets[0].visible():
            raise ValueError(prefix + f'的 target={plan["target"]} 未唯一对应可见对象。')
        if not _implemented(targets[0], form):
            raise ValueError(prefix + f'计划使用 {form}，但对应对象未实现该图式；文字框、普通表格、图标和空 SVG 不计。')
