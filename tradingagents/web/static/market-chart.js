'use strict';

// Raw retained bars and explicit derived displays remain separate. No market data is fetched here.
window.DeskMarketChart=(()=>{
  const mounted=new Map(),ranges=new Map();
  const intervals=['1Min','5Min','15Min','30Min','1Hour','1Day'];
  function timeValue(value,timeframe){
    if(timeframe==='1Day'){
      const day=typeof value==='object'&&value?`${value.year}-${String(value.month).padStart(2,'0')}-${String(value.day).padStart(2,'0')}`:value;
      if(typeof day!=='string'||!/^\d{4}-\d{2}-\d{2}$/.test(day)||!Number.isFinite(Date.parse(day+'T00:00:00Z'))||new Date(day+'T00:00:00Z').toISOString().slice(0,10)!==day)throw new Error('Recorded daily business day is invalid.');
      return day;
    }
    if(!intervals.includes(timeframe)||typeof value!=='number'||!Number.isInteger(value)||value<0||value>253402300799)throw new Error('Recorded intraday UTC-second timestamp is invalid.');
    return value;
  }
  function ordered(bars,timeframe){
    let prior=null;for(const bar of bars){const time=timeValue(bar.t,timeframe);if(prior!==null&&time<=prior)throw new Error('Recorded bars must have unique increasing times.');prior=time;}
    return bars;
  }
  function normalize(points,timeframe){
    const unique=new Map();
    for(const point of points){const time=timeValue(point.t,timeframe),prior=unique.get(time);
      if(prior&&JSON.stringify(prior)!==JSON.stringify(point))throw new Error('Conflicting recorded revisions require a replacement source.');
      unique.set(time,point);
    }
    return [...unique.values()].sort((a,b)=>a.t<b.t?-1:a.t>b.t?1:0);
  }
  function formatTime(value,timeframe){
    const time=timeValue(value,timeframe);return timeframe==='1Day'?time:new Intl.DateTimeFormat(undefined,{timeZone:'America/New_York',year:'numeric',month:'short',day:'numeric',hour:'2-digit',minute:'2-digit',timeZoneName:'short'}).format(new Date(time*1000));
  }
  function compare(primary,secondary,anchor=null){
    if(!primary||!secondary||!primary.symbol||!secondary.symbol||primary.symbol===secondary.symbol)throw new Error('Choose two distinct retained symbols.');
    for(const field of ['context','provider','feed','timeframe','adjustment','session','currency']){
      if(primary[field]===undefined||primary[field]===null||primary[field]===''||primary[field]!==secondary[field])throw new Error('Comparison requires matching recorded '+field+' provenance.');
    }
    const timeframe=primary.timeframe;if(!intervals.includes(timeframe))throw new Error('Recorded comparison interval is unsupported.');
    const inputs=[primary,secondary].map(source=>ordered(source.bars||[],timeframe));
    const closes=inputs.map(bars=>new Map(bars.map(bar=>{
      const raw=bar.raw?.c??bar.c,value=Number(raw);
      if(!['number','string'].includes(typeof raw)||typeof raw==='string'&&!raw.trim()||!Number.isFinite(value))throw new Error('Comparison source close is missing or non-finite.');
      return [bar.t,{raw:String(raw),value}];
    })));
    const common=[...closes[0].keys()].filter(time=>closes[1].has(time));
    if(!common.length)throw new Error('These caches have no matching recorded bar times.');
    if(anchor===null)anchor=common.find(time=>closes.every(values=>values.get(time).value>0));
    if(anchor===undefined)throw new Error('No matching recorded time has positive closes for both comparison symbols.');
    anchor=timeValue(anchor,timeframe);
    if(!common.includes(anchor)||closes.some(values=>values.get(anchor).value<=0))throw new Error('Choose a common recorded time with positive source closes as the fixed comparison anchor.');
    const series=[primary,secondary].map((source,index)=>({symbol:source.symbol,key:source.key,source:source.source,captured_at:source.captured_at,
      anchor_close:closes[index].get(anchor).raw,excluded:inputs[index].length-common.length,
      points:common.map(time=>({time,value:closes[index].get(time).value/closes[index].get(anchor).value*100,source_close:closes[index].get(time).raw}))}));
    if(series.some(item=>item.points.some(point=>!Number.isFinite(point.value))))throw new Error('Comparison index cannot represent these source closes.');
    return {timeframe,anchor,anchors:common.filter(time=>closes.every(values=>values.get(time).value>0)),series,meaning:'Close-price index: 100 at the fixed common anchor. Unmatched times are excluded; no interpolation, portfolio return or dividend reinvestment is implied.'};
  }
  function dispose(){for(const [element,item] of mounted){if(element.isConnected)continue;
    const range=item.chart.timeScale().getVisibleLogicalRange();if(range)ranges.set(item.key,range);
    item.controller?.destroy();item.chart.remove();mounted.delete(element);item.onDispose?.();
  }while(ranges.size>32)ranges.delete(ranges.keys().next().value);}
  new MutationObserver(dispose).observe(document.documentElement,{childList:true,subtree:true});
  function annotations(element,chart,series,bars,options){
    const core=window.LightweightChartsDrawing,scope=options.drawingScope,ts=chart.timeScale();
    if(!core||!scope){options.onDrawingStatus?.([{state:'unavailable',reason:'Drawing library or chart source scope unavailable.'}]);return null;}
    let list=(options.drawings||[]).map(d=>structuredClone(d)),selected=options.selectedDrawingId||null,tool=options.drawingTool||null,drag=null,request=null;
    const times=bars.map(b=>b.t),decimal=value=>{const s=String(value),m=/^([+-]?)(\d*)(?:\.(\d*))?$/.exec(s);return m?(m[1]==='-'?'-':'')+(m[2].replace(/^0+/,'')||'0')+(m[3]?.replace(/0+$/,'')?'.'+m[3].replace(/0+$/,''):''):s;};
    const index=time=>times.indexOf(time),sec=time=>typeof time==='string'?Date.parse(time+'T00:00:00Z')/1000:time;
    function logical(time){
      const found=index(time);if(found>=0)return found;
      const value=sec(time);for(let i=1;i<times.length;i++)if(value>sec(times[i-1])&&value<sec(times[i]))return i-1+(value-sec(times[i-1]))/(sec(times[i])-sec(times[i-1]));
      return null;
    }
    function anchor(point){
      if(!Number.isFinite(Number(point.price)))throw new Error('Anchor price cannot render. Exact entered text is retained.');
      let x;
      if(point.basis==='logical_offset'){
        const origin=index(point.origin_time);if(origin<0)throw new Error('Projected anchor origin is absent from this view.');
        x=ts.logicalToCoordinate(origin+point.offset);
      }else{
        if(point.basis==='observed'){
          const bar=bars[index(point.time)];if(!bar)throw new Error('Observed anchor bar is absent or beyond the replay cutoff.');
          const raw=bar.raw?.[point.value_kind]??bar[point.value_kind];
          if(decimal(raw)!==decimal(point.price))throw new Error('Observed anchor value changed; original provenance is retained.');
        }
        const at=logical(point.time);if(at===null)throw new Error('Timestamp anchor is outside this loaded view; use an explicit projected offset.');
        x=ts.logicalToCoordinate(at);
      }
      const y=series.priceToCoordinate(Number(point.price));if(x===null||y===null)throw new Error('Anchor coordinates unavailable.');
      return {x,y};
    }
    const coords={priceToY:p=>series.priceToCoordinate(p),yToPrice:y=>series.coordinateToPrice(y),isLog:()=>false,
      timeToX:t=>{const n=logical(t);return n===null?null:ts.logicalToCoordinate(n);},xToTime:x=>{const n=ts.coordinateToLogical(x);return n!==null&&Number.isInteger(n)?times[n]??null:null;},
      barAt:t=>{const b=bars[index(t)];return b?{time:b.t,open:b.o,high:b.h,low:b.l,close:b.c}:null;},timeToBarIndex:logical,barIndexToTime:i=>times[i]??null,
      bars:()=>bars.map(b=>({time:b.t,open:b.o,high:b.h,low:b.l,close:b.c})),visibleTimeRange:()=>null,indicatorValuesAt:()=>[],pipSize:()=>NaN,
      formatTime:t=>String(t),timeInfo:()=>({timeZone:'America/New_York',intraday:scope.timeframe!=='1Day'}),timeAxis:()=>({height:ts.height(),width:ts.width(),fontSize:chart.options().layout.fontSize,fontFamily:chart.options().layout.fontFamily})};
    function visible(){
      const statuses=[],out=[];
      for(const d of list.filter(d=>!d.deleted)){
        try{
          if(Object.keys(scope).some(k=>d.scope?.[k]!==scope[k]))throw new Error('Drawing instrument/source/adjustment/unit scope differs.');
          const pts=d.points.map(anchor),render={...d,points:d.points.map(p=>({time:p.time??p.origin_time,price:Number(p.price)})),
            style:{...core.defaultStyleFor(d.kind),...d.style,text:d.text,showPriceLabels:false,showTimeLabels:false,showStats:false},text:d.text};
          out.push({drawing:d,render,pts});statuses.push({id:d.id,state:'available'});
        }catch(error){statuses.push({id:d.id,state:'unresolved',reason:error.message});}
      }
      return {statuses,out};
    }
    const primitive={attached:p=>{request=p.requestUpdate;},detached:()=>{request=null;},updateAllViews:()=>{},paneViews:()=>[{zOrder:()=> 'top',renderer:()=>({draw:target=>target.useMediaCoordinateSpace(({context,mediaSize})=>{
      context.save();context.beginPath();context.rect(0,0,mediaSize.width,mediaSize.height);context.clip();
      for(const item of visible().out){const scene=core.sceneOf(item.render,item.pts,{w:mediaSize.width,h:mediaSize.height,coords,selected:item.drawing.id===selected});core.drawScene(context,scene,{fontFamily:'sans-serif',anchors:{selected:item.drawing.id===selected,fillAt:()=>getComputedStyle(element).getPropertyValue('--surface').trim()||'#1c2933'}});}
      context.restore();
    })})}]};
    function redraw(){request?.();}
    function report(){options.onDrawingStatus?.(visible().statuses);redraw();}
    function select(id){
      selected=id;const item=visible().out.find(item=>item.drawing.id===id&&item.drawing.kind==='text');
      if(item){const box=core.sceneOf(item.render,item.pts,{w:ts.width(),h:element.clientHeight-ts.height(),coords,selected:true}).find(shape=>shape.t==='rect');
        const shift=box?(box.x<0?box.x:Math.max(0,box.x+box.w-ts.width())):0,spacing=ts.options().barSpacing;
        if(Number.isFinite(shift)&&shift!==0&&spacing>0)ts.scrollToPosition(ts.scrollPosition()+shift/spacing,false);
      }
      options.onDrawingSelect?.(id);redraw();
    }
    function update(d){const at=list.findIndex(item=>item.id===d.id);if(at<0)list.push(structuredClone(d));else list[at]=structuredClone(d);report();}
    const savedScroll=chart.options().handleScroll;
    function setTool(kind){tool=kind;drag=null;chart.applyOptions({handleScroll:kind?false:savedScroll});element.style.cursor=kind?'crosshair':'';}
    function pointAt(event){
      const box=element.getBoundingClientRect(),x=event.clientX-box.left,y=event.clientY-box.top,n=ts.coordinateToLogical(x),price=series.coordinateToPrice(y);
      if(n===null||price===null||!Number.isFinite(price)||x<0||x>ts.width()||y<0||y>element.clientHeight-ts.height()||!times.length)return null;
      const at=Math.max(0,Math.min(times.length-1,Math.round(n))),raw=Number(price).toLocaleString('en-US',{useGrouping:false,maximumFractionDigits:20});
      return {cursor:{x,y},point:Math.abs(n-at)<.05?{basis:'manual_time',time:times[at],price:raw}:{basis:'logical_offset',origin_time:times[at],offset:n-at,price:raw}};
    }
    function down(event){
      if(event.button!==0)return;const input=pointAt(event);if(!input)return;
      if(tool){event.preventDefault();event.stopImmediatePropagation();options.onDrawingPoint?.(input.point);return;}
      const hit=visible().out.reverse().map(item=>({...item,hit:core.hitTestKind(item.render,item.pts,input.cursor,ts.width(),element.clientHeight-ts.height(),coords,item.drawing.id===selected)})).find(item=>item.hit);
      if(!hit)return;select(hit.drawing.id);event.preventDefault();event.stopImmediatePropagation();
      if(hit.hit.hit==='handle'||hit.drawing.kind!=='trend-line'){drag={drawing:structuredClone(hit.drawing),index:hit.hit.handleIndex??0};chart.applyOptions({handleScroll:false});element.setPointerCapture(event.pointerId);}
    }
    function move(event){if(!drag)return;const input=pointAt(event);if(!input)return;const d=structuredClone(drag.drawing);d.points[drag.index]=input.point;update(d);options.onDrawingChange?.(structuredClone(d));event.preventDefault();}
    function up(event){if(!drag)return;const changed=list.find(d=>d.id===drag.drawing.id);drag=null;chart.applyOptions({handleScroll:savedScroll});if(element.hasPointerCapture(event.pointerId))element.releasePointerCapture(event.pointerId);if(changed)options.onDrawingChange?.(structuredClone(changed));}
    function keydown(event){if(event.target!==element)return;if(event.key==='Escape'){setTool(null);select(null);}else if((event.key==='Delete'||event.key==='Backspace')&&selected){event.preventDefault();const d=list.find(item=>item.id===selected);if(d){const deleted={...structuredClone(d),deleted:true};update(deleted);select(null);options.onDrawingChange?.(deleted);}}}
    element.tabIndex=0;element.addEventListener('pointerdown',down,true);element.addEventListener('pointermove',move);element.addEventListener('pointerup',up);element.addEventListener('pointercancel',up);element.addEventListener('keydown',keydown);
    series.attachPrimitive(primitive);setTool(tool);report();
    return {select,setTool,update,add:update,remove:id=>{list=list.filter(d=>d.id!==id);report();},destroy:()=>{setTool(null);series.detachPrimitive(primitive);element.removeEventListener('pointerdown',down,true);element.removeEventListener('pointermove',move);element.removeEventListener('pointerup',up);element.removeEventListener('pointercancel',up);element.removeEventListener('keydown',keydown);}};
  }
  function mount(element,options){
    const {bars:inputBars,indicators=[],key,onSelect,timeframe='1Day',comparison=null,logicalRange=null,onRangeChange,onDispose}=options;let bars=inputBars;
    dispose();if(!element||mounted.has(element))return mounted.get(element)?.controller;
    if(!window.LightweightCharts){element.textContent='Chart library unavailable. Recorded OHLCV remains available below.';return;}
    try{
      bars=normalize(bars,timeframe);ordered(bars,timeframe);if(comparison&&comparison.timeframe!==timeframe)throw new Error('Comparison interval differs from chart interval.');
      const library=window.LightweightCharts,style=getComputedStyle(element),color=name=>style.getPropertyValue(name).trim();
      const chart=library.createChart(element,{autoSize:true,height:280,
        layout:{background:{color:color('--paper')},textColor:color('--ink'),fontSize:parseFloat(style.getPropertyValue('--text-data')),fontFamily:style.getPropertyValue('--font').trim()},
        grid:{vertLines:{color:color('--line')},horzLines:{color:color('--line')}},timeScale:{timeVisible:timeframe!=='1Day',secondsVisible:false,lockVisibleTimeRangeOnResize:true},
        localization:{priceFormatter:value=>Number(value).toFixed(2),timeFormatter:time=>formatTime(time,timeframe)}});
      mounted.set(element,{chart,key,onDispose});
      if(comparison){
        chart.priceScale('right').applyOptions({mode:library.PriceScaleMode.Normal});
        comparison.series.forEach((item,index)=>{const line=chart.addSeries(library.LineSeries,{color:['#86d6ab','#e6c17d'][index],title:item.symbol+' close index',priceScaleId:'right',priceLineVisible:false});line.setData(item.points.map(point=>({time:point.time,value:point.value})));});
      }else{
        const candles=chart.addSeries(library.CandlestickSeries,{upColor:color('--positive'),downColor:color('--negative'),borderVisible:false,wickUpColor:color('--positive'),wickDownColor:color('--negative')});
        candles.setData(bars.map(b=>({time:b.t,open:b.o,high:b.h,low:b.l,close:b.c})));
        mounted.get(element).controller=annotations(element,chart,candles,bars,options);
        const volume=chart.addSeries(library.HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:'volume'});
        volume.priceScale().applyOptions({scaleMargins:{top:.82,bottom:0},visible:false});
        volume.setData(bars.map(b=>({time:b.t,value:b.v,color:b.c>=b.o?'#386c58':'#704650'})));
        indicators.filter(i=>/sma|ema/i.test(i.name)).forEach((item,index)=>{
          const series=chart.addSeries(library.LineSeries,{color:['#e6c17d','#86d6ab','#a5b3c0'][index%3],lineWidth:1,title:item.name,priceLineVisible:false});
          const dates=new Set(bars.map(b=>b.t));series.setData(normalize(item.points,timeframe).filter(p=>dates.has(p.t)&&Number.isFinite(p.value)).map(p=>({time:p.t,value:p.value})));
        });
      }
      if(comparison)options.onDrawingStatus?.([{state:'unavailable',reason:'Drawings use price units; this comparison pane uses an index.'}]);
      chart.subscribeClick(event=>{if(event.time!==undefined&&event.time!==null&&onSelect)onSelect(timeValue(event.time,timeframe));});
      const range=logicalRange||ranges.get(key);if(range)chart.timeScale().setVisibleLogicalRange(range);else chart.timeScale().fitContent();
      if(onRangeChange)chart.timeScale().subscribeVisibleLogicalRangeChange(range=>{if(range)onRangeChange({from:range.from,to:range.to});});
      return mounted.get(element).controller;
    }catch{const item=mounted.get(element);item?.controller?.destroy();item?.chart.remove();mounted.delete(element);element.textContent='Chart could not render these saved bars. Use the recorded session values below.';}
  }

  function displayNumber(raw){
    if(raw===null||raw===undefined||raw==='')return null;const text=String(raw),parts=text.split('/');let value;
    if(parts.length===2){if(!/^-?\d+$/.test(parts[0])||!/^\d+$/.test(parts[1])||Number(parts[1])===0)return null;value=Number(parts[0])/Number(parts[1]);}else if(parts.length===1)value=Number(text);else return null;
    return Number.isFinite(value)?value:null;
  }
  function xml(value){return String(value??'').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');}
  function analysisTable(rows){if(!rows?.length)return '<p>No eligible retained rows.</p>';const fields=[...new Set(rows.flatMap(row=>Object.keys(row)))];return '<div class="table-scroll"><table><thead><tr>'+fields.map(key=>'<th>'+xml(key.replaceAll('_',' '))+'</th>').join('')+'</tr></thead><tbody>'+rows.map(row=>'<tr>'+fields.map(key=>'<td>'+xml(typeof row[key]==='object'?JSON.stringify(row[key]):row[key]??'Unavailable')+'</td>').join('')+'</tr>').join('')+'</tbody></table></div>';}
  function svgFrame(title,values,xmax,draw){
    const valid=values.filter(value=>value!==null&&Number.isFinite(value));if(!valid.length)return '<p>'+xml(title)+': no numerical values available.</p>';
    const lo=valid.reduce((a,b)=>Math.min(a,b),Infinity),hi=valid.reduce((a,b)=>Math.max(a,b),-Infinity),span=hi-lo||Math.max(Math.abs(hi)*.01,1),x=value=>50+value/Math.max(xmax,1)*700,y=value=>235-(value-lo)/span*200;
    return '<figure><figcaption>'+xml(title)+'</figcaption><svg viewBox="0 0 800 280" role="img" aria-label="'+xml(title)+'"><line x1="50" x2="750" y1="245" y2="245" stroke="currentColor"/><text x="0" y="35" fill="currentColor" font-size="10">'+xml(hi)+'</text><text x="0" y="235" fill="currentColor" font-size="10">'+xml(lo)+'</text>'+draw(x,y)+'</svg></figure>';
  }
  function transformDisplay(result,definition){
    const events=result.events||[],family=definition?.settings?.family,positions=new Map(),box=family==='point_figure'?displayNumber(definition.settings.box_size):null;let base=0,previousSegment=null,maximum=0,segmentOrigin=0;
    if(family==='point_figure'&&(box===null||box<=0))return '<p>P&amp;F configured box size cannot be represented for display; exact levels remain in retained evidence.</p>';
    for(const event of events){const coordinate=family==='kagi'||family==='point_figure'?Number(event.column??event.output_ordinal):event.output_ordinal;if(previousSegment===null||event.segment!==previousSegment){base=previousSegment===null?0:maximum+2;segmentOrigin=coordinate;}const position=base+coordinate-segmentOrigin;positions.set(event.output_ordinal,position);maximum=Math.max(maximum,position);previousSegment=event.segment;}
    const numbers=events.flatMap(event=>family==='point_figure'&&box!==null?[displayNumber(event.ohlc?.close)].flatMap(level=>level===null?[]:[level-box/2,level+box/2]):Object.values(event.ohlc||{}).map(displayNumber));
    return svgFrame(family+' · logical event/column axis; exact source times may repeat',numbers,maximum+1,(x,y)=>{let previous=null;return events.map(event=>{
      const p=event.ohlc||{},o=displayNumber(p.open),c=displayNumber(p.close),h=displayNumber(p.high),l=displayNumber(p.low);if([o,c,h,l].some(value=>value===null)){previous=null;return '';}
      const glyphHigh=family==='point_figure'&&box!==null?c+box/2:h,glyphLow=family==='point_figure'&&box!==null?c-box/2:l,cx=x(positions.get(event.output_ordinal)),width=Math.min(12,600/Math.max(maximum+2,1)),color=event.direction===-1?'#dc8995':'#86d6ab',title='Event '+event.output_ordinal+' · actual source '+event.t+' · derived '+JSON.stringify(p);let shape='';
      if(family==='kagi'){const join=previous&&previous.segment===event.segment&&event.geometry?.reversal?'<path d="M'+previous.x+','+previous.y+' H'+cx+'" stroke="'+color+'" fill="none"/>':'';shape=join+'<line x1="'+cx+'" x2="'+cx+'" y1="'+y(o)+'" y2="'+y(c)+'" stroke="'+color+'" stroke-width="'+(event.style==='thick'?4:1.5)+'"/>';}
      else if(family==='point_figure'){shape=event.style==='X'?'<path d="M'+(cx-width/2)+','+y(glyphHigh)+' L'+(cx+width/2)+','+y(glyphLow)+' M'+(cx-width/2)+','+y(glyphLow)+' L'+(cx+width/2)+','+y(glyphHigh)+'" stroke="'+color+'" fill="none"/>':'<ellipse cx="'+cx+'" cy="'+((y(glyphHigh)+y(glyphLow))/2)+'" rx="'+width/2+'" ry="'+Math.abs(y(glyphHigh)-y(glyphLow))/2+'" fill="none" stroke="'+color+'"/>';}
      else shape='<line x1="'+cx+'" x2="'+cx+'" y1="'+y(h)+'" y2="'+y(l)+'" stroke="'+color+'"/><rect x="'+(cx-width/2)+'" y="'+Math.min(y(o),y(c))+'" width="'+width+'" height="'+Math.max(Math.abs(y(o)-y(c)),1)+'" fill="'+color+'"/>';
      previous={x:cx,y:y(c),segment:event.segment};return '<g role="button" tabindex="0" data-analysis-event-ordinal="'+event.output_ordinal+'" aria-label="'+xml(title)+'"><title>'+xml(title)+'</title>'+shape+'<rect x="'+(cx-width)+'" y="'+Math.min(y(glyphHigh),y(glyphLow))+'" width="'+width*2+'" height="'+Math.max(Math.abs(y(glyphHigh)-y(glyphLow)),8)+'" fill="transparent"/></g>';
    }).join('')+'<text x="50" y="270" fill="currentColor" font-size="10">Logical origin</text><text x="750" y="270" text-anchor="end" fill="currentColor" font-size="10">Logical event / column '+xml(maximum)+'</text>';})+'<p>Coordinates are derived geometry, not market timestamps or executable prices. Source gaps separate logical segments; volume is not summed across generated events. P&amp;F glyph height is configured-box display geometry centered on its exact level, not an observed OHLC range.</p>';
  }
  function seriesDisplay(series,sourceRows,axis=null){
    const gapBefore=new Set(sourceRows.filter((row,index)=>row.gap_before||!row.raw||row.reasons?.length||index>0&&row.segment!==sourceRows[index-1].segment).map(row=>row.source_ordinal));
    const groups=new Map();for(const item of series){const render=item.render|| (item.units==='price'?'overlay':'line'),key=render+':'+item.units;if(!groups.has(key))groups.set(key,[]);groups.get(key).push({...item,render});}
    const colors=['#e6c17d','#86d6ab','#a5b3c0','#dc8995','#90b9e0'];
    return [...groups].map(([key,items])=>{const overlay=items[0].render==='overlay',rows=overlay?sourceRows.filter(row=>row.raw):[],coordinates=items.flatMap(s=>s.points.map(p=>p.source_ordinal+(p.display_offset||0))),minX=axis?.min??coordinates.reduce((a,b)=>Math.min(a,b),0),maxX=axis?.max??coordinates.reduce((a,b)=>Math.max(a,b),0),values=items.flatMap(s=>s.points.filter(p=>p.numerical_available&&p.initialized).map(p=>displayNumber(p.raw)));if(items[0].render==='histogram'&&values.some(value=>value!==null))values.push(0);if(overlay)values.push(...rows.flatMap(row=>[displayNumber(row.raw.h),displayNumber(row.raw.l)]));
      return svgFrame(items.map(s=>s.name).join(' / ')+' · '+items[0].units+' · '+items[0].render+'; source logical ordinals + explicit displacement',values,maxX-minX+1,(x,y)=>{
        let background=rows.map(row=>{const o=displayNumber(row.raw.o),c=displayNumber(row.raw.c),h=displayNumber(row.raw.h),l=displayNumber(row.raw.l);if([o,c,h,l].some(v=>v===null))return '';const cx=x(row.source_ordinal-minX);return '<line x1="'+cx+'" x2="'+cx+'" y1="'+y(h)+'" y2="'+y(l)+'" stroke="#62717e"/><line x1="'+(cx-2)+'" x2="'+(cx+2)+'" y1="'+y(o)+'" y2="'+y(c)+'" stroke="#62717e"/>';}).join('');
        const leadingA=items.find(s=>s.name==='span_a'),leadingB=items.find(s=>s.name==='span_b');if(leadingA&&leadingB){const pairs=new Map();for(const p of leadingA.points)if(p.initialized&&p.numerical_available)pairs.set(p.source_ordinal+(p.display_offset||0),{a:displayNumber(p.raw),source:p.source_ordinal});for(const p of leadingB.points){const key=p.source_ordinal+(p.display_offset||0),pair=pairs.get(key);if(pair&&p.initialized&&p.numerical_available)pair.b=displayNumber(p.raw);}for(const [key,pair]of pairs){const prior=pairs.get(key-1);if(prior&&!gapBefore.has(pair.source)&&[pair.a,pair.b,prior.a,prior.b].every(v=>v!==null&&v!==undefined))background+='<polygon points="'+x(key-1-minX)+','+y(prior.a)+' '+x(key-minX)+','+y(pair.a)+' '+x(key-minX)+','+y(pair.b)+' '+x(key-1-minX)+','+y(prior.b)+'" fill="'+(pair.a>=pair.b?'#86d6ab':'#dc8995')+'" fill-opacity=".16"/>';}}
        return background+items.map((s,index)=>{let path='',prior=null,shapes='';for(const p of s.points){const value=p.numerical_available&&p.initialized?displayNumber(p.raw):null,cx=x(p.source_ordinal+(p.display_offset||0)-minX);if(value===null){prior=null;continue;}const color=p.initialized?colors[index%colors.length]:'#62717e';if(s.render==='histogram'){shapes+='<line x1="'+cx+'" x2="'+cx+'" y1="'+y(0)+'" y2="'+y(value)+'" stroke="'+color+'" stroke-width="3"/>';continue;}const gap=prior===null||p.source_ordinal!==prior+1||gapBefore.has(p.source_ordinal)||p.gap_before===true;path+=(gap?'M':'L')+cx+','+y(value)+' ';prior=p.source_ordinal;}return shapes+'<path d="'+path+'" fill="none" stroke="'+colors[index%colors.length]+'" '+(s.partial?'stroke-dasharray="5 4"':'')+'/>';}).join('')+'<text x="50" y="270" fill="currentColor" font-size="10">Logical source '+xml(minX)+'</text><text x="750" y="270" text-anchor="end" fill="currentColor" font-size="10">Logical display '+xml(maxX)+'</text>';})+'<ul>'+items.map((s,index)=>'<li><span style="color:'+colors[index%colors.length]+'">'+xml(s.name)+'</span>'+ (s.partial?' · dashed partial prefix':'')+'</li>').join('')+'</ul>'+(overlay?'<p>Muted candles are actual captured raw OHLC from this calculation source.</p>':'')+'<p>Display displacement does not change origin or availability time. Numerical seed/warmup values remain in the exact readout and are omitted from the plotted line until initialized. Gaps are not zero or interpolated.</p>';
    }).join('');
  }
  function seasonalityDisplay(value,options={}){
    if(!value)return '';const months=value.monthly||[],years=value.comparison_years||value.years||[],keys=[...new Set(years.flatMap(year=>year.points.map(p=>value.alignment==='calendar'?p.calendar_key:p.session_ordinal)))].sort((a,b)=>typeof a==='number'?a-b:String(a).localeCompare(String(b))),series=years.map(year=>({name:String(year.year)+(year.complete===false?' · partial prefix; excluded from monthly samples':''),partial:year.complete===false,units:value.comparison,render:'line',points:year.points.map(p=>({source_ordinal:keys.indexOf(value.alignment==='calendar'?p.calendar_key:p.session_ordinal),display_offset:0,raw:p.value,numerical_available:p.value!==null,initialized:true}))}));
    const monthlySeries=[{name:'Monthly positive-year frequency / fraction',units:'eligible-year fraction',render:'histogram',points:months.map(m=>({source_ordinal:m.month-1,raw:m.positive_frequency,numerical_available:m.positive_frequency!==null,initialized:true}))},{name:'Monthly whole-sample mean return / %',units:'percent',render:'histogram',points:months.map(m=>({source_ordinal:m.month-1,raw:m.mean_return_pct,numerical_available:m.mean_return_pct!==null,initialized:true}))}];
    return '<h4>Completed-year seasonality</h4>'+(!value.calendar_coverage?.reference||!value.calendar_coverage?.start||!value.calendar_coverage?.end?'<p>Authenticated calendar request bounds are unavailable. Complete-year and period coverage cannot be established. An empty missing-sessions list only checks dates present in the retained calendar response.</p>':'')+'<p>'+xml(value.return_basis)+' · '+xml(value.adjustment)+' · '+xml(value.frequency_denominator)+'</p>'+seriesDisplay(monthlySeries,[])+'<p>Monthly axis: 0 = January, 11 = December. Frequency is a fraction of all eligible complete years, with flats retained in the denominator.</p>'+analysisTable(months)+'<h4>Yearly '+xml(value.comparison)+' comparison · '+xml(value.alignment)+' alignment</h4>'+'<p>'+xml(options.yearScale==='separate'?'Separate labeled value scale for each year; common calendar/session x domain.':'Common value scale across all years; common calendar/session x domain.')+'</p>'+(options.yearScale==='separate'?series.map(item=>seriesDisplay([item],[],{min:0,max:Math.max(keys.length-1,0)})).join(''):seriesDisplay(series,[],{min:0,max:Math.max(keys.length-1,0)}))+'<p>Year-axis logical positions map to these actual calendar/session labels: '+xml(keys.join(', '))+'. No synthetic market timestamp or zero return is inserted.</p>'+analysisTable(years.map(year=>({year:year.year,complete:year.complete,through:year.through,included_in_monthly_aggregates:year.complete===true,prior_anchor:year.prior_anchor,prior_anchor_close:year.prior_anchor_close,monthly_returns:year.monthly_returns})))+'<h4>Incomplete periods · excluded from completed aggregates</h4>'+analysisTable([{period:'MTD',...value.partial?.mtd},{period:'YTD',...value.partial?.ytd}])+'<h4>Excluded years</h4>'+analysisTable(value.excluded_years);
  }
  function mountAnalysis(element,result,options={}){
    if(!element)return;const definition=options.definition,series=result.series||[],selectedSource=options.selectedSourceOrdinal??options.sourceRows?.filter(row=>row.raw).at(-1)?.source_ordinal;
    element.innerHTML=(result.events?.length?transformDisplay(result,definition):'')+seriesDisplay(series,options.sourceRows||[])+seasonalityDisplay(result.seasonality,options)+(series.length?'<h4>Exact series readout · selected actual source ordinal '+xml(selectedSource??'Unavailable')+'</h4>'+analysisTable(series.flatMap(s=>s.points.filter(p=>p.source_ordinal===selectedSource).map(p=>({series:s.name,units:s.units,source:p.source_ordinal,origin:p.origin_at,closed_at:p.closed_at,source_available_at:p.source_available_at,calculated_at:p.calculated_at,available:p.available_at,display_offset:p.display_offset,exact:p.raw,numerical:p.numerical_available,initialized:p.initialized,closed:p.closed,reasons:p.reasons})))):'');
    const select=event=>{const target=event.target.closest('[data-analysis-event-ordinal]');if(target&&(event.type==='click'||event.key==='Enter'||event.key===' ')){event.preventDefault();options.onSelect?.(Number(target.dataset.analysisEventOrdinal));}};element.addEventListener('click',select);element.addEventListener('keydown',select);
  }

  return {mount,mountAnalysis,dispose,compare,timeValue,formatTime,controller:element=>mounted.get(element)?.controller};
})();
