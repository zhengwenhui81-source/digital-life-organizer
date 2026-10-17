/* Agreed Agent HTTP transport. Mock is always an explicit choice. */
window.AgentAPI = {
    mode: 'mock',
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
            try { data = JSON.parse(raw); }
            catch (_) {
                const error = new Error('HTTP ' + response.status + ': Agent backend returned invalid JSON');
                error.status = response.status;
                throw error;
            }
            if (!response.ok) {
                const detail = data?.detail ?? data?.error ?? data?.message;
                const error = new Error('HTTP ' + response.status + ': ' + (typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : response.statusText || 'Agent request failed'));
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
    async createTask(userGoal, workspace, scenario = 'happy') {
        if (!userGoal?.trim() || !workspace?.trim()) throw new Error('Workspace and goal are required');
        if (this.mode === 'mock') return window.AgentMock.createTask({user_goal: userGoal, workspace, scenario});
        return this.request('/api/agent/tasks', 'POST', {user_goal: userGoal, workspace}, 202);
    },
    async getTask(id) {
        if (this.mode === 'mock') return window.AgentMock.getTask(id);
        return this.request(this.taskPath(id));
    },
    async approveTask(id, previewId) { return this.decideTask(id, previewId, true); },
    async rejectTask(id, previewId) { return this.decideTask(id, previewId, false); },
    async decideTask(id, previewId, approve) {
        if (this.mode === 'mock') {
            window.AgentMock[approve ? 'approveTask' : 'rejectTask'](id);
            return window.AgentMock.getTask(id);
        }
        if (typeof previewId !== 'string' || !previewId) throw new Error('Missing approval preview_id; refresh task status');
        return this.request(this.taskPath(id) + (approve ? '/approve' : '/reject'), 'POST', {preview_id: previewId});
    },
    async getReport(id) {
        if (this.mode === 'mock') return window.AgentMock.getReport(id);
        return this.request(this.taskPath(id) + '/report');
    }
};
