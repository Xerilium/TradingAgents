/* Native status follows the application's accepted state snapshot. */
let nativeProfileDraft=null;
function renderNativeProfile(runtime){
 let host=document.querySelector('#native-execution-profile');
 if(!host){host=document.createElement('section');host.id='native-execution-profile';host.innerHTML='<label>Native execution profile<select id="native-profile-select"><option value="long_only">Long-only default</option><option value="bounded_risk_spread_v1">Bounded-risk option spreads</option></select></label><p id="native-profile-help"></p><details><summary>Actual account, eligibility and native session evidence</summary><pre id="native-profile-evidence"></pre></details>';document.querySelector('#nautilus-account').after(host);host.querySelector('select').addEventListener('change',e=>{nativeProfileDraft=e.target.value;renderNativeProfile(state.nautilus||{});});}
 const stopped=['stopped','disconnected'].includes(runtime.status||'stopped'),transition=runtime.profile_transition||{},selected=runtime.execution_profile||transition.selected_profile||'long_only',select=host.querySelector('select');
 if(!stopped)nativeProfileDraft=null;
 select.value=nativeProfileDraft||selected;select.disabled=!stopped||busy.has('native');
 host.querySelector('#native-profile-help').textContent='Selection changes native representation only after an explicit stopped-session Start and fresh eligibility validation. It does not enable a broker account or permissions. Active sessions cannot change profile. Selected session: '+selected+'; eligibility '+(transition.eligibility?.eligible===true?'supported at its recorded observation':transition.eligibility?.eligible===false?'blocked':'unverified')+'. Paper margin simulation is distinct from live legal account classification. Missing applicable account/mapping evidence, current permissions, balances or required margins remain unknown; option level, multiplier and shorting flag alone do not prove eligibility. Bounded native total=broker equity, locked=initial margin, free=equity−initial margin is a derived diagnostic projection, not spendable cash or a pending reservation. Native Portfolio.equity can add unrealized P/L again and is not broker actual equity.';
 const a=runtime.account||{};host.querySelector('pre').textContent=JSON.stringify({profile_transition:transition,native_balance:runtime.native_balance??null,account_observed_at:runtime.account_at,broker_reported:{account_id:a.id??null,cash:a.cash??null,buying_power:a.buying_power??null,options_buying_power:a.options_buying_power??null,initial_margin:a.initial_margin??null,maintenance_margin:a.maintenance_margin??null}},null,2);
}
function renderNautilus(runtime){
  renderNativeProfile(runtime);
  document.querySelector('#nautilus-status').textContent=stateErrorMessage?'Nautilus connection unconfirmed · last snapshot shown':'Nautilus '+(runtime.version||'')+': '+(runtime.status||'stopped')+(runtime.error?' · '+runtime.error:'');
  const account=runtime.account,configured=new Set(runtime.desired_symbols||[]),prices=runtime.market_data||{},hasPrice=s=>Boolean(prices[s]?.trade||prices[s]?.quote),outside=[...new Set((runtime.positions||[]).map(p=>p.symbol))].filter(s=>!configured.has(s));
  document.querySelector('#nautilus-account').textContent=account?'Account '+account.id+' · '+(state?.connection?.endpoint||'Configured origin unavailable')+(runtime.execution_profile==='bounded_risk_spread_v1'?' · broker cash '+account.cash+' · broker equity '+account.equity+' · derived native diagnostic total '+(runtime.native_balance?.total??'Unavailable')+' / locked '+(runtime.native_balance?.locked??'Unavailable')+' / free '+(runtime.native_balance?.free??'Unavailable'):' · Nautilus cash '+runtime.nautilus_cash)+' · observed '+runtime.account_at:'Nautilus account unavailable';
  document.querySelector('#nautilus-quote').textContent=[...configured].filter(hasPrice).length+' / '+configured.size+' configured stocks with IEX prices · '+outside.filter(hasPrice).length+' / '+outside.length+' outside-universe holdings with prices · checked '+(runtime.prices_checked_at||'pending');
  document.querySelector('#nautilus-start').disabled=busy.has('native')||['starting','connected','stale','error'].includes(runtime.status);
  document.querySelector('#nautilus-stop').disabled=busy.has('native')||['stopped','disconnected'].includes(runtime.status||'stopped');
}
(() => {
  async function update(action){
    if(busy.has('native'))return;
    busy.add('native');renderNautilus(state?.nautilus||{});
    const button=document.querySelector('#nautilus-'+action);button.textContent=action==='start'?'Starting Nautilus…':'Stopping Nautilus…';
    try{await api('/api/nautilus/'+action,action==='start'?{execution_profile:document.querySelector('#native-profile-select').value}:{});await readState({force:true});}
    catch(error){setError((action==='start'?'Start Nautilus: ':'Stop Nautilus: ')+error.message);}
    finally{busy.delete('native');button.textContent=action==='start'?'Start Nautilus':'Stop Nautilus';renderNautilus(state?.nautilus||{});}
  }
  document.querySelector('#nautilus-start').addEventListener('click',()=>update('start'));
  document.querySelector('#nautilus-stop').addEventListener('click',()=>update('stop'));
  if(state)renderNautilus(state.nautilus||{});
  document.addEventListener('click', async event => {
    const button = event.target.closest('[data-action]');
    if (!button || button.disabled) return;
    if (button.dataset.action === 'open-saved-result') {
      selectedRunId = button.dataset.run;
      selectedSymbol = button.dataset.symbol;
      activePage = 'research';
      location.hash = 'research';
      await readState({force: true});
      return;
    }
  });
})();
