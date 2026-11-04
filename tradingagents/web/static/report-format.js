const DeskReports = (() => {
  const esc = value => String(value ?? '').replace(/[&<>"']/g, character => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[character]));
  const text = value => typeof value === 'string' ? value : JSON.stringify(value, null, 2);
function reportLink(value){
  if(!/^https?:\/\//i.test(value)||/[\s<>"'\\]/.test(value))return null;
  try{const url=new URL(value);return ['http:','https:'].includes(url.protocol)?url.href:null;}catch{return null;}
}
function reportInline(value,depth=0){
  const source=String(value??'');
  if(depth>5)return esc(source);
  const tokens=/`([^`\n]+)`|(!?\[([^\]\n]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\))|\*\*([^\n]+?)\*\*|(?<![\p{L}\p{N}_])__([^\n]+?)__(?![\p{L}\p{N}_])|\*([^*\n]+)\*|(?<![\p{L}\p{N}_])_([^_\n]+)_(?![\p{L}\p{N}_])/gu;
  let html='',offset=0;
  for(const match of source.matchAll(tokens)){
    html+=esc(source.slice(offset,match.index));
    if(match[1]!==undefined)html+=`<code>${esc(match[1])}</code>`;
    else if(match[2]!==undefined){
      const href=match[2].startsWith('!')?null:reportLink(match[4]);
      html+=href?`<a href="${esc(href)}" target="_blank" rel="noopener noreferrer">${esc(match[3])}</a>`:esc(match[2]);
    }else if(match[5]!==undefined||match[6]!==undefined)html+=`<strong>${reportInline(match[5]??match[6],depth+1)}</strong>`;
    else html+=`<em>${reportInline(match[7]??match[8],depth+1)}</em>`;
    offset=match.index+match[0].length;
  }
  return html+esc(source.slice(offset));
}
function reportTableCells(line){return line.trim().replace(/^\|/,'').replace(/\|$/,'').split(/(?<!\\)\|/).map(cell=>cell.trim().replace(/\\\|/g,'|'));}
function reportMarkdown(value,depth=0){
  if(depth>8)return `<p>${esc(value)}</p>`;
  const lines=String(value??'').replace(/\r\n?/g,'\n').split('\n');
  const html=[];
  const isTable=i=>i+1<lines.length&&lines[i].includes('|')&&reportTableCells(lines[i+1]).length>1&&reportTableCells(lines[i+1]).every(cell=>/^:?-{3,}:?$/.test(cell));
  const isBlock=i=>/^\s*$|^\s*```|^\s*#{1,6}\s|^\s*[^:\n]{1,80}:\s*#{1,6}\s|^\s*(?:[-+*]|\d+[.)])\s+|^\s*>\s?|^\s*(?:---+|\*\*\*+)\s*$/.test(lines[i])||isTable(i);
  for(let i=0;i<lines.length;){
    if(!lines[i].trim()){i++;continue;}
    if(/^\s*```/.test(lines[i])){
      const code=[];i++;
      while(i<lines.length&&!/^\s*```/.test(lines[i]))code.push(lines[i++]);
      if(i<lines.length)i++;
      html.push(`<pre><code>${esc(code.join('\n'))}</code></pre>`);continue;
    }
    const speakerHeading=lines[i].match(/^\s*([^:\n]{1,80}):\s*(#{1,6})\s+(.+?)\s*#*\s*$/);
    if(speakerHeading){const level=Math.min(6,speakerHeading[2].length+2);html.push(`<h${level}><strong>${reportInline(speakerHeading[1])}:</strong> ${reportInline(speakerHeading[3])}</h${level}>`);i++;continue;}
    const heading=lines[i].match(/^\s*(#{1,6})\s+(.+?)\s*#*$/);
    if(heading){const level=Math.min(6,heading[1].length+2);html.push(`<h${level}>${reportInline(heading[2])}</h${level}>`);i++;continue;}
    if(isTable(i)){
      const headers=reportTableCells(lines[i]);i+=2;const rows=[];
      while(i<lines.length&&lines[i].trim()&&lines[i].includes('|')){const cells=reportTableCells(lines[i++]);rows.push(`<tr>${headers.map((_,n)=>`<td>${reportInline(cells[n]??'')}</td>`).join('')}</tr>`);}
      html.push(`<div class="report-table-scroll" role="region" aria-label="Report table" tabindex="0"><table><thead><tr>${headers.map(cell=>`<th scope="col">${reportInline(cell)}</th>`).join('')}</tr></thead><tbody>${rows.join('')}</tbody></table></div>`);continue;
    }
    const list=lines[i].match(/^\s*([-+*]|\d+[.)])\s+(.+)$/);
    if(list){
      const ordered=/^\d/.test(list[1]);const start=ordered?Number.parseInt(list[1],10):1;const items=[];
      while(i<lines.length){const item=lines[i].match(/^\s*([-+*]|\d+[.)])\s+(.+)$/);if(!item||/^\d/.test(item[1])!==ordered)break;items.push(`<li>${reportInline(item[2])}</li>`);i++;}
      const tag=ordered?'ol':'ul';html.push(`<${tag}${ordered&&start!==1?` start="${start}"`:''}>${items.join('')}</${tag}>`);continue;
    }
    if(/^\s*>/.test(lines[i])){const quote=[];while(i<lines.length&&/^\s*>/.test(lines[i]))quote.push(lines[i++].replace(/^\s*>\s?/,''));html.push(`<blockquote>${reportMarkdown(quote.join('\n'),depth+1)}</blockquote>`);continue;}
    if(/^\s*(?:---+|\*\*\*+)\s*$/.test(lines[i])){html.push('<hr>');i++;continue;}
    const paragraph=[lines[i++]];
    while(i<lines.length&&!isBlock(i))paragraph.push(lines[i++]);
    html.push(`<p>${reportInline(paragraph.join('\n')).replace(/\n/g,'<br>')}</p>`);
  }
  return html.join('');
}
function reportValue(value){
  if(typeof value==='string'&&/^[\s]*[\[{]/.test(value)){try{const parsed=JSON.parse(value);if(parsed&&typeof parsed==='object')return parsed;}catch{/* Narrative text is not JSON. */}}
  return value;
}
const reportLabel=value=>String(value??'').replaceAll('_',' ').replace(/^\w/,letter=>letter.toUpperCase());
function reportStructured(value,depth=0){
  value=reportValue(value);
  if(value===null||value===undefined||value==='')return '<p class="muted">Not provided</p>';
  if(typeof value==='boolean')return `<p>${value?'Yes':'No'}</p>`;
  if(typeof value!=='object')return reportMarkdown(value);
  if(depth>4)return `<pre>${esc(text(value))}</pre>`;
  if(Array.isArray(value))return `<ul>${value.map(item=>`<li>${reportStructured(item,depth+1)}</li>`).join('')}</ul>`;
  return `<dl class="report-fields">${Object.entries(value).map(([key,item])=>`<div><dt>${esc(reportLabel(key))}</dt><dd>${reportStructured(item,depth+1)}</dd></div>`).join('')}</dl>`;
}
  return {reportLink, reportInline, reportTableCells, reportMarkdown, reportValue, reportLabel, reportStructured};
})();
