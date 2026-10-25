"""Render an explicitly planned report. Pagination belongs to the page source."""
import argparse
import html
import json
from pathlib import Path
from urllib.parse import quote
from components import blocks_html
from visual_plan import validate_page

CANVASES = {'16:9': (1280,720), '9:16': (720,1280), 'A4': (794,1123), 'scroll': (1100,0)}


def render(source, output, replace=False, no_pdf=False, preserve_layout=False):
    markdown_input = Path(source).suffix.lower() in {'.md', '.markdown'}
    if markdown_input:
        from markdown_source import read_markdown
        data = read_markdown(source, output)
    else:
        data = json.loads(Path(source).read_text(encoding='utf-8'))
    pdf_file = data.get('pdf_file', '')
    if no_pdf or not pdf_file or not (Path(output).parent / pdf_file).is_file():
        data['pdf_file'] = ''
    else:
        data['pdf_file'] = quote(pdf_file, safe='/')
    canvas = data.get('canvas','16:9')
    if canvas not in CANVASES: raise ValueError(f'不支持的画布：{canvas}')
    width,height = CANVASES[canvas]
    theme = data.get('theme','blue')
    if theme not in {'blue','editorial','brief'}: raise ValueError(f'不支持的主题：{theme}')
    slides = data['slides']
    if not slides:
        raise ValueError('页面源为空')
    parts, options = [], []
    for index, slide in enumerate(slides, 1):
        kind = slide['kind']
        if kind not in {'content', 'cover', 'toc', 'chapter', 'back'}:
            raise ValueError(f'第{index}页类型不支持：{kind}')
        title, lead = slide['title'].strip(), slide.get('lead', '').strip()
        if not title or (canvas != 'scroll' and (not lead or title == lead)):
            raise ValueError(f'第{index}页需要不同的主标题及完整副标题')
        body = blocks_html(slide['blocks'],canvas) if 'blocks' in slide else slide.get('body', '')
        if not body.strip() and canvas != 'scroll':
            raise ValueError(f'第{index}页正文为空')
        if '<style' in body.lower() or '<script' in body.lower():
            raise ValueError(f'第{index}页正文包含全局样式或脚本；样式请使用 extra_css')
        if not markdown_input and not preserve_layout:
            validate_page(slide, body, index)
        esc = html.escape
        layout = esc(slide.get('layout', ''), quote=True)
        parts.append(f'<section id="page-{index}" class="slide {kind}" data-page="{index}" data-layout="{layout}"><header><div class="eyebrow"><span class="chapter-name">{esc(slide.get("section", ""))}</span><span>{index:02d}</span></div><h1>{esc(title)}</h1><p class="lead">{esc(lead)}</p></header><div class="content">{body}</div><footer><span>{esc(data.get("footer", ""))}</span><span>{index:02d} / {len(slides):02d}</span></footer></section>')
        options.append(f'<option value="{index-1}">{index:02d} · {esc(title)}</option>')
    template = (Path(__file__).resolve().parents[1] / 'assets/report.html').read_text(encoding='utf-8')
    mode_css=(Path(__file__).resolve().parents[1]/'assets/modes.css').read_text(encoding='utf-8')
    mode_css+='\n'+(Path(__file__).resolve().parents[1]/'assets/business.css').read_text(encoding='utf-8')
    size = '210mm 297mm' if canvas in {'A4','scroll'} else f'{width/96*25.4}mm {height/96*25.4}mm'
    settings=f':root{{--page-w:{width}px;--page-h:{height}px}} @page{{size:{size};margin:0}}'
    if canvas=='scroll':settings+='@page{margin:14mm 12mm}'
    values={'TITLE':html.escape(data['title']), 'EXTRA_CSS':data.get('extra_css','')+'\n'+mode_css+'\n'+settings, 'SLIDES':'\n'.join(parts), 'OPTIONS':''.join(options), 'PDF':html.escape(data.get('pdf_file',''),quote=True),'CANVAS':canvas,'THEME':theme,'WIDTH':str(width),'HEIGHT':str(height)}
    for key, value in values.items():
        template = template.replace('{{'+key+'}}', value)
    status = 'preserved-layout' if markdown_input or preserve_layout else 'visual-plan-checked'
    template = template.replace('</head>', f'<meta name="report-visual-check" content="{status}">\n</head>', 1)
    if not data.get('pdf_file'):
        template = template.replace('<a id="download" href="" download>下载 PDF</a>', '<!--PDF_DOWNLOAD-->')
    if canvas == 'scroll':
        assets = Path(__file__).resolve().parents[1] / 'assets'
        template = template.replace('</style>', '\n' + (assets/'scroll-sidebar.css').read_text(encoding='utf8') + '\n</style>', 1)
        nav = '<aside id="report-sidebar" aria-label="报告目录"><div class="sidebar-brand">报告目录</div><div class="sidebar-title">' + html.escape(data['title']) + '</div><nav id="report-toc" aria-label="章节导航"></nav></aside><button id="toc-toggle" aria-controls="report-sidebar" aria-expanded="false">目录</button>'
        template = template.replace('<main id="stage">', nav + '<main id="stage">', 1)
        template = template.replace('<script>\n', '<script>\nconst originalHash=location.hash;\n', 1)
        template = template.replace('</body>', '<script>\n' + (assets/'scroll-sidebar.js').read_text(encoding='utf8') + '\n</script></body>')
        # Preserve Markdown heading anchors, including links from the source TOC.
        for index, slide in enumerate(slides, 1):
            anchor = slide.get('heading_id')
            if anchor:
                marker = f'<h1>{html.escape(slide["title"].strip())}</h1>'
                start = template.index(f'<section id="page-{index}"')
                at = template.index(marker, start)
                template = template[:at] + template[at:].replace(marker, f'<h1 id="{html.escape(anchor, quote=True)}">{html.escape(slide["title"].strip())}</h1>', 1)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open('w' if replace else 'x', encoding='utf-8') as handle:
        handle.write(template)
    return len(slides)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source'); parser.add_argument('output'); parser.add_argument('--replace', action='store_true')
    parser.add_argument('--no-pdf', action='store_true', help='Do not show a download link when no PDF will be delivered.')
    parser.add_argument('--preserve-layout', action='store_true', help='Only for faithful conversion of an existing layout; skips new-design visual planning.')
    args = parser.parse_args()
    print(f'{render(args.source,args.output,args.replace,args.no_pdf,args.preserve_layout)} pages: {args.output}')
    if args.preserve_layout or Path(args.source).suffix.lower() in {'.md', '.markdown'}:
        print('原样转换：保留既有图文，未执行新设计的图形方案检查。')
