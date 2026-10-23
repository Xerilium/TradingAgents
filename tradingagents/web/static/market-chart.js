'use strict';

// Retained provider bars only. This adapter never fetches or synthesizes data.
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
    item.chart.remove();mounted.delete(element);
  }while(ranges.size>32)ranges.delete(ranges.keys().next().value);}
  new MutationObserver(dispose).observe(document.documentElement,{childList:true,subtree:true});
  function mount(element,{bars,indicators=[],key,onSelect,timeframe='1Day',comparison=null,logicalRange=null,onRangeChange}){
    dispose();if(!element||mounted.has(element))return;
    if(!window.LightweightCharts){element.textContent='Chart library unavailable. Recorded OHLCV remains available below.';return;}
    try{
      ordered(bars,timeframe);if(comparison&&comparison.timeframe!==timeframe)throw new Error('Comparison interval differs from chart interval.');
      const library=window.LightweightCharts,style=getComputedStyle(element);
      const chart=library.createChart(element,{autoSize:true,height:280,
        layout:{background:{color:style.getPropertyValue('--surface').trim()||'#1c2933'},textColor:style.getPropertyValue('--fg').trim()||'#c7d1d9'},
        grid:{vertLines:{color:'#2c3d49'},horzLines:{color:'#2c3d49'}},timeScale:{timeVisible:timeframe!=='1Day',secondsVisible:false},
        localization:{priceFormatter:value=>Number(value).toFixed(2),timeFormatter:time=>formatTime(time,timeframe)}});
      mounted.set(element,{chart,key});
      if(comparison){
        chart.priceScale('right').applyOptions({mode:library.PriceScaleMode.Normal});
        comparison.series.forEach((item,index)=>{const line=chart.addSeries(library.LineSeries,{color:['#86d6ab','#e6c17d'][index],title:item.symbol+' close index',priceScaleId:'right',priceLineVisible:false});line.setData(item.points.map(point=>({time:point.time,value:point.value})));});
      }else{
        const candles=chart.addSeries(library.CandlestickSeries,{upColor:'#86d6ab',downColor:'#dc8995',borderVisible:false,wickUpColor:'#86d6ab',wickDownColor:'#dc8995'});
        candles.setData(bars.map(b=>({time:b.t,open:b.o,high:b.h,low:b.l,close:b.c})));
        const volume=chart.addSeries(library.HistogramSeries,{priceFormat:{type:'volume'},priceScaleId:'volume'});
        volume.priceScale().applyOptions({scaleMargins:{top:.82,bottom:0},visible:false});
        volume.setData(bars.map(b=>({time:b.t,value:b.v,color:b.c>=b.o?'#386c58':'#704650'})));
        indicators.filter(i=>/sma|ema/.test(i.name)).forEach((item,index)=>{
          const series=chart.addSeries(library.LineSeries,{color:['#e6c17d','#86d6ab','#a5b3c0'][index%3],lineWidth:1,title:item.name,priceLineVisible:false});
          const dates=new Set(bars.map(b=>b.t));series.setData(item.points.filter(p=>dates.has(p.t)&&Number.isFinite(p.value)).map(p=>({time:p.t,value:p.value})));
        });
      }
      chart.subscribeClick(event=>{if(event.time!==undefined&&event.time!==null&&onSelect)onSelect(timeValue(event.time,timeframe));});
      const range=logicalRange||ranges.get(key);if(range)chart.timeScale().setVisibleLogicalRange(range);else chart.timeScale().fitContent();
      if(onRangeChange)chart.timeScale().subscribeVisibleLogicalRangeChange(range=>{if(range)onRangeChange({from:range.from,to:range.to});});
    }catch{const item=mounted.get(element);item?.chart.remove();mounted.delete(element);element.textContent='Chart could not render these saved bars. Use the recorded session values below.';}
  }
  return {mount,dispose,compare,timeValue,formatTime};
})();
