/* Native status follows the application's accepted state snapshot. */
function renderNautilus(runtime){
  document.querySelector('#nautilus-status').textContent='Nautilus '+(runtime.version||'')+': '+(runtime.status||'stopped')+(runtime.error?' · '+runtime.error:'');
  const account=runtime.account,configured=new Set(runtime.desired_symbols||[]),prices=runtime.market_data||{},hasPrice=s=>Boolean(prices[s]?.trade||prices[s]?.quote),outside=[...new Set((runtime.positions||[]).map(p=>p.symbol))].filter(s=>!configured.has(s));
  document.querySelector('#nautilus-account').textContent=account?'Account '+account.id+' · '+(state?.connection?.endpoint||'Configured origin unavailable')+' · Nautilus cash '+runtime.nautilus_cash+' · observed '+runtime.account_at:'Nautilus account unavailable';
  document.querySelector('#nautilus-quote').textContent=[...configured].filter(hasPrice).length+' / '+configured.size+' configured stocks with IEX prices · '+outside.filter(hasPrice).length+' / '+outside.length+' outside-universe holdings with prices · checked '+(runtime.prices_checked_at||'pending');
  document.querySelector('#nautilus-start').disabled=busy.has('native')||['starting','connected','stale','error'].includes(runtime.status);
  document.querySelector('#nautilus-stop').disabled=busy.has('native')||['stopped','disconnected'].includes(runtime.status||'stopped');
}
(() => {
  async function update(action){
    if(busy.has('native'))return;
    busy.add('native');renderNautilus(state?.nautilus||{});
    try{await api('/api/nautilus/'+action,{});await readState({force:true});}
    catch(error){setError(error.message);}
    finally{busy.delete('native');renderNautilus(state?.nautilus||{});}
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
