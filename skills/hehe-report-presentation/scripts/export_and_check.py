"""Render every page, check geometry and navigation, export searchable PDF."""
import argparse,json,re
from pathlib import Path
from urllib.parse import quote
from playwright.sync_api import sync_playwright
import fitz

def normalize(text): return re.sub(r'\s+','',text)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('html');ap.add_argument('--browser',required=True);ap.add_argument('--out',required=True);ap.add_argument('--replace',action='store_true')
    args=ap.parse_args();source=Path(args.html).resolve();out=Path(args.out).resolve()
    out.mkdir(parents=True,exist_ok=True)
    pdf=source.with_suffix('.pdf')
    if pdf.exists() and not args.replace:raise FileExistsError(pdf)
    result={'html':str(source),'pages':[],'browser_errors':[],'pdf_text_missing':[]}
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path=args.browser)
        page=browser.new_page(viewport={'width':1280,'height':764},device_scale_factor=1)
        page.context.set_offline(True)
        page.on('pageerror',lambda error:result['browser_errors'].append(str(error)))
        page.goto(source.as_uri());page.wait_for_function("document.documentElement.dataset.ready==='true'")
        canvas=page.locator('body').get_attribute('data-canvas') or '16:9'; scroll=canvas=='scroll'; result['canvas']=canvas
        width,height=page.evaluate("[parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--page-w')),parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--page-h'))]")
        page.set_viewport_size({'width':int(width),'height':int(height+44) if height else 900})
        count=page.locator('.slide').count()
        pdf_units=[]
        def navigation_reached(target):
            if not scroll:
                return page.locator('#pages').input_value()==str(target)
            page.wait_for_timeout(90)
            return page.evaluate('''n=>{const s=document.querySelectorAll('.slide')[n];if(!s)return false;const r=s.getBoundingClientRect(),h=s.querySelector('h1').getBoundingClientRect();return Math.abs(r.top)<150||(h.top>=0&&h.bottom<=innerHeight&&scrollY+innerHeight>=document.documentElement.scrollHeight-3)}''',target)
        for n in range(count):
            page.evaluate('(n)=>show(n)',n)
            row=page.evaluate('''n=>{const s=document.querySelectorAll('.slide')[n],box=s.getBoundingClientRect(),footer=s.querySelector('footer').getBoundingClientRect(),content=s.querySelector('.content');const nodes=[...s.querySelectorAll('h1,.lead,h2,p,td,th,.qty,.name,.work,.output,.role h2,.chapter-route>span,.toc-link')].filter(e=>e.getBoundingClientRect().height>0);const issues=[];let maxBottom=0;for(const el of nodes){const b=el.getBoundingClientRect();if(b.top<box.top-1||b.right>box.right-4||b.left<box.left-1||b.bottom>footer.top-8)issues.push({type:'page_boundary',text:el.textContent.slice(0,55),bottom:b.bottom,footer:footer.top});if(el.scrollWidth>el.clientWidth+2)issues.push({type:'horizontal_overflow',text:el.textContent.slice(0,55)});if(content.contains(el))maxBottom=Math.max(maxBottom,b.bottom);const r=document.createRange();r.selectNodeContents(el);const rects=[...r.getClientRects()];if(rects.some(x=>x.right>b.right+3||x.bottom>b.bottom+3))issues.push({type:'text_container',text:el.textContent.slice(0,55)});}return {number:Number(s.dataset.page),title:s.querySelector('h1').textContent,layout:s.dataset.layout,kind:s.className,issues,body_bottom:maxBottom,blank_before_footer:footer.top-maxBottom,font:getComputedStyle(content).fontFamily,units:[...s.querySelectorAll('h1,.lead,h2,p,td,th,.interview-row>.name,.interview-row>.qty,.interview-row>div:last-child,.week>.work,.week>.output')].map(e=>e.textContent.trim())}}''',n)
            pdf_units.append(row.pop('units'));result['pages'].append(row)
            page.locator('.slide').nth(n).screenshot(path=str(out/f'P{n+1:02}_CO.png'))
        page.evaluate('show(0)')
        if count>1:page.locator('#next').click()
        result['next_button']=navigation_reached(min(1,count-1))
        keyboard_target=min(int(page.locator('#pages').input_value())+1,count-1)
        page.keyboard.press('ArrowRight');result['keyboard']=navigation_reached(keyboard_target)
        if scroll:
            page.set_viewport_size({'width':1440,'height':960});page.evaluate('show(0)')
            result['sidebar_links']=[]
            result['sidebar_active_targets']=[]
            links=page.locator('#report-toc a')
            for i in range(links.count()):
                link=links.nth(i);target=link.evaluate('a=>decodeURIComponent(a.hash.slice(1))')
                link.click();page.wait_for_timeout(90)
                result['sidebar_links'].append(page.evaluate('id=>{const h=document.getElementById(id);if(!h)return false;const r=h.getBoundingClientRect();return Math.abs(r.top)<150||(r.top>=0&&r.bottom<=innerHeight&&scrollY+innerHeight>=document.documentElement.scrollHeight-3)}',target))
                at_bottom=page.evaluate('scrollY+innerHeight>=document.documentElement.scrollHeight-3')
                last_highlighted=links.last.get_attribute('aria-current')=='location'
                # At the document end several short sections can be visible together.
                result['sidebar_active_targets'].append(link.get_attribute('aria-current')=='location' or
                    (at_bottom and last_highlighted and result['sidebar_links'][-1]))
            page.locator('#report-toc a').first.click();page.wait_for_timeout(90)
            result['sidebar_highlight']=page.locator('#report-toc a[aria-current="location"]').count()==1
            page.evaluate("window.scrollTo(0,0);document.getElementById('report-sidebar').scrollTop=0")
            page.screenshot(path=str(out/'桌面侧栏预览_CO.png'))
            page.emulate_media(media='print')
            result['print_sidebar_hidden']=page.locator('#report-sidebar').evaluate('e=>getComputedStyle(e).display')=='none'
            page.emulate_media(media='screen')
        result['toc']=[]
        page.evaluate('show(0)')
        for i in range(page.locator('.toc-link').count()):
            a=page.locator('.toc-link').nth(i);parent=a.evaluate("el=>Number(el.closest('.slide').dataset.page)-1");page.evaluate('(n)=>show(n)',parent);target=int(re.search(r'show\((\d+)\)',a.get_attribute('onclick')).group(1));a.click();result['toc'].append(page.locator('#pages').input_value()==str(target))
        page.set_viewport_size({'width':390,'height':844});page.evaluate('show(2)');box=page.locator('.slide.active').bounding_box();result['phone_ratio']=box['width']/box['height'];result['offline']=True;result['phone_overflow']=page.evaluate('document.documentElement.scrollWidth>innerWidth+2');page.screenshot(path=str(out/'手机预览_CO.png'))
        if scroll:
            result['phone_toc_collapsed']=not page.locator('#report-sidebar').is_visible()
            page.locator('#toc-toggle').click();result['phone_toc_open']=page.locator('#report-sidebar').is_visible()
            page.screenshot(path=str(out/'手机目录预览_CO.png'))
            page.locator('#report-toc a').nth(min(1,page.locator('#report-toc a').count()-1)).click()
            result['phone_toc_closes_after_click']=not page.locator('#report-sidebar').is_visible()
        page.set_viewport_size({'width':int(width),'height':int(height+44) if height else 900});page.evaluate('show(0)')
        page.emulate_media(media='print')
        page.pdf(path=str(pdf),print_background=True,display_header_footer=False,prefer_css_page_size=True)
        browser.close()
    doc=fitz.open(pdf);result['pdf_pages']=len(doc);result['pdf_sizes']=[list(p.rect)[2:] for p in doc]
    for i,units in enumerate(pdf_units):
        text=normalize(''.join(p.get_text() for p in doc)) if scroll else (normalize(doc[i].get_text()) if i<len(doc) else '')
        for unit in units:
            if normalize(unit) not in text:result['pdf_text_missing'].append({'page':i+1,'text':unit[:90]})
    ratio=210/297 if canvas in {'scroll','A4'} else width/height
    result['pdf_ratio_correct']=all(abs(p.rect.width/p.rect.height-ratio)<.003 for p in doc)
    result['pdf_browser_header_absent']=not any('file:///' in p.get_text() for p in doc)
    result['pdf_colored_text']=any(span['color'] not in [0,0xffffff] for p in doc for block in p.get_text('dict')['blocks'] if 'lines' in block for line in block['lines'] for span in line['spans'])
    for n in [0,min(6,len(doc)-1),min(15,len(doc)-1),min(28,len(doc)-1)]:doc[n].get_pixmap(matrix=fitz.Matrix(1,1)).save(str(out/f'PDF_P{n+1:02}_CO.png'))
    result['passed']=not(result['browser_errors'] or result['pdf_text_missing'] or any(r['issues'] for r in result['pages']) or result['phone_overflow']) and result['pdf_ratio_correct'] and result['pdf_browser_header_absent'] and result['next_button'] and result['keyboard'] and all(result['toc']) and (scroll or len(doc)==count)
    if scroll:result['passed']=result['passed'] and all(result['sidebar_links']) and all(result['sidebar_active_targets']) and result['sidebar_highlight'] and result['print_sidebar_hidden'] and result['phone_toc_collapsed'] and result['phone_toc_open'] and result['phone_toc_closes_after_click']
    if result['passed']:
        # Expose the download only after the PDF has been created and checked.
        text=source.read_text(encoding='utf8')
        link=f'<a id="download" href="{quote(pdf.name)}" download>下载 PDF</a>'
        text,updated=re.subn(r'<a id="download"[^>]*>.*?</a>|<!--PDF_DOWNLOAD-->',lambda _:link,text,count=1)
        if updated:source.write_text(text,encoding='utf8')
        result['pdf_download_link_updated']=bool(updated)
    (out/'技术核验_CO.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    print(json.dumps({'canvas':canvas,'passed':result['passed'],'pages':count,'geometry_issues':[(r['number'],r['issues']) for r in result['pages'] if r['issues']], 'pdf_pages':len(doc),'pdf_ratio_correct':result['pdf_ratio_correct'],'pdf_text_missing':result['pdf_text_missing'],'navigation':result['next_button'] and result['keyboard'] and all(result['toc'])},ensure_ascii=False))

    if not result['passed']:raise SystemExit(1)

if __name__=='__main__':main()
