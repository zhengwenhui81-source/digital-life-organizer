/* Synthetic fixtures only. Paths and results are illustrative; nothing is executed. */
(function(root){
    const ok=(tool,data)=>({tool,success:true,data,message:tool+' synthetic result',error:null});
    const names=['complete','risks','success','partial','cleanup_failed','unknown_residual','bad_index','mismatch','missing','null','empty','wrong_type','long','non_package','missing_unresolved','stale_success','invalid_cleanup','unsafe_timestamp','executing','verifying','verification_failed','cleanup_succeeded'];
    function get(name='complete'){
        const requested=name;
        if(['executing','verifying','verification_failed'].includes(name))name='success';
        if(name==='cleanup_succeeded')name='partial';
        const task={task_id:'fixture_task',user_goal:'准备虚构课程结题材料',workspace:'E:\\虚构输入',status:'awaiting_approval'};
        const ref={file_id:'fixture_file_1',path:'E:\\虚构输入\\结题报告.txt',filename:'结题报告.txt'};
        const results=[ok('extract_requirements',{required_documents:['报告']}),ok('match_requirements',{required_documents:['报告'],matched:[{requirement:'报告',documents:[ref,{...ref,file_id:'fixture_file_2',filename:'报告_v2.txt',path:'E:\\虚构输入\\报告_v2.txt'}]}],missing:[]}),ok('detect_conflicts',{conflicts:[]}),ok('compare_versions',{groups:[]})];
        const analysis=Object.fromEntries(results.map((result,result_index)=>[result.tool,{result_index,result}]));
        const plan={plan_id:'package_plan_'+'1'.repeat(32),task:{task_id:task.task_id,user_goal:task.user_goal,workspace:task.workspace},destination:'E:\\虚构输入\\材料包（未创建）',selected_files:[{source:ref,requirements:['报告'],reason:'合成候选中的提议；未获用户确认',target:'E:\\虚构输入\\材料包（未创建）\\结题报告.txt',snapshot:{size:128,mtime_ns:123456789,sha256:'a'.repeat(64)}}],analysis,missing:[],unresolved:[],report:{path:'E:\\虚构输入\\材料包（未创建）\\PACKAGE_REPORT.md',content:'# Fixture 冻结计划\n审批前冻结的计划记录；不证明实际执行或验证成功。\n选材为提议。文件名候选不是内容审核。',sha256:'b'.repeat(64)},operations:[{kind:'create_directory',step_id:'package_001'},{kind:'copy',step_id:'package_002',selected_file_index:0},{kind:'write_report',step_id:'package_003'},{kind:'verify',step_id:'package_004'}],verification_targets:{selected_file_indices:[0],report:true,exact_directory_entries:true}};
        const digest='sha256:'+'c'.repeat(64),planResult=ok('plan_package',{plan,plan_sha256:digest});results.push(planResult);
        const snapshot={task,plan:null,results,pending_operations:[],preview_id:null,error:null,package_execution:null};
        const data={planResult,snapshot,report:null};
        if(['risks','success','partial','cleanup_failed','unknown_residual','stale_success','invalid_cleanup','unsafe_timestamp'].includes(name)){
            plan.missing=['签字页'];results[1].data.missing=['签字页'];
            plan.unresolved=['selection_pending','version_undecided','conflict','analysis_not_run'].map((kind,i)=>({kind,text:['另一个材料尚未提议选取','没有可确定的最新版本','两份通知日期冲突','未运行冲突分析'][i],source_tool:['match_requirements','compare_versions','detect_conflicts','extract_requirements'][i],source_result_index:i===3?null:[1,3,2][i],documents:i===3?[]:[ref]}));
            plan.unresolved[3].text='未运行需求提取分析';plan.analysis.extract_requirements=null;
            results[0]=ok('list_files',{files:[]}); // No successful extraction is claimed for this not-run slot.
            results[2].data.conflicts=[{field:'deadline',values:[{value:'虚构日期 A',source:ref},{value:'虚构日期 B',source:ref}]}];
            results[3].data.groups=[{group_id:'fixture_version_group',documents:[ref],newest_candidate:null,recommendation_reason:'insufficient_evidence'}];
            plan.report.content+='\n缺项：签字页。另有选材、版本、冲突及未执行分析风险。';
        }
        if(['success','partial','cleanup_failed','unknown_residual','bad_index','mismatch','missing_unresolved','stale_success','invalid_cleanup','unsafe_timestamp'].includes(name)){
            const success=['success','bad_index','mismatch','missing_unresolved','unsafe_timestamp'].includes(name);
            if(!success){
                plan.selected_files.push({source:{file_id:'fixture_file_3',path:'E:\\虚构输入\\原始记录.txt',filename:'原始记录.txt'},requirements:[],reason:'虚构补充材料提议',target:plan.destination+'\\原始记录.txt',snapshot:{size:64,mtime_ns:123456789,sha256:'d'.repeat(64)}});
                plan.operations=[{kind:'create_directory',step_id:'package_001'},{kind:'copy',step_id:'package_002',selected_file_index:0},{kind:'copy',step_id:'package_003',selected_file_index:1},{kind:'write_report',step_id:'package_004'},{kind:'verify',step_id:'package_005'}];
                plan.verification_targets.selected_file_indices=[0,1];
            }
            task.status=success?'completed':'failed';
            const children=[ok('create_folder',{path:plan.destination}),ok('copy_file',{source:ref.path,destination:plan.selected_files[0].target})];
            if(success)children.push(ok('write_package_report',{path:plan.report.path,sha256:plan.report.sha256}),ok('verify_result',{passed:true,checks:[{path:plan.selected_files[0].target,kind:'material-digest',passed:true},{path:plan.report.path,kind:'report-digest',passed:true},{path:plan.destination,kind:'file-set',passed:true},{path:plan.task.workspace,kind:'source-snapshot',passed:true}]}));
            else children.push({tool:'copy_file',success:false,data:null,message:'合成第二次复制失败',error:'Fixture: second copy failed; first copied target retained'});
            const operation_results=children.map((r,i)=>({step_id:plan.operations[i].step_id,result_index:5+i}));results.push(...children);
            const final_result_index=results.length;
            results.push(success?ok('build_package',{plan_id:plan.plan_id,plan_sha256:digest,package_path:plan.destination,generated_files:[plan.selected_files[0].target,plan.report.path],report_path:plan.report.path,verification_result_index:8}):{tool:'build_package',success:false,data:null,message:'合成执行失败',error:'Fixture: partially created; no retry'});
            snapshot.package_execution={plan_id:plan.plan_id,plan_sha256:digest,operation_results,final_result_index,cleanup_results:[{step_id:'package_002',status:'not_attempted',reason:'copy_succeeded',residual_state:'absent'}]};
            if(!success){
                snapshot.error='Fixture: 部分操作成功，目录及首次复制文件保留；第二次复制失败，报告和验证未执行';
                snapshot.package_execution.cleanup_results.push({step_id:'package_003',status:'not_attempted',reason:'Fixture: source read failed before target creation',residual_state:'absent'});
            }
            if(success)data.report={task_id:task.task_id,status:'completed',found_files:[],version_groups:results[3].data.groups,conflicts:results[2].data.conflicts,operations:children.filter(r=>r.tool!=='verify_result'),missing_items:plan.missing,package_path:plan.destination,summary:plan.missing.length?'打包执行成功，但材料包仍有缺项或未决事项；文件名候选不是材料审核。':'文件操作与文件验证成功；不代表材料审核通过。',package_unresolved:{plan_id:plan.plan_id,plan_sha256:digest,items:plan.unresolved}};
        }
        if(name==='cleanup_failed'||name==='unknown_residual')snapshot.package_execution.cleanup_results[1]={step_id:'package_003',status:name==='cleanup_failed'?'failed':'not_attempted',reason:name==='cleanup_failed'?'Fixture: safely bound owned-fragment removal attempt failed':'Fixture: ownership could not be safely confirmed; no removal attempted',residual_state:name==='cleanup_failed'?'owned_fragment':'unknown'};
        // Deliberately malformed evidence, kept separate from consistent failure examples.
        if(name==='invalid_cleanup')snapshot.package_execution.cleanup_results.pop();
        // Ordinary fixture timestamps are synthetic small exact integers, not real file times.
        if(name==='unsafe_timestamp')plan.selected_files[0].snapshot.mtime_ns=1792310400000000000;
        if(name==='bad_index')snapshot.package_execution.operation_results[0].result_index=999;
        if(name==='mismatch')snapshot.package_execution.plan_id='another_plan';
        if(name==='missing_unresolved')delete data.report.package_unresolved;
        if(name==='stale_success'){
            // Add historical evidence and shift every current reference together.
            results.unshift(ok('build_package',{plan_id:'package_plan_'+'9'.repeat(32),plan_sha256:'sha256:'+'9'.repeat(64),package_path:'E:\\旧结果',generated_files:[],report_path:'E:\\旧结果\\PACKAGE_REPORT.md',verification_result_index:null}));
            for(const slot of Object.values(plan.analysis))if(slot!==null)slot.result_index++;
            for(const u of plan.unresolved)if(u.source_result_index!==null)u.source_result_index++;
            for(const link of snapshot.package_execution.operation_results)link.result_index++;
            snapshot.package_execution.final_result_index++;
        }
        if(name==='missing')delete plan.selected_files;
        if(name==='null')return {planResult:null,snapshot:null,report:null};
        if(name==='empty'){plan.selected_files=[];plan.operations=[];}
        if(name==='wrong_type'){plan.missing={};plan.unresolved='invalid';plan.operations=42;}
        if(name==='long'){ref.path='E:\\'+ '很长的虚构目录\\'.repeat(35)+'报告.txt';plan.selected_files[0].snapshot.sha256='a'.repeat(1024);}
        if(name==='non_package')return {planResult:null,snapshot:{task:{task_id:'analysis',status:'completed'},results:[]},report:{task_id:'analysis',status:'completed',package_path:'',operations:[],missing_items:[],summary:'分析结束'}};
        if(['executing','verifying'].includes(requested)){
            const count=requested==='executing'?1:3;
            task.status=requested;data.report=null;
            results.length=5+count;
            snapshot.package_execution.operation_results=snapshot.package_execution.operation_results.slice(0,count);
            snapshot.package_execution.final_result_index=null;
            if(requested==='executing')snapshot.package_execution.cleanup_results=[];
        }
        if(requested==='verification_failed'){
            task.status='failed';data.report=null;snapshot.error='Fixture: material digest verification failed';
            results[8]={tool:'verify_result',success:false,data:null,message:'verification failed',error:snapshot.error};
            results[9]={tool:'build_package',success:false,data:null,message:'build failed',error:snapshot.error};
        }
        if(requested==='cleanup_succeeded')snapshot.package_execution.cleanup_results[1]={step_id:'package_003',status:'succeeded',reason:'Fixture: safely bound owned failed-copy fragment removed',residual_state:'absent'};
        return JSON.parse(JSON.stringify(data));
    }
    const api={get,names};if(typeof module!=='undefined'&&module.exports)module.exports=api;else root.PackageFixtures=api;
})(typeof window==='undefined'?globalThis:window);
