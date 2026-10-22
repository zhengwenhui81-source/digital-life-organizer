/* Agreed Agent HTTP transport. Mock is always an explicit choice. */
window.AgentAPI = {
    mode: 'real',
    // Preserve large JSON integer tokens before Number can round mtime_ns.
    // BigInt is local presentation data, never sent as an authorization field.
    parseJSON(raw) {
        let i = 0;
        const space = () => { while (/[ \t\r\n]/.test(raw[i] || '') && i < raw.length) i++; };
        const value = () => {
            space(); const start = i, c = raw[i];
            if (c === '"') {
                i++;
                while (i < raw.length) { if (raw[i] === '\\') i += 2; else if (raw[i++] === '"') return JSON.parse(raw.slice(start, i)); }
                throw new SyntaxError('Unterminated JSON string');
            }
            if (c === '{' || c === '[') {
                const object = c === '{', out = object ? {} : []; i++; space();
                if (raw[i] === (object ? '}' : ']')) { i++; return out; }
                while (i < raw.length) {
                    let key;
                    if (object) { space(); if (raw[i] !== '"') throw new SyntaxError('Invalid key'); key = value(); space(); if (raw[i++] !== ':') throw new SyntaxError('Missing colon'); }
                    const item = value();
                    if (object) Object.defineProperty(out, key, {value:item, enumerable:true, configurable:true, writable:true}); else out.push(item);
                    space(); const end = raw[i++];
                    if (end === (object ? '}' : ']')) return out;
                    if (end !== ',') throw new SyntaxError('Missing separator');
                }
                throw new SyntaxError('Unterminated JSON collection');
            }
            const token = raw.slice(i).match(/^(?:true|false|null|-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?)/)?.[0];
            if (!token) throw new SyntaxError('Invalid JSON token');
            i += token.length;
            const parsed = JSON.parse(token);
            return /^-?\d+$/.test(token) && !Number.isSafeInteger(parsed) ? BigInt(token) : parsed;
        };
        const parsed = value(); space();
        if (i !== raw.length) throw new SyntaxError('Trailing JSON data');
        return parsed;
    },
    setMode(mode) {
        if (!['mock', 'real'].includes(mode)) throw new Error('Unknown API mode');
        this.mode = mode;
    },
    async request(path, method = 'GET', body, expectedStatus = 200) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        let response;
        try {
            response = await fetch(path, {
                method, signal: controller.signal,
                headers: {'Accept': 'application/json', ...(body === undefined ? {} : {'Content-Type': 'application/json'})},
                ...(body === undefined ? {} : {body: JSON.stringify(body)})
            });
            const raw = await response.text();
            let data;
            try { data = this.parseJSON(raw); }
            catch (_) {
                const error = new Error('HTTP ' + response.status + ': Agent backend returned invalid JSON');
                error.status = response.status;
                throw error;
            }
            if (!response.ok) {
                const detail = data?.detail ?? data?.error ?? data?.message;
                const error = new Error('HTTP ' + response.status + ': ' + (typeof detail === 'string' ? detail : detail ? JSON.stringify(detail, (_,v)=>typeof v==='bigint'?v.toString():v) : response.statusText || 'Agent request failed'));
                error.status = response.status;
                throw error;
            }
            if (response.status !== expectedStatus || !data || typeof data !== 'object' || Array.isArray(data)) {
                const error = new Error('HTTP ' + response.status + ': Unexpected Agent response');
                error.status = response.status;
                throw error;
            }
            return data;
        } catch (error) {
            if (error.status !== undefined) throw error;
            const failure = new Error(error.name === 'AbortError' ? 'Agent backend request timed out. 请刷新任务状态；文件操作不会自动重试。' : 'Agent backend unavailable: ' + error.message);
            failure.status = null;
            throw failure;
        } finally { clearTimeout(timer); }
    },
    taskPath(id) {
        if (typeof id !== 'string' || !id) throw new Error('Missing task_id');
        return '/api/agent/tasks/' + encodeURIComponent(id);
    },
    async createTask(userGoal, workspace, scenario = 'happy', interactive = false) {
        if (!userGoal?.trim() || !workspace?.trim()) throw new Error('Workspace and goal are required');
        if (this.mode === 'mock') return window.AgentMock.createTask({user_goal: userGoal, workspace, scenario});
        return this.request('/api/agent/tasks', 'POST', {user_goal: userGoal, workspace, ...(interactive ? {interactive:true} : {})}, 202);
    },
    async answerTask(id, clarificationId, answers) {
        if (this.mode !== 'real') throw new Error('澄清回答仅支持正式 Real Mode 接口');
        return this.request(this.taskPath(id) + '/answers', 'POST', {clarification_id:clarificationId, answers}, 202);
    },
    async getTask(id) {
        if (this.mode === 'mock') return window.AgentMock.getTask(id);
        return this.request(this.taskPath(id));
    },
    async approveTask(id, previewId, acceptIncomplete) { return this.decideTask(id, previewId, true, acceptIncomplete); },
    async rejectTask(id, previewId) { return this.decideTask(id, previewId, false); },
    async decideTask(id, previewId, approve, acceptIncomplete) {
        if (acceptIncomplete !== undefined && typeof acceptIncomplete !== 'boolean') throw new Error('accept_incomplete must be boolean');
        if (this.mode === 'mock') {
            window.AgentMock[approve ? 'approveTask' : 'rejectTask'](id);
            return window.AgentMock.getTask(id);
        }
        if (typeof previewId !== 'string' || !previewId) throw new Error('Missing approval preview_id; refresh task status');
        return this.request(this.taskPath(id) + (approve ? '/approve' : '/reject'), 'POST', {preview_id: previewId, ...(approve && acceptIncomplete === true ? {accept_incomplete:true} : {})});
    },
    async getReport(id) {
        if (this.mode === 'mock') return window.AgentMock.getReport(id);
        return this.request(this.taskPath(id) + '/report');
    }
};
