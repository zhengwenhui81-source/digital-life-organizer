/* Pure presentation of unimplemented Package contracts. No IO or authorization. */
(function(root){
    'use strict';
    const arr=Array.isArray, obj=v=>v!==null&&typeof v==='object'&&!arr(v);
    const str=v=>typeof v==='string'&&v.trim().length>0;
    const esc=v=>String(v??'未提供').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const json=v=>JSON.stringify(v,null,2)??'未提供';
    const pre=v=>'<pre>'+esc(typeof v==='string'?v:json(v))+'</pre>';
    const section=(title,body)=>'<section><h2>'+esc(title)+'</h2>'+body+'</section>';
    const labels={selection_pending:'选材待确认',version_undecided:'版本未决',conflict:'来源冲突',analysis_not_run:'分析未执行'};
    const slots=['extract_requirements','match_requirements','detect_conflicts','compare_versions'];
    // Compare data without serialization: own fields and types are significant;
    // object insertion order is not. Reject accessors, exotic objects and cycles.
    function equalData(a,b,activeA=new WeakSet(),activeB=new WeakSet()){
        if(a===null||b===null||typeof a!=='object'||typeof b!=='object'){
            // Rounded JSON integers cannot establish exact source equality.
            if([a,b].some(v=>typeof v==='number'&&(!Number.isFinite(v)||(Number.isInteger(v)&&!Number.isSafeInteger(v)))))return false;
            return typeof a===typeof b&&typeof a!=='function'&&Object.is(a,b);
        }
        if(arr(a)!==arr(b)||activeA.has(a)||activeB.has(b))return false;
        if(!arr(a)&&[a,b].some(v=>![Object.prototype,null].includes(Object.getPrototypeOf(v))))return false;
        const keys=Reflect.ownKeys(a),other=Reflect.ownKeys(b);
        if(keys.length!==other.length||keys.some(k=>typeof k!=='string'||!Object.hasOwn(b,k)))return false;
        activeA.add(a);activeB.add(b);
        try{return keys.every(k=>{
            const left=Object.getOwnPropertyDescriptor(a,k),right=Object.getOwnPropertyDescriptor(b,k);
            return Object.hasOwn(left,'value')&&Object.hasOwn(right,'value')&&equalData(left.value,right.value,activeA,activeB);
        });}finally{activeA.delete(a);activeB.delete(b);}
    }
    const list=v=>arr(v)?v:[];
    const resultRecord=v=>obj(v)&&str(v.tool)&&typeof v.success==='boolean'&&Object.hasOwn(v,'data')&&typeof v.message==='string'&&Object.hasOwn(v,'error')&&(v.success?obj(v.data)&&v.error===null:v.data===null&&str(v.error));
    function inspect(input={}){
        const {planResult:r,snapshot:s,report}=input||{}, p=r?.data?.plan, errors=[];
        const warn=m=>errors.push(m);
        const operations=list(p?.operations), results=list(s?.results);
        const taskValid=obj(p?.task)&&['task_id','user_goal','workspace'].every(k=>str(p.task[k]));
        const taskMatches=taskValid&&obj(s?.task)&&['task_id','user_goal','workspace'].every(k=>s.task[k]===p.task[k]);
        if(p&&!taskValid)warn('方案数据不完整：任务信息缺失或无效');
        if(s!=null&&(!obj(s)||!obj(s.task)||!str(s.task.task_id)||!arr(s.results)||results.some(v=>!resultRecord(v))))warn('执行记录不完整/无效：Snapshot.results 或任务字段无效');
        if(s!=null&&!['created','planning','awaiting_approval','executing','verifying','completed','failed'].includes(s?.task?.status))warn('任务状态缺失或无效');
        if(!obj(p)||r?.tool!=='plan_package'||r.success!==true)warn('没有成功且完整的 Package 计划');
        if(obj(p)){
            if(!str(p.plan_id)||!str(r.data.plan_sha256)||!obj(p.task)||!str(p.task.task_id)||!str(p.task.user_goal)||!str(p.destination))warn('方案身份或目标字段缺失');
            if(!/^package_plan_[a-f0-9]{32}$/.test(p.plan_id)||!/^sha256:[a-f0-9]{64}$/.test(r.data.plan_sha256))warn('方案 ID 或摘要格式不正确');
            for(const key of ['selected_files','missing','unresolved','operations'])if(!arr(p[key]))warn(key+' 不是数组');
            if(!p.selected_files?.length)warn('提议选材为空');
            if(arr(p.selected_files)&&p.selected_files.some(f=>!obj(f)||!str(f.source?.file_id)||!str(f.source?.path)||!str(f.source?.filename)||!str(f.target)||!str(f.reason)||!arr(f.requirements)||!Number.isSafeInteger(f.snapshot?.size)||f.snapshot.size<0||!str(f.snapshot?.sha256)))warn('文件映射或快照数据不完整');
            if(arr(p.selected_files)&&p.selected_files.some(f=>!Number.isInteger(f?.snapshot?.mtime_ns)||!/^([a-f0-9]{64})$/.test(f?.snapshot?.sha256)))warn('文件快照时间或摘要格式不正确');
            if(arr(p.selected_files)&&p.selected_files.some(f=>Number.isInteger(f?.snapshot?.mtime_ns)&&!Number.isSafeInteger(f.snapshot.mtime_ns)))warn('纳秒时间戳超出 JavaScript 安全整数范围：精度无法确认，Number 相等不能证明来源快照一致；需 A/D 确认无损接入');
            const targets=p.verification_targets;
            if(!obj(targets)||Object.keys(targets).length!==3||!equalData(targets.selected_file_indices,list(p.selected_files).map((_,i)=>i))||targets.report!==true||targets.exact_directory_entries!==true)warn('verification_targets 缺失或无效：不能确认冻结验证范围');
            if(!obj(p.report)||!str(p.report.path)||typeof p.report.content!=='string'||!str(p.report.sha256))warn('冻结报告不完整');
            if(arr(p.missing)&&p.missing.some(v=>!str(v)))warn('missing 数据不完整');
            if(arr(p.unresolved)&&p.unresolved.some(v=>!obj(v)||!Object.hasOwn(labels,v.kind)||!str(v.text)||!arr(v.documents)))warn('未决事项数据不完整');
            for(const tool of slots){
                const slot=p.analysis?.[tool];
                if(slot===null){if(!list(p.unresolved).some(u=>u?.kind==='analysis_not_run'&&u.source_tool===tool&&u.source_result_index===null))warn(tool+' 未执行且缺少未决记录');}
                else if(!obj(slot)||slot.result?.tool!==tool||slot.result?.success!==true||!Number.isInteger(slot.result_index)||slot.result_index<0)warn(tool+' 分析来源缺失或失败');
                else if(s&&(!arr(s.results)||!equalData(s.results[slot.result_index],slot.result)||s.results.slice(slot.result_index+1).some(x=>x?.tool===tool)))warn(tool+' 分析来源不一致或已过期');
            }
            for(const u of list(p.unresolved)){
                const slot=p.analysis?.[u?.source_tool];
                const index=u?.source_result_index;
                const notRun=obj(u)&&u.kind==='analysis_not_run'&&slots.includes(u.source_tool)&&slot===null&&index===null;
                const expectedTool={selection_pending:'match_requirements',version_undecided:'compare_versions',conflict:'detect_conflicts'}[u?.kind];
                const linked=obj(u)&&u.source_tool===expectedTool&&Number.isInteger(index)&&index>=0&&obj(slot)&&slot.result_index===index&&resultRecord(slot.result)&&slot.result.success===true&&slot.result.tool===u.source_tool&&(!s||(arr(s.results)&&resultRecord(results[index])&&equalData(results[index],slot.result)&&!results.slice(index+1).some(v=>v?.tool===u.source_tool)));
                if(!notRun&&!linked)warn('未决事项来源关联无效：保留原始记录，不作为已确认分析结论');
            }
            if(s&&(!taskValid||s.task?.task_id!==p.task?.task_id))warn('任务标识不一致');
            if(s&&taskValid&&!taskMatches)warn('任务上下文不一致：task_id、user_goal 或 Workspace 缺失/不匹配');
            if(arr(p.operations)){
                const expected=['create_directory',...(arr(p.selected_files)?p.selected_files.map(()=> 'copy'):[]),'write_report','verify'];
                if(p.operations.length!==expected.length||p.operations.some((o,i)=>!obj(o)||o.kind!==expected[i]||!str(o.step_id)||(o.kind==='copy'&&o.selected_file_index!==i-1)))warn('操作顺序或选材索引不一致');
            }
            if(!arr(p.operations)||operations.some(o=>!obj(o)||!str(o.step_id)||!['create_directory','copy','write_report','verify'].includes(o.kind)))warn('执行记录不完整/无效：冻结操作描述无效');
        }
        const e=s?.package_execution;
        const same=obj(e)&&obj(p)&&taskMatches&&e.plan_id===p.plan_id&&e.plan_sha256===r?.data?.plan_sha256;
        let writes=[], verification=null, build=null;
        const attemptedCopies=[];
        if(e!=null){
            if(!same)warn('执行方案标识或摘要不一致');
            if(!arr(e.operation_results))warn('执行关联数据缺失');
            else for(const [position,link] of e.operation_results.entries()){
                const index=link?.result_index, result=Number.isInteger(index)&&index>=0?results[index]:null;
                const descriptor=operations.find(o=>obj(o)&&o.step_id===link?.step_id);
                const tools={create_directory:'create_folder',copy:'copy_file',write_report:'write_package_report',verify:'verify_result'};
                if(position>0&&results[e.operation_results[position-1]?.result_index]?.success===false)warn('执行记录不完整/无效：失败后仍有后续操作记录');
                if(!same||!obj(link)||!str(link.step_id)||!resultRecord(result)||!descriptor||operations[position]?.step_id!==link?.step_id||result.tool!==tools[descriptor.kind]||e.operation_results.slice(0,position).some(x=>x?.result_index===index)){warn('执行记录不完整/无效：操作结果索引或来源不一致');continue;}
                const selected=descriptor.kind==='copy'?p.selected_files?.[descriptor.selected_file_index]:null;
                if(descriptor.kind==='copy'&&(!obj(selected)||!obj(selected.source)||!str(selected.source.path)||!str(selected.target))){warn('执行记录不完整/无效：复制映射缺失');continue;}
                if(result.success===true&&((selected&&(result.data?.source!==selected.source?.path||result.data?.destination!==selected.target))||(descriptor.kind==='create_directory'&&result.data?.path!==p.destination)||(descriptor.kind==='write_report'&&(result.data?.path!==p.report?.path||result.data?.sha256!==p.report?.sha256)))){warn('操作结果文件映射不一致');continue;}
                if(descriptor.kind==='copy')attemptedCopies.push({step_id:link.step_id,result});
                if(result.tool==='verify_result')verification=result;
                else writes.push({step_id:link.step_id,result});
            }
            if(e.final_result_index!==null){
                build=Number.isInteger(e.final_result_index)&&e.final_result_index>=0?s?.results?.[e.final_result_index]:null;
                if(!same||!resultRecord(build)||build.tool!=='build_package'){warn('执行记录不完整/无效：最终结果索引不一致');build=null;}
                else{
                    if(list(e.operation_results).some(link=>!Number.isSafeInteger(link?.result_index)||link.result_index>=e.final_result_index))warn('最终执行结果来源不一致：终止结果必须在本次子操作之后');
                    if(build.success===true&&(build.data?.plan_id!==e.plan_id||build.data?.plan_sha256!==e.plan_sha256||build.data?.package_path!==p.destination||!Number.isSafeInteger(build.data?.verification_result_index)||build.data.verification_result_index<0||s.results?.[build.data?.verification_result_index]!==verification))warn('最终执行结果来源不一致');
                }
            }
            // Diagnose recorded observations only; never infer ownership or clean files.
            const cleanup=e.cleanup_results;
            if(!arr(cleanup))warn('cleanup_results 缺失或无效：清理及残留状态未知');
            else{
                const keys=['step_id','status','reason','residual_state'];
                if(cleanup.some(c=>!obj(c)||Object.keys(c).length!==keys.length||keys.some(k=>!Object.hasOwn(c,k))||!str(c.step_id)||!str(c.reason)||!['not_attempted','succeeded','failed'].includes(c.status)||!['absent','owned_fragment','other_object','unknown'].includes(c.residual_state)))warn('cleanup_results 记录不完整/无效：保留原始清理信息');
                if(cleanup.length!==attemptedCopies.length||attemptedCopies.some(copy=>cleanup.filter(c=>c?.step_id===copy.step_id).length!==1)||cleanup.some(c=>!attemptedCopies.some(copy=>copy.step_id===c?.step_id)))warn('cleanup_results 与已尝试复制关联不完整：缺失、重复或未知步骤，残留不可推断');
                if(cleanup.some(c=>c?.status==='failed'))warn('清理尝试失败：保留原始复制错误和清理原因，不表示已回滚');
                if(cleanup.some(c=>c?.residual_state==='unknown'))warn('清理残留状态未知：不能确认对象已移除，不表示已回滚');
                for(const copy of attemptedCopies){
                    const c=cleanup.find(c=>c?.step_id===copy.step_id);
                    if(!obj(c))continue;
                    if(copy.result.success?(c.status!=='not_attempted'||c.reason!=='copy_succeeded'||c.residual_state!=='absent'):(c.reason==='copy_succeeded'||(c.status==='succeeded'&&c.residual_state!=='absent')||(c.status==='failed'&&!['owned_fragment','unknown'].includes(c.residual_state))||(c.status==='not_attempted'&&c.residual_state==='owned_fragment')))warn('cleanup_results 与复制结果或残留状态矛盾：不能视为回滚成功');
                }
            }
        }
        if(verification?.success===true){
            const checks=verification.data?.checks;
            const required=[...(arr(p?.selected_files)?p.selected_files.map(f=>[f?.target,'material-digest']):[]),[p?.report?.path,'report-digest'],[p?.destination,'file-set'],[p?.task?.workspace,'source-snapshot']];
            if(verification.data?.passed!==true||!arr(checks)||checks.some(c=>c?.passed!==true)||required.some(([path,kind])=>!checks?.some?.(c=>c?.path===path&&c?.kind===kind&&c?.passed===true)))warn('文件验证检查缺失或未通过');
        }
        if(build?.success===true&&(e?.operation_results?.length!==p?.operations?.length||writes.some(w=>w.result.success!==true)))warn('成功构建缺少完整的成功操作证据');
        if(e!=null&&((build?.success===true&&s?.task?.status!=='completed')||(s?.task?.status==='completed'&&build?.success!==true)))warn('任务状态与当前 Package 执行结果不一致');
        const isPackage=!!p||e!=null||str(report?.package_path)||Object.hasOwn(report||{},'package_unresolved');
        if(report!=null&&!obj(report))warn('FinalReport 数据不完整/无效：必须为对象或未提供');
        if(report&&s&&report.task_id!==s.task?.task_id)warn('报告任务标识不一致');
        if(report&&isPackage){
            if(!obj(report)||report.status!=='completed'||report.status!==s?.task?.status)warn('Package 报告状态无效或与当前任务不一致');
            const u=report.package_unresolved;
            if(!obj(u)||!arr(u.items))warn('Package 报告缺少 package_unresolved');
            else if(!p||u.plan_id!==p.plan_id||u.plan_sha256!==r?.data?.plan_sha256||!equalData(u.items,p.unresolved)||!equalData(report.missing_items,p.missing))warn('报告与冻结风险来源不一致');
            if(s?.task?.status!=='completed'||build?.success!==true||verification?.success!==true||verification.data?.passed!==true)warn('未取得当前执行的成功与验证证据，不能确认 Package 成功');
            if(report.package_path!==build?.data?.package_path||!equalData(report.operations,writes.filter(w=>w.result.success===true).map(w=>w.result)))warn('报告路径或实际成功操作不一致');
            if(!equalData(report.conflicts,p?.analysis?.detect_conflicts?.result?.data?.conflicts))warn('报告冲突证据不一致');
        }
        if(s?.task?.status==='failed')warn('当前任务失败；旧成功结果不能代表当前成功');
        return {plan:p,errors,writes,verification,build,isPackage,hasRisks:!arr(p?.missing)||!arr(p?.unresolved)||!!(p.missing.length||p.unresolved.length),formalApprovalEnabled:false};
    }
    function render(input={}){
        const m=inspect(input),p=m.plan,s=input?.snapshot,report=input?.report;
        const risk=(missing,unresolved)=>'<h3>missing · 缺少文件名候选</h3>'+pre(missing)+'<h3>未决事项</h3>'+(arr(unresolved)?unresolved.map(u=>'<article><h4>'+esc(u?.kind)+' · '+esc(labels[u?.kind]||'未知风险')+'</h4>'+pre(u)+'</article>').join('')||'<p>未决数组为空，不代表内容审核通过。</p>':pre(unresolved));
        let html='<p class="warning">文件名候选不代表材料内容已经审核通过；版本推荐不代表用户确认选材。材料真实性、完整性及有效性未由本界面核验。</p>';
        html+=section('数据与来源检查',m.errors.length?'<p class="warning">数据不完整或来源待核对；不能确认方案有效及执行验证成功。</p><ul>'+m.errors.map(e=>'<li>'+esc(e)+'</li>').join('')+'</ul>':'<p>展示所需来源字段一致；不构成服务端授权。</p>');
        html+=section('1. 冻结方案',pre({goal:p?.task?.user_goal,destination:p?.destination,plan_id:p?.plan_id,plan_sha256:input?.planResult?.data?.plan_sha256})+'<p>计划生成：'+(input?.planResult?.success===true?'工具报告成功（未执行）':'未确认')+'</p><p>服务端任务状态：'+esc(s?.task?.status)+'；等待审批与执行成功是不同状态。</p>');
        html+=section('2. 具体文件映射 · proposed selected_files',arr(p?.selected_files)?p.selected_files.map((f,i)=>'<article><h3>提议文件 '+(i+1)+' · '+esc(f?.source?.filename)+'</h3><p>文件标识</p>'+pre(f?.source?.file_id)+'<p>源路径</p>'+pre(f?.source?.path)+'<p>目标路径</p>'+pre(f?.target)+'<p>选择依据</p>'+pre(f?.reason)+'<p>对应要求</p>'+pre(f?.requirements)+'<p>文件大小（字节） · '+esc(f?.snapshot?.size)+'</p><p>SHA-256（文件字节摘要）</p>'+pre(f?.snapshot?.sha256)+'</article>').join('')||'<p>选材为空；无法确认可执行方案。</p>':'<p>文件映射未提供。</p>');
        html+=section('3. 缺项与风险',risk(p?.missing,p?.unresolved)+'<h3>冻结分析与多候选证据</h3>'+pre(p?.analysis));
        html+=section('4. 操作顺序 · 仅计划',pre(p?.operations));
        html+=section('5. 冻结报告 · 审批前计划记录',pre(p?.report?.path)+pre(p?.report?.sha256)+pre(p?.report?.content));
        html+=section('执行结果 · 与计划分开',pre({task_status:s?.task?.status,error:s?.error})+'<h3>当前执行关联的操作结果（成功与失败分别标示）</h3>'+m.writes.map(w=>'<article><h4>'+esc(w.step_id)+' · '+(w.result.success===true?'文件操作执行成功':'文件操作失败')+'</h4>'+pre(w.result)+'</article>').join('')+'<h3>verification</h3>'+pre(m.verification)+'<p>文件验证：'+(s?.task?.status!=='failed'&&!m.errors.length&&m.verification?.success===true&&m.verification.data?.passed===true?'通过（仅文件检查）':'未确认通过')+'</p><h3>当前 build_package</h3>'+pre(m.build)+'<h3>cleanup_results · 契约已确认，后端尚未实现</h3>'+pre(s?.package_execution?.cleanup_results)+'<p>absent 仅描述失败片段；成功复制的文件仍可能保留。未知残留不等于已回滚；本界面不重试或清理。</p>');
        html+=section('FinalReport · 原始报告事实',report?pre(report):'<p>未提供 FinalReport；失败任务通过 Snapshot 查看，不回退到旧成功报告。</p>');
        if(m.errors.some(e=>e.includes('执行记录不完整/无效')))html+=section('无效执行记录 · 原始数据保留，不能当作成功操作',pre({operations:p?.operations,package_execution:s?.package_execution,results:s?.results}));
        if(report)html+=section('报告中的缺项与未决事项',risk(report.missing_items,report.package_unresolved?.items));
        return html;
    }
    // Read-only adapter: only the latest planning attempt in this exact Snapshot.
    // No cached success, inferred approval, transport or Fixture dependency.
    function inspectSnapshot(snapshot,expectedTask=snapshot?.task){
        const base={state:'unavailable',resultIndex:null,input:null,issues:[]};
        const invalid=message=>({...base,state:'invalid',issues:[message]});
        if(snapshot==null)return base;
        if(!obj(snapshot)||!obj(snapshot.task)||!arr(snapshot.results))return invalid('TaskSnapshot 数据格式异常：task/results 缺失或无效');
        const taskKeys=['task_id','user_goal','workspace'];
        if(!obj(expectedTask)||taskKeys.some(k=>!str(expectedTask[k])||snapshot.task[k]!==expectedTask[k]))return invalid('TaskSnapshot 与当前任务归属不一致或任务字段缺失');
        let resultIndex=-1;
        snapshot.results.forEach((result,index)=>{if(result?.tool==='plan_package')resultIndex=index;});
        if(resultIndex<0){
            if(snapshot.package_execution!=null)return invalid('存在 Package 执行关联但未提供对应规划结果；不能回退查找旧方案');
            if(snapshot.results.some(result=>!resultRecord(result)))return invalid('TaskSnapshot.results 包含格式异常的工具记录');
            return base;
        }
        const result=snapshot.results[resultIndex],current={...base,resultIndex};
        if(!resultRecord(result))return {...current,state:'invalid',issues:['当前 plan_package ToolResult 格式异常；不使用历史成功']};
        if(snapshot.task.status==='failed'||!result.success||snapshot.results.some(item=>item?.success===false))return {...current,state:'failed',issues:['当前任务或工具执行失败；不使用历史成功规划补齐预览',snapshot.error,result.error].filter(str)};
        const plan=result.data.plan;
        if(!obj(plan)||!obj(plan.task)||taskKeys.some(k=>plan.task[k]!==expectedTask[k]))return {...current,state:'invalid',issues:['规划结果与当前任务归属不一致或 plan/task 缺失；不展示跨任务方案']};
        if(snapshot.results.slice(resultIndex+1).some(item=>slots.includes(item?.tool)||item?.tool==='read_document'))return {...current,state:'invalid',issues:['规划之后存在新的分析或文档读取结果，冻结证据可能已过期；不回退展示旧方案']};
        const input={planResult:result,snapshot},issues=[...inspect(input).errors];
        for(const tool of slots){
            const slot=plan.analysis?.[tool];
            if(slot!=null&&(!Number.isSafeInteger(slot.result_index)||slot.result_index<0||slot.result_index>=resultIndex))issues.push(tool+' 分析索引未引用本次规划之前的结果');
        }
        if(snapshot.preview_id!=null&&!str(snapshot.preview_id))issues.push('preview_id 格式异常；不能确认服务端预览关联');
        if(snapshot.task.status==='awaiting_approval'&&!str(snapshot.preview_id))issues.push('等待审批但 preview_id 尚未提供；不能确认冻结预览绑定');
        if(str(snapshot.preview_id)&&(!arr(snapshot.pending_operations)||!snapshot.pending_operations.length))issues.push('preview_id 缺少对应 pending_operations；不能确认冻结操作关联');
        return {...current,state:issues.length?'invalid':'provided',input,issues};
    }
    function renderSnapshot(snapshot,expectedTask){
        const m=inspectSnapshot(snapshot,expectedTask);
        let html='<p class="warning">真实 TaskSnapshot 只读展示 · Package 批准与执行未接通；不构成服务端授权。</p>';
        if(m.state==='unavailable')return html+'<p>真实 Package 规划数据尚未提供。当前 Agent 可能尚未产生 plan_package ToolResult；不使用 Fixture 补齐。</p>';
        html+=pre({task_id:snapshot?.task?.task_id,plan_id:m.input?.planResult?.data?.plan?.plan_id,plan_sha256:m.input?.planResult?.data?.plan_sha256,preview_id:snapshot?.preview_id,result_index:m.resultIndex});
        if(m.issues.length)html+='<p class="warning">'+(m.state==='failed'?'当前失败，冻结预览不可用。':'数据不完整、格式异常或来源无法确认；不得视为有效当前冻结预览。')+'</p><ul>'+m.issues.map(issue=>'<li>'+esc(issue)+'</li>').join('')+'</ul>';
        else html+='<p>规划记录来自当前 Snapshot；'+(str(snapshot?.preview_id)?'preview_id 仅按服务端返回展示，权威绑定尚未验收。':'服务端审批预览尚未提供，当前仅为只读规划。')+'</p>';
        if(m.input)html+=render(m.input);
        return html;
    }
    const api={inspect,render,inspectSnapshot,renderSnapshot};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.PackagePreview=api;
})(typeof window==='undefined'?globalThis:window);
