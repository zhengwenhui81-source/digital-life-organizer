/* Real transport awaits the agreed HTTP contract. No fallback to mock. */
window.AgentAPI = {
    mode: 'mock',
    setMode(mode) {
        if (!['mock', 'real'].includes(mode)) throw new Error('Unknown API mode');
        this.mode = mode;
    },
    async call(method, ...args) {
        if (this.mode === 'real') throw new Error('Real Agent API is not available. Waiting for Developer A’s agreed HTTP contract.');
        return window.AgentMock[method](...args);
    },
    createTask(input) { return this.call('createTask', input); },
    getTask(id) { return this.call('getTask', id); },
    approveTask(id) { return this.call('approveTask', id); },
    rejectTask(id) { return this.call('rejectTask', id); },
    getReport(id) { return this.call('getReport', id); }
};
