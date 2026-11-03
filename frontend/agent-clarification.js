/* Render only authoritative questions; no local classification decisions. */
window.AgentClarification = {
    render(host, snapshot, submit) {
        host.replaceChildren(); host.hidden = snapshot?.task?.status !== 'awaiting_clarification';
        if (host.hidden) return;
        const data = snapshot.clarification;
        if (!data || typeof data.clarification_id !== 'string' || !data.clarification_id || !Array.isArray(data.questions) || !data.questions.length ||
            data.questions.some(q=>!q || typeof q.question_id!=='string' || !q.question_id || typeof q.question!=='string' || typeof q.reason!=='string' ||
                !Array.isArray(q.file_paths) || !Array.isArray(q.options) || [...q.file_paths,...q.options].some(s=>typeof s!=='string')) ||
            new Set(data.questions.map(q=>q.question_id)).size!==data.questions.length) {
            host.textContent = '缺少有效的后端澄清问题，无法提交回答。'; return;
        }
        const title = document.createElement('h3'); title.textContent = '需要你确认材料用途'; host.append(title);
        const fields = [];
        for (const q of data.questions) {
            const section = document.createElement('section');
            for (const text of [q.question, q.reason, ...(q.file_paths || [])]) {
                const p = document.createElement('p'); p.textContent = String(text); p.style.overflowWrap='anywhere'; section.append(p);
            }
            const input = document.createElement('textarea'); input.setAttribute('aria-label', q.question); input.maxLength=4000;
            for (const option of q.options || []) {
                const button = document.createElement('button'); button.type='button'; button.textContent=option;
                button.onclick=()=>{input.value=option;}; section.append(button);
            }
            section.append(input); host.append(section); fields.push({q,input});
        }
        const note=document.createElement('p');note.textContent='回答将重新规划，不代表批准任何文件操作。';host.append(note);
        const error=document.createElement('p');error.setAttribute('role','alert');host.append(error);
        const button=document.createElement('button');button.type='button';button.textContent='提交回答并继续规划';
        button.onclick=async()=>{
            if(button.disabled)return;
            const answers=fields.map(({q,input})=>({question_id:q.question_id,answer:input.value.trim()}));
            if(answers.some(a=>!a.answer)){error.textContent='请回答每个问题。';return;}
            button.disabled=true;error.textContent='';
            try{await submit(data.clarification_id,answers);}catch(e){error.textContent=e.message;button.disabled=false;}
        };host.append(button);
    }
};
