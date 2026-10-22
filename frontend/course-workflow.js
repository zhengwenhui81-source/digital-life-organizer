(function(root){
  'use strict';
  const CATEGORIES = ['待确认','课程资料','实验与作业','报告与总结','参考资料','其他'];
  const TARGET_COUNT = 22;
  const state = { files: [], nextId: 1, selectedReportId: null, search: '', filter: 'all' };
  const byId = id => document.getElementById(id);
  const escapeHtml = value => String(value == null ? '' : value).replace(/[&<>"']/g, ch => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[ch]));
  const getExtension = name => {
    const base = String(name || '').split(/[\\/]/).pop();
    const index = base.lastIndexOf('.');
    return index > 0 ? base.slice(index + 1).toLowerCase() : 'file';
  };
  const formatBytes = value => {
    const bytes = Number(value);
    if (!Number.isFinite(bytes) || bytes < 0) return '未知大小';
    if (bytes < 1024) return bytes + ' B';
    const units = ['KB','MB','GB','TB'];
    let size = bytes / 1024, i = 0;
    while (size >= 1024 && i < units.length - 1) { size /= 1024; i++; }
    return size.toFixed(size >= 10 ? 0 : 1) + ' ' + units[i];
  };
  const formatDate = value => {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime()) || !value) return '修改时间未知';
    return date.toLocaleString('zh-CN', {year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hour12:false});
  };
  function buildDirectoryModel(files) {
    const groups = new Map();
    (Array.isArray(files) ? files : []).forEach(file => {
      const category = CATEGORIES.includes(file.category) ? file.category : '待确认';
      if (!groups.has(category)) groups.set(category, []);
      groups.get(category).push(file);
    });
    return CATEGORIES.filter(category => groups.has(category)).map(category => ({category, files: groups.get(category).slice()}));
  }
  function getProgress(files, selectedReportId) {
    const list = Array.isArray(files) ? files : [];
    const categorized = list.filter(file => CATEGORIES.includes(file.category) && file.category !== '待确认').length;
    const pending = list.length - categorized;
    const candidates = list.filter(file => file.isReportCandidate);
    const selected = candidates.find(file => file.id === selectedReportId) || null;
    return {imported:list.length, targetCount:TARGET_COUNT, categorized, pending, reportCandidates:candidates.length, selectedReport:selected ? selected.id : null, treeFiles:list.length};
  }
  function iconFor(name) {
    const ext = getExtension(name);
    if (['pdf'].includes(ext)) return 'PDF';
    if (['doc','docx','rtf','txt','md'].includes(ext)) return ext.toUpperCase();
    if (['xls','xlsx','csv'].includes(ext)) return 'XLS';
    if (['ppt','pptx'].includes(ext)) return 'PPT';
    if (['jpg','jpeg','png','gif','webp','bmp'].includes(ext)) return 'IMG';
    if (['zip','7z','rar','tar','gz'].includes(ext)) return 'ZIP';
    return ext === 'file' ? 'FILE' : ext.slice(0,4).toUpperCase();
  }
  function visibleFiles() {
    const query = state.search.trim().toLocaleLowerCase();
    return state.files.filter(entry => {
      const matchesQuery = !query || (entry.file.name + ' ' + entry.path).toLocaleLowerCase().includes(query);
      const matchesFilter = state.filter === 'all'
        || (state.filter === 'pending' && entry.category === '待确认')
        || (state.filter === 'categorized' && entry.category !== '待确认')
        || (state.filter === 'reports' && entry.isReportCandidate);
      return matchesQuery && matchesFilter;
    });
  }
  function showToast(message) {
    const toast = byId('toast');
    toast.textContent = message;
    toast.hidden = false;
    if (state.toastTimer) clearTimeout(state.toastTimer);
    state.toastTimer = setTimeout(() => { toast.hidden = true; }, 3600);
  }
  function renderMetrics(progress) {
    byId('metricImported').innerHTML = progress.imported + ' <small>/ ' + progress.targetCount + '</small>';
    byId('metricPending').textContent = progress.pending;
    byId('metricReports').textContent = progress.reportCandidates;
    byId('metricTree').textContent = progress.treeFiles;
    byId('inventoryCount').textContent = progress.imported + ' 份材料';
    byId('treeSummary').textContent = progress.treeFiles + ' 个文件 · ' + buildDirectoryModel(state.files).length + ' 个分类';
    byId('clearAll').disabled = state.files.length === 0;
    byId('exportManifest').disabled = state.files.length === 0;
    byId('importMessage').textContent = state.files.length ? ('当前会话已导入 ' + state.files.length + ' 份材料；未上传到服务器。') : '尚未导入文件。';
    byId('workflowStatus').textContent = !progress.imported ? '等待导入材料' : (progress.pending ? '有材料待确认' : (progress.selectedReport ? '核心步骤已确认' : '等待报告定版'));
  }
  function renderWorkflow(progress) {
    const steps = [
      {key:'import',done:progress.imported>0,current:progress.imported===0,label:progress.imported>0?'已导入':'待开始'},
      {key:'classify',done:progress.imported>0 && progress.pending===0,current:progress.imported>0 && progress.pending>0,label:progress.imported===0?'待开始':(progress.pending===0?'已确认':'待确认 '+progress.pending+' 份')},
      {key:'report',done:Boolean(progress.selectedReport),current:progress.reportCandidates>0 && !progress.selectedReport,label:progress.selectedReport?'已定版':(progress.reportCandidates?'待选择':'待标记候选')},
      {key:'preview',done:progress.imported>0,current:progress.imported===0,label:progress.imported>0?'已生成预览':'待开始'}
    ];
    steps.forEach(step => {
      const node = byId('workflowTrack').querySelector('[data-step="' + step.key + '"]');
      node.classList.toggle('is-done', step.done);
      node.classList.toggle('is-current', step.current);
      node.querySelector('.step-state').textContent = step.label;
    });
  }
  function renderFileList() {
    const entries = visibleFiles();
    byId('visibleCount').textContent = '显示 ' + entries.length + ' 份';
    if (!entries.length) {
      byId('fileList').innerHTML = state.files.length
        ? '<div class="empty-state compact"><strong>没有匹配的材料</strong><p>尝试修改搜索词或筛选条件。</p></div>'
        : '<div class="empty-state"><span class="empty-icon" aria-hidden="true">▤</span><strong>清单还是空的</strong><p>导入实际材料后，这里会显示文件信息、分类选择和报告候选操作。</p></div>';
      return;
    }
    byId('fileList').innerHTML = entries.map(entry => {
      const id = escapeHtml(entry.id);
      const name = escapeHtml(entry.file.name);
      const path = escapeHtml(entry.path);
      const options = CATEGORIES.map(category => '<option value="' + escapeHtml(category) + '"' + (entry.category === category ? ' selected' : '') + '>' + escapeHtml(category) + '</option>').join('');
      return '<article class="file-row" data-file-id="' + id + '"><div class="file-main"><span class="file-type-icon">' + escapeHtml(iconFor(entry.file.name)) + '</span><div class="file-info"><strong class="file-name">' + name + '</strong><span class="file-path">' + path + '</span><div class="file-meta"><span>' + formatBytes(entry.file.size) + '</span><span>' + formatDate(entry.file.lastModified) + '</span></div></div></div><div class="file-controls"><select class="category-select" data-action="category" aria-label="为 ' + name + ' 选择分类">' + options + '</select><div class="mini-actions"><button type="button" class="mini-btn ' + (entry.isReportCandidate ? 'is-marked' : '') + '" data-action="report" aria-pressed="' + String(entry.isReportCandidate) + '">' + (entry.isReportCandidate ? '✓ 报告候选' : '设为报告候选') + '</button><button type="button" class="mini-btn remove-btn" data-action="remove" aria-label="移除 ' + name + '">移除</button></div></div></article>';
    }).join('');
  }
  function renderReports(progress) {
    const candidates = state.files.filter(entry => entry.isReportCandidate).slice().sort((a,b) => (b.file.lastModified || 0) - (a.file.lastModified || 0));
    if (!candidates.length) {
      byId('reportCandidates').innerHTML = '<div class="empty-state compact"><strong>还没有报告候选</strong><p>在材料清单中点击“设为报告候选”。</p></div>';
    } else {
      byId('reportCandidates').innerHTML = candidates.map(entry => {
        const selected = progress.selectedReport === entry.id;
        return '<article class="candidate-card ' + (selected ? 'is-selected' : '') + '"><div class="candidate-title"><span aria-hidden="true">▤</span><strong>' + escapeHtml(entry.file.name) + '</strong></div><p class="candidate-date">修改时间：' + formatDate(entry.file.lastModified) + ' · ' + formatBytes(entry.file.size) + '</p><div class="candidate-footer"><span class="candidate-date">' + (selected ? '当前选定版本' : '尚未定版') + '</span><button type="button" class="mini-btn ' + (selected ? 'is-marked' : '') + '" data-action="select-report" data-file-id="' + escapeHtml(entry.id) + '">' + (selected ? '已选定' : '选择此版本') + '</button></div></article>';
      }).join('');
    }
    const selected = candidates.find(entry => entry.id === progress.selectedReport);
    byId('selectedReport').hidden = !selected;
    byId('selectedReport').innerHTML = selected ? '<strong>✓ 已手动选择当前报告版本</strong><p>' + escapeHtml(selected.file.name) + '</p><p>修改时间：' + formatDate(selected.file.lastModified) + '</p>' : '';
  }
  function renderDirectory() {
    const model = buildDirectoryModel(state.files);
    if (!state.files.length) {
      byId('directoryTree').innerHTML = '<div class="empty-tree"><span aria-hidden="true">⌁</span><p>导入材料并选择分类后，将在这里显示拟整理的目录树。</p></div>';
      return;
    }
    const rootName = escapeHtml(byId('outputRoot').value.trim() || '课程材料整理结果');
    const groups = model.map(group => {
      const items = group.files.map(entry => '<div class="tree-file">' + escapeHtml(entry.file.name) + '</div>').join('');
      return '<details class="tree-group" open><summary>' + escapeHtml(group.category) + '<span>' + group.files.length + '</span></summary><div class="tree-files">' + items + '</div></details>';
    }).join('');
    byId('directoryTree').innerHTML = '<div class="tree-root">▣ ' + rootName + ' <span style="color:#7086a2;font-weight:400">(拟建目录)</span></div>' + groups;
  }
  function render() {
    const progress = getProgress(state.files, state.selectedReportId);
    renderMetrics(progress);
    renderWorkflow(progress);
    renderFileList();
    renderReports(progress);
    renderDirectory();
  }
  function addFiles(fileList) {
    const incoming = Array.from(fileList || []);
    if (!incoming.length) return;
    let added = 0, skipped = 0;
    incoming.forEach(file => {
      const path = file.webkitRelativePath || file.name;
      const duplicate = state.files.some(entry => entry.path === path && entry.file.size === file.size && entry.file.lastModified === file.lastModified);
      if (duplicate) { skipped++; return; }
      state.files.push({id:'course-file-' + state.nextId++, file, path, category:'待确认', isReportCandidate:false});
      added++;
    });
    render();
    const message = '新增 ' + added + ' 份材料' + (skipped ? '，跳过 ' + skipped + ' 个重复选择' : '') + '。';
    showToast(message);
  }
  function removeFile(id) {
    state.files = state.files.filter(entry => entry.id !== id);
    if (state.selectedReportId === id) state.selectedReportId = null;
    render();
  }
  function exportManifest() {
    const progress = getProgress(state.files, state.selectedReportId);
    const payload = {
      manifest_type:'course_material_workflow_local_preview',
      notice:'仅为浏览器文件元数据与用户手动选择；不代表已解析正文、自动分类或执行磁盘操作。',
      output_root_label:byId('outputRoot').value.trim() || '课程材料整理结果',
      expected_material_count:TARGET_COUNT,
      imported_count:progress.imported,
      selected_report:state.files.find(entry => entry.id === progress.selectedReport) ? state.files.find(entry => entry.id === progress.selectedReport).file.name : null,
      files:state.files.map(entry => ({
        filename:entry.file.name, relative_path:entry.path, extension:getExtension(entry.file.name),
        size_bytes:entry.file.size, last_modified:entry.file.lastModified ? new Date(entry.file.lastModified).toISOString() : null,
        category:entry.category, report_candidate:entry.isReportCandidate, selected_report_version:entry.id === progress.selectedReport
      }))
    };
    const blob = new Blob([JSON.stringify(payload,null,2)], {type:'application/json;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'course-material-manifest.json';
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    showToast('已导出清单 JSON；文件正文未包含在导出内容中。');
  }
  function init() {
    byId('chooseFiles').addEventListener('click', () => byId('fileInput').click());
    byId('chooseFolder').addEventListener('click', () => byId('folderInput').click());
    byId('dropZone').addEventListener('click', event => {
      if (event.target.closest('button')) return;
      byId('fileInput').click();
    });
    byId('dropZone').addEventListener('keydown', event => {
      if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); byId('fileInput').click(); }
    });
    byId('fileInput').addEventListener('change', event => { addFiles(event.target.files); event.target.value = ''; });
    byId('folderInput').addEventListener('change', event => { addFiles(event.target.files); event.target.value = ''; });
    ['dragenter','dragover'].forEach(type => byId('dropZone').addEventListener(type, event => { event.preventDefault(); byId('dropZone').classList.add('dragover'); }));
    ['dragleave','drop'].forEach(type => byId('dropZone').addEventListener(type, event => { event.preventDefault(); byId('dropZone').classList.remove('dragover'); }));
    byId('dropZone').addEventListener('drop', event => addFiles(event.dataTransfer && event.dataTransfer.files));
    byId('searchInput').addEventListener('input', event => { state.search = event.target.value; renderFileList(); });
    byId('filterSelect').addEventListener('change', event => { state.filter = event.target.value; renderFileList(); });
    byId('outputRoot').addEventListener('input', renderDirectory);
    byId('clearAll').addEventListener('click', () => {
      if (!state.files.length) return;
      state.files = []; state.selectedReportId = null; state.search = ''; state.filter = 'all';
      byId('searchInput').value = ''; byId('filterSelect').value = 'all';
      render(); showToast('已清空当前浏览器会话的材料清单。');
    });
    byId('exportManifest').addEventListener('click', exportManifest);
    byId('fileList').addEventListener('change', event => {
      const select = event.target.closest('[data-action="category"]');
      if (!select) return;
      const row = select.closest('[data-file-id]');
      const entry = state.files.find(file => file.id === row.dataset.fileId);
      if (!entry) return;
      entry.category = CATEGORIES.includes(select.value) ? select.value : '待确认';
      render();
    });
    byId('fileList').addEventListener('click', event => {
      const button = event.target.closest('[data-action]');
      if (!button) return;
      const row = button.closest('[data-file-id]');
      const id = row && row.dataset.fileId;
      const entry = state.files.find(file => file.id === id);
      if (!entry) return;
      if (button.dataset.action === 'report') {
        entry.isReportCandidate = !entry.isReportCandidate;
        if (!entry.isReportCandidate && state.selectedReportId === id) state.selectedReportId = null;
        render();
      } else if (button.dataset.action === 'remove') {
        removeFile(id);
      }
    });
    byId('reportCandidates').addEventListener('click', event => {
      const button = event.target.closest('[data-action="select-report"]');
      if (!button) return;
      const entry = state.files.find(file => file.id === button.dataset.fileId && file.isReportCandidate);
      if (!entry) return;
      state.selectedReportId = entry.id;
      render();
      showToast('已记录你的报告版本选择；请再核对文件内容。');
    });
    render();
  }
  const api = {CATEGORIES, TARGET_COUNT, escapeHtml, getExtension, formatBytes, buildDirectoryModel, getProgress};
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  if (root && root.document) {
    if (root.document.readyState === 'loading') root.document.addEventListener('DOMContentLoaded', init, {once:true});
    else init();
  }
})(typeof window === 'undefined' ? globalThis : window);