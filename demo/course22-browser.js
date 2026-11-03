// Reused from frontend/index.html Directory Browser. No new picker or API.
        // ── Directory Browser ─────────────────────────────────────────────
        var browserCurrentPath = '';
        var browserTargetInput = 'scanPath';
        var browserRequestId = 0;

        function openBrowser(targetInput) {
            browserTargetInput = targetInput || 'scanPath';
            browserCurrentPath = '';
            document.getElementById('browserModal').classList.add('active');
            var cur = document.getElementById(browserTargetInput).value.trim();
            fetchDirectory(cur || '~');
        }

        function closeBrowser() {
            browserRequestId++;
            document.getElementById('browserModal').classList.remove('active');
        }

        async function fetchDirectory(path) {
            var requestId = ++browserRequestId;
            path = String(path || '').trim();
            browserCurrentPath = '';
            document.getElementById('browserSelect').disabled = true;
            document.getElementById('browserJumpPath').value = path;
            document.getElementById('browserCurPath').textContent = '';
            document.getElementById('browserBreadcrumb').textContent = '';
            document.getElementById('dirList').innerHTML = '<div class="dir-empty">Loading…</div>';
            try {
                if (!path) throw new Error('Enter a drive root or directory path.');
                var r = await fetch('/api/browse?path=' + encodeURIComponent(path));
                if (requestId !== browserRequestId) return;
                if (!r.ok) {
                    var detail = '';
                    try { var error = await r.json(); detail = typeof error.detail === 'string' ? error.detail : ''; } catch (_) {}
                    throw new Error('Cannot open directory (HTTP ' + r.status + '). ' + detail);
                }
                var data = await r.json();
                if (requestId !== browserRequestId) return;
                if (typeof data.path !== 'string' || !data.path || !Array.isArray(data.entries)) throw new Error('Invalid directory response. Please try again.');
                renderBreadcrumb(data.path, data.parent);
                renderDirList(data.entries, data.parent);
                browserCurrentPath = data.path;
                document.getElementById('browserCurPath').textContent = data.path;
                document.getElementById('browserJumpPath').value = data.path;
                document.getElementById('browserSelect').disabled = false;
            } catch (e) {
                if (requestId !== browserRequestId) return;
                document.getElementById('dirList').innerHTML = '<div class="dir-empty"></div>';
                document.getElementById('dirList').firstElementChild.textContent = e instanceof TypeError ? 'Directory browser unavailable. Check the server connection.' : e.message;
            }
        }

        // Serialize a value as a JS literal that is safe inside a double-quoted HTML attribute.
        // JSON.stringify wraps strings in " which would prematurely close onclick="...".
        // Replacing " with &quot; lets the HTML parser decode it back to " before JS executes.
        function jsq(val) { return escapeHtml(JSON.stringify(val)); }

        function renderBreadcrumb(path, parent) {
            var normalized = path.replace(/\\/g, '/');
            var drive = /^[A-Za-z]:\//.test(normalized);
            var unc = normalized.startsWith('//');
            var parts = normalized.split('/').filter(Boolean);
            var html = '';
            if (parent !== null) html += '<button onclick="fetchDirectory(' + jsq(parent) + ')">..</button><span class="bc-sep">/</span>';
            var accumulated = drive ? '' : unc ? '//' : normalized.startsWith('/') ? '/' : '';
            parts.forEach(function(part, i) {
                accumulated += part + (i < parts.length - 1 || (drive && i === 0) ? '/' : '');
                if (i < parts.length - 1) html += '<button onclick="fetchDirectory(' + jsq(accumulated) + ')">' + escapeHtml(part) + '</button><span class="bc-sep">/</span>';
                else html += '<span>' + escapeHtml(part) + '</span>';
            });
            document.getElementById('browserBreadcrumb').innerHTML = html;
        }

        function renderDirList(entries, parent) {
            if (!entries.length) {
                document.getElementById('dirList').innerHTML = '<div class="dir-empty">No subdirectories</div>';
                return;
            }
            var html = entries.map(function(e) {
                return '<div class="dir-item" onclick="selectEntry(' + jsq(e.path) + ')">'
                    + '<span class="dir-item-icon">📁</span>'
                    + '<span class="dir-item-name">' + escapeHtml(e.name) + '</span>'
                    + '<button class="dir-nav-btn" onclick="event.stopPropagation(); fetchDirectory(' + jsq(e.path) + ')" title="Browse into folder">›</button>'
                    + '</div>';
            }).join('');
            document.getElementById('dirList').innerHTML = html;
        }

        function selectEntry(path) {
            browserCurrentPath = path;
            document.getElementById(browserTargetInput).value = path;
            document.getElementById(browserTargetInput).dispatchEvent(new Event('input', {bubbles:true}));
            closeBrowser();
        }

        function selectDirectory() {
            if (browserCurrentPath) {
                document.getElementById(browserTargetInput).value = browserCurrentPath;
                document.getElementById(browserTargetInput).dispatchEvent(new Event('input', {bubbles:true}));
            }
            closeBrowser();
        }
