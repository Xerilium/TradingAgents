'use strict';
(() => {
 const get=id=>document.getElementById(id);let token='',candidate=null,busy=false,finished=false;
 async function request(path,body){
  const response=await fetch(path,{credentials:'same-origin',headers:body?{'Content-Type':'application/json','X-CSRF-Token':token}:{},method:body?'POST':'GET',body:body?JSON.stringify(body):undefined});
  const value=await response.json();if(!response.ok)throw new Error(value.error||'Recovery request failed');return value;
 }
 function controls(){get('preview').disabled=busy||finished;get('restore').disabled=busy||finished||!candidate||get('confirmation').value!=='RESTORE LOCAL RECORDS';}
 get('confirmation').addEventListener('input',controls);
 get('archive').addEventListener('change',()=>{candidate=null;get('manifest').textContent='';controls();});
 async function act(action){
  if(busy||finished)return;busy=true;controls();
  try{
   if(action==='preview'){
    candidate=null;const file=get('archive').files[0];if(!file||file.size>64*1024*1024)throw new Error('Choose a backup ZIP no larger than 64 MiB');
    const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let index=0;index<bytes.length;index+=32768)binary+=String.fromCharCode(...bytes.subarray(index,index+32768));
    candidate=await request('/api/recovery',{action:'preview',archive:btoa(binary)});get('manifest').textContent=JSON.stringify(candidate,null,2);get('message').textContent='Archive inspected. Review the manifest and checksum before confirming.';
   }else{
    const result=await request('/api/recovery',{action:'restore',token:candidate?.token,confirmation:get('confirmation').value});finished=result.restart_required===true;get('message').textContent=result.message;if(result.promoted)location.reload();
   }
  }catch(error){get('message').textContent=error.message;}finally{busy=false;controls();}
 }
 get('preview').addEventListener('click',()=>act('preview'));get('restore').addEventListener('click',()=>act('restore'));
 request('/api/state').then(value=>{token=value.csrf_token;finished=value.health.restart_required===true;get('health').textContent=JSON.stringify(value.health,null,2);controls();}).catch(error=>{get('message').textContent=error.message;});
})();
