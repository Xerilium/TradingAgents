'use strict';
fetch('/api/state',{credentials:'same-origin'}).then(async response=>{
 const value=await response.json();if(!response.ok)throw new Error(value.error||'Saved-record inspection failed');
 document.getElementById('health').textContent=JSON.stringify(value.health,null,2);
}).catch(error=>{document.getElementById('message').textContent=error.message;});
