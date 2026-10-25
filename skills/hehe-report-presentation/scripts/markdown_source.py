"""Read a Markdown report as natural-flow sections; no pagination script needed."""
import base64
import mimetypes
from pathlib import Path
from urllib.parse import unquote, urlsplit


def read_markdown(source, output):
    try:
        import markdown
        from bs4 import BeautifulSoup
    except ImportError as exc:
        raise RuntimeError('Markdown 输入需要 markdown 和 beautifulsoup4：python -m pip install markdown beautifulsoup4') from exc
    source = Path(source).resolve()
    md = source.read_text(encoding='utf-8-sig')
    document = markdown.markdown(md, extensions=['tables', 'fenced_code', 'footnotes', 'toc', 'sane_lists'])
    soup = BeautifulSoup(document, 'html.parser')
    if soup.find(['script', 'style', 'iframe']):
        raise ValueError('Markdown 含脚本、全局样式或嵌入网页，请先转换为报告正文或本地图片。')
    for image in soup.find_all('img'):
        src = image.get('src', '')
        if src.startswith('data:'):
            continue
        parsed = urlsplit(src)
        if parsed.scheme or parsed.netloc:
            raise ValueError(f'离线报告请先下载图片，并在 Markdown 中使用本地路径：{src}')
        asset = (source.parent / unquote(parsed.path)).resolve()
        if not asset.is_file():
            raise FileNotFoundError(f'报告图片不存在：{asset}')
        mime = mimetypes.guess_type(asset.name)[0] or 'application/octet-stream'
        image['src'] = f'data:{mime};base64,' + base64.b64encode(asset.read_bytes()).decode('ascii')
    # Keep local attachments reachable when HTML is written to another directory.
    import os
    for link in soup.find_all('a', href=True):
        href = link['href']
        parsed = urlsplit(href)
        if href.startswith('#') or parsed.scheme or parsed.netloc:
            continue
        asset = (source.parent / unquote(parsed.path)).resolve()
        if asset.exists():
            try:
                relative = Path(os.path.relpath(asset, Path(output).resolve().parent)).as_posix()
            except ValueError:  # different Windows drives
                relative = asset.as_uri()
            link['href'] = relative + ('#' + parsed.fragment if parsed.fragment else '')
    for table in soup.find_all('table'):
        table['class'] = [*table.get('class', []), 'research-table']
        wrapper = soup.new_tag('div', attrs={'class': 'table-scroll'})
        table.wrap(wrapper)
    title_node = soup.find('h1')
    title = title_node.get_text(' ', strip=True) if title_node else source.stem
    slides = []
    current = {'kind': 'content', 'title': title, 'lead': '', 'body': '', 'section': ''}
    for node in list(soup.children):
        if getattr(node, 'name', None) in {'h1', 'h2'}:
            text = node.get_text(' ', strip=True)
            if node is title_node and not slides and not current['body'].strip():
                current['heading_id'] = node.get('id', '')
                continue
            slides.append(current)
            current = {'kind': 'content', 'title': text, 'lead': '', 'body': '',
                       'section': '', 'heading_id': node.get('id', '')}
        else:
            current['body'] += str(node)
    slides.append(current)
    return {'title': title, 'canvas': 'scroll', 'theme': 'blue', 'slides': slides,
            'footer': '', 'pdf_file': Path(output).with_suffix('.pdf').name}
