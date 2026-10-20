/* Fixture controller only: local UI intent, never server approval. */
(function(root){
    function createState(){
        let key='',accepted=false;
        return {update(scene,input){const next=JSON.stringify([scene,input?.planResult?.data?.plan?.plan_id,input?.planResult?.data?.plan_sha256,input?.planResult?.data?.plan]);if(next!==key)accepted=false;key=next;return accepted;},confirm(value){accepted=value===true;},get accepted(){return accepted;}};
    }
    if(typeof module!=='undefined'&&module.exports){module.exports={createState};return;}
    const state=createState(),select=document.getElementById('scenario'),content=document.getElementById('content'),check=document.getElementById('riskIntent'),message=document.getElementById('intent');
    for(const name of root.PackageFixtures.names){const option=document.createElement('option');option.value=option.textContent=name;select.append(option);}
    function load(){const input=root.PackageFixtures.get(select.value);state.update(select.value,input);check.checked=state.accepted;content.innerHTML=root.PackagePreview.render(input);message.textContent='尚未表达本地确认意向；没有服务端批准事实。';document.getElementById('formalApprove').disabled=true;}
    select.addEventListener('change',load);
    check.addEventListener('change',()=>{state.confirm(check.checked);message.textContent=state.accepted?'仅记录本地 UI 风险确认意向；不生成 preview_id，不批准、不执行。':'本地确认意向已清除。';});
    load();root.PackageDemo={state,load};
})(typeof window==='undefined'?globalThis:window);
