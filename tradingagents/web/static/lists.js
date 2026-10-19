'use strict';

// Pure collection helpers shared by the operating views and their fixtures.
const DeskLists = (() => {
  function page(items, current=0, size=25) {
    size=[25,50,100].includes(size)?size:25;
    const pages=Math.max(1,Math.ceil(items.length/size));
    current=Math.max(0,Math.min(pages-1,Number.isInteger(current)?current:0));
    const start=current*size;
    return {items:items.slice(start,start+size),current,pages,total:items.length,
      first:items.length?start+1:0,last:Math.min(items.length,start+size),size};
  }

  function csvRows(input) {
    const rows=[];let row=[],cell='',quoted=false,closed=false;
    for(let i=0;i<input.length;i++) {
      const c=input[i];
      if(c==='"') {
        if(quoted&&input[i+1]==='"'){cell+='"';i++;}
        else if(quoted){quoted=false;closed=true;}
        else if(cell.trim()||closed)throw new Error('A CSV quote is misplaced. Quote the entire field.');
        else quoted=true;
      } else if(c===','&&!quoted){row.push(cell);cell='';closed=false;}
      else if((c==='\n'||c==='\r')&&!quoted){
        if(c==='\r'&&input[i+1]==='\n')i++;
        row.push(cell);if(row.some(v=>v.trim()))rows.push(row);row=[];cell='';closed=false;
      }else if(closed&&!/\s/.test(c))throw new Error('A CSV field contains text after its closing quote.');
      else cell+=c;
    }
    if(quoted)throw new Error('A CSV quote is not closed. Check the file and try again.');
    row.push(cell);if(row.some(v=>v.trim()))rows.push(row);
    return rows;
  }

  function parseSymbols(input,{file=false,preview=false}={}) {
    input=String(input||'').replace(/^\uFEFF/,'');
    if(input.length>1048576)throw new Error('Use a CSV or text file smaller than 1 MB.');
    const rows=csvRows(input);
    const header=(rows[0]||[]).findIndex(v=>['symbol','ticker','stocksymbol'].includes(v.trim().toLowerCase().replace(/[\s_]/g,'')));
    let values;
    if(header>=0){
      values=rows.slice(1).map((row,index)=>{
        return {value:row[header]?.trim()||'',row:index+2};
      });
    }else{
      if(file&&rows.some(r=>r.length>1)&&rows.length>1)
        throw new Error('Add a Symbol or Ticker header to a multi-column CSV. A one-column list also works.');
      values=file&&rows.every(row=>row.length===1)?rows.flatMap((row,index)=>row[0].split(/[\s;]+/).filter(Boolean).map(value=>({value,row:index+1}))):input.split(/[\s,;]+/).filter(Boolean).map((value,index)=>({value,row:index+1}));
    }
    const seen=new Set(),dispositions=values.map(item=>{
      const symbol=item.value.trim().toUpperCase();
      const status=!/^[A-Z][A-Z0-9.\-]{0,9}$/.test(symbol)?'rejected':seen.has(symbol)?'duplicate':'accepted';
      if(status==='accepted')seen.add(symbol);
      return {...item,symbol,status,reason:status==='accepted'?'Valid syntax; broker support is checked separately':status==='duplicate'?'Already accepted earlier in this file':symbol?'Unsupported US equity symbol syntax':'Symbol field is empty'};
    });
    const invalid=dispositions.filter(item=>item.status==='rejected'),symbols=[...seen];
    if(!preview&&invalid.length)throw new Error('Rejected symbol rows: '+invalid.slice(0,5).map(item=>item.row+' ('+(item.value||'empty')+')').join(', ')+'. Correct them or use the file import preview.');
    if(!preview&&!symbols.length)throw new Error('Enter at least one stock symbol.');
    if(symbols.length>1000)throw new Error('This workspace supports up to 1,000 stock symbols.');
    return {symbols,duplicates:dispositions.filter(item=>item.status==='duplicate').length,rejected:invalid.length,rows:dispositions,column:header>=0};
  }

  function dateNY(value=new Date()) {
    return new Intl.DateTimeFormat('en-CA',{timeZone:'America/New_York',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date(value));
  }

  function marketState(clock,now=Date.now()) {
    if(typeof clock?.is_open!=='boolean'||!Number.isFinite(now))return 'unknown';
    const observed=typeof clock.timestamp==='string'?Date.parse(clock.timestamp):NaN;
    const boundary=Date.parse(clock.is_open?clock.next_close:clock.next_open);
    // A broker observation establishes an interval, not a fifteen-minute lease.
    // Never extrapolate past its next transition or infer false from a missing flag.
    if(!Number.isFinite(observed)||observed>now||!Number.isFinite(boundary)||boundary<=now||boundary<=observed)return 'unknown';
    return clock.is_open?'open':'closed';
  }

  function quoteState(quote,now=Date.now(),clock=null) {
    if(!quote||quote.price===null||quote.price===undefined||typeof quote.price==='boolean'||typeof quote.price==='string'&&!quote.price.trim()||!Number.isFinite(Number(quote.price)))return 'missing';
    const timestamps=[quote.timestamp,quote.quote_timestamp??quote.timestamp].map(value=>new Date(value).getTime());
    if(timestamps.some(timestamp=>!Number.isFinite(timestamp)||timestamp>now+60000))return 'stale';
    const market=marketState(clock,now);
    // Closed describes the session, not execution freshness. Keep the observed
    // last-trade date visible; never imply it is an official closing auction.
    if(market==='closed') {
      // The clock does not include the previous session's close. Only extend
      // references from its observed NY date; do not invent a holiday calendar.
      if(timestamps.every(timestamp=>dateNY(timestamp)===dateNY(clock.timestamp)))return 'closed';
      return 'unverified';
    }
    if(market==='unknown')return 'unknown';
    return timestamps.some(timestamp=>now-timestamp>900000)?'stale':'current';
  }

  function duration(seconds) {
    if(!Number.isFinite(seconds)||seconds<0)return null;
    const minutes=Math.max(1,Math.round(seconds/60));
    if(minutes<60)return `${minutes} min`;
    const hours=Math.floor(minutes/60),rest=minutes%60;
    return `${hours} hr${rest?` ${rest} min`:''}`;
  }

  function estimate(runs,config,stocks) {
    const keys=['llm_provider','deep_think_llm','quick_think_llm','max_debate_rounds','max_risk_discuss_rounds'];
    const samples=[];
    for(const run of runs) {
      if(keys.some(key=>run.config?.[key]!==config?.[key]))continue;
      for(const result of run.results||[])
        if(result.status==='completed'&&Number.isFinite(result.elapsed_seconds)&&result.elapsed_seconds>0)samples.push(result.elapsed_seconds);
    }
    if(!samples.length)return null;
    const recent=samples.slice(0,10).sort((a,b)=>a-b);
    const middle=Math.floor(recent.length/2);
    const median=recent.length%2?recent[middle]:(recent[middle-1]+recent[middle])/2;
    return {seconds:median*stocks,perStock:median,samples:recent.length};
  }

  return {page,parseSymbols,dateNY,marketState,quoteState,duration,estimate};
})();
