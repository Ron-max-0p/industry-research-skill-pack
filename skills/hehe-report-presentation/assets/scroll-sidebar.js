/* Generate navigation from the actual report, including nested subsections. */
(() => {
  const sidebar=document.getElementById('report-sidebar');
  const toc=document.getElementById('report-toc');
  const toggle=document.getElementById('toc-toggle');
  const entries=[];
  document.querySelectorAll('#stage .slide').forEach((section,i)=>{
    const main=section.querySelector('header h1');
    const headings=[main,...section.querySelectorAll('.content h2,.content h3')].filter(Boolean);
    headings.forEach((heading,j)=>{
      if(!heading.id){let id=`section-${i+1}-${j+1}`;while(document.getElementById(id))id+='-x';heading.id=id;}
      const link=document.createElement('a');link.href='#'+encodeURIComponent(heading.id);
      link.textContent=heading.textContent;link.dataset.depth=j===0?'1':(heading.tagName==='H3'?'3':'2');
      link.addEventListener('click',()=>{sidebar.classList.remove('open');toggle.setAttribute('aria-expanded','false');});
      toc.append(link);entries.push({heading,link,section});
    });
  });
  function highlight(){
    const cutoff=innerWidth<=900?70:32;
    let selected=entries[0];
    for(const entry of entries){
      const top=entry.heading.getBoundingClientRect().top;
      const position=entry.heading.tagName==='H1'?Math.min(top,entry.section.getBoundingClientRect().top):top;
      if(position<=cutoff)selected=entry;else break;
    }
    if(scrollY+innerHeight>=document.documentElement.scrollHeight-3&&entries.length){selected=entries[entries.length-1];}
    if(!selected)return;
    for(const entry of entries){if(entry===selected)entry.link.setAttribute('aria-current','location');else entry.link.removeAttribute('aria-current');}
    const n=Number(selected.section.dataset.page)-1;
    current=n;sel.value=String(n);
    slides.forEach((s,i)=>s.classList.toggle('active',i===n));
    document.getElementById('counter').textContent=`${n+1} / ${slides.length}`;
    document.getElementById('prev').disabled=n===0;
    document.getElementById('next').disabled=n===slides.length-1;
  }
  let pending=false;
  window.addEventListener('scroll',()=>{if(!pending){pending=true;requestAnimationFrame(()=>{highlight();pending=false;});}},{passive:true});
  window.addEventListener('resize',highlight);
  toggle.addEventListener('click',()=>{const open=sidebar.classList.toggle('open');toggle.setAttribute('aria-expanded',String(open));});
  document.addEventListener('keydown',event=>{if(event.key==='Escape'&&sidebar.classList.contains('open')){sidebar.classList.remove('open');toggle.setAttribute('aria-expanded','false');toggle.focus();}});
  if(originalHash){
    try{const target=document.getElementById(decodeURIComponent(originalHash.slice(1)));if(target){history.replaceState(null,'',originalHash);target.scrollIntoView();}}catch{}
  }
  document.getElementById('contents').onclick=()=>{if(innerWidth<=900){sidebar.classList.add('open');toggle.setAttribute('aria-expanded','true');}toc.querySelector('a')?.focus();};
  highlight();
})();
