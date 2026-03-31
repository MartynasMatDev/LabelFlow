/* LabelFlow – main.js */

/* ── Theme management ──────────────────────────────────────
   Persists in localStorage as 'lf-theme' = 'light' | 'dark'
   Applied to <html data-theme="..."> before paint to avoid flash.
   The inline <script> in app_base.html applies it immediately;
   this block handles the toggle button clicks.
─────────────────────────────────────────────────────────── */
(function () {
  // Apply saved theme immediately (also done inline in <head> to avoid FOUC)
  const saved = localStorage.getItem('lf-theme') || 'light';
  document.documentElement.setAttribute('data-theme', saved);
})();

window.toggleTheme = function () {
  const current = document.documentElement.getAttribute('data-theme') || 'light';
  const next    = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('lf-theme', next);
  // Update toggle button label
  document.querySelectorAll('.theme-toggle-label').forEach(el => {
    el.textContent = next === 'dark' ? 'Light mode' : 'Dark mode';
  });
  document.querySelectorAll('.theme-toggle-icon').forEach(el => {
    el.textContent = next === 'dark' ? '☀' : '☾';
  });
};

document.addEventListener('DOMContentLoaded', () => {

  // Sync toggle labels to current theme on load
  const theme = document.documentElement.getAttribute('data-theme') || 'light';
  document.querySelectorAll('.theme-toggle-label').forEach(el => {
    el.textContent = theme === 'dark' ? 'Light mode' : 'Dark mode';
  });
  document.querySelectorAll('.theme-toggle-icon').forEach(el => {
    el.textContent = theme === 'dark' ? '☀' : '☾';
  });

  // ── Modal helpers ───────────────────────────────────────
  document.querySelectorAll('[data-open-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = document.getElementById(btn.dataset.openModal);
      if (modal) modal.classList.add('open');
    });
  });

  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-overlay');
      if (modal) modal.classList.remove('open');
    });
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape')
      document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
  });

  document.addEventListener('click', e => {
    if (e.target.classList.contains('modal-overlay'))
      e.target.classList.remove('open');
  });

  // ── Tabs ───────────────────────────────────────────────
  window.switchTab = function (tabId) {
    const container = document.querySelector('[data-tabs]') || document;
    container.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    container.querySelectorAll('.tab-pane').forEach(pane => {
      pane.classList.toggle('active', pane.id === 'tab-' + tabId);
    });
  };

  // ── View toggle (grid/list) ────────────────────────────
  window.setView = function (mode) {
    const grid = document.getElementById('image-grid-view');
    const list = document.getElementById('image-list-view');
    const gbtn = document.getElementById('btn-grid');
    const lbtn = document.getElementById('btn-list');
    if (!grid) return;
    if (mode === 'grid') {
      grid.style.display = ''; list.style.display = 'none';
      gbtn.classList.add('active'); lbtn.classList.remove('active');
    } else {
      grid.style.display = 'none'; list.style.display = 'block';
      lbtn.classList.add('active'); gbtn.classList.remove('active');
    }
    localStorage.setItem('lf-view', mode);
  };

  const savedView = localStorage.getItem('lf-view');
  if (savedView) setView(savedView);

  // ── CSRF cookie helper ──────────────────────────────────
  window.getCookie = function (name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '=([^;]*)');
    return m ? decodeURIComponent(m[2]) : null;
  };

  // ── Auto-dismiss alerts ─────────────────────────────────
  document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity .4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 4000);
  });

  // ── Drop-zone upload ────────────────────────────────────
  window.initDropZone = function (zoneId, inputId, previewId) {
    const zone  = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    if (!zone || !input) return;

    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', e => {
      e.preventDefault(); zone.classList.remove('dragover');
      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length) {
        const dataTransfer = new DataTransfer();
        Array.from(dt.files).forEach(f => dataTransfer.items.add(f));
        input.files = dataTransfer.files;
        handleFilePreview(input.files, previewId);
      }
    });
    input.addEventListener('change', () => handleFilePreview(input.files, previewId));
  };

  window.handleFilePreview = function (files, previewId) {
    const container  = document.getElementById(previewId);
    const previewWrap = document.getElementById('file-preview-wrap');
    const countEl    = document.getElementById('upload-file-count');
    const submitBtn  = document.getElementById('upload-submit');
    if (!container) return;

    container.querySelectorAll('img[data-object-url]').forEach(img => {
      URL.revokeObjectURL(img.getAttribute('data-object-url'));
    });

    if (!files || files.length === 0) {
      container.innerHTML = '';
      if (previewWrap) previewWrap.style.display = 'none';
      if (countEl) countEl.textContent = '';
      if (submitBtn) submitBtn.disabled = true;
      return;
    }

    container.innerHTML = '';
    if (previewWrap) previewWrap.style.display = '';
    if (countEl) countEl.textContent = `${files.length} file(s) selected`;
    if (submitBtn) submitBtn.disabled = false;

    Array.from(files).slice(0, 10).forEach(f => {
      const wrap = document.createElement('div');
      wrap.style.cssText = 'width:52px;height:52px;border-radius:6px;background:var(--surface2);border:1px solid var(--border);overflow:hidden;flex-shrink:0;display:inline-block;';
      if (f.type && f.type.startsWith('image/')) {
        const img = document.createElement('img');
        const objUrl = URL.createObjectURL(f);
        img.src = objUrl;
        img.setAttribute('data-object-url', objUrl);
        img.style.cssText = 'width:100%;height:100%;object-fit:cover;';
        wrap.appendChild(img);
      } else {
        wrap.innerHTML = '<span style="font-size:20px;display:flex;align-items:center;justify-content:center;height:100%">⬡</span>';
      }
      container.appendChild(wrap);
    });
  };

});

(function () {
  const ALLOWED = new Set(['.jpg','.jpeg','.png','.webp','.bmp','.gif']);
  const MAX_B   = 20 * 1024 * 1024;

  let pending      = [];
  let preSkipped   = 0;
  let running      = false;

  // DOM
  const dropZone    = document.getElementById('drop-zone');
  const inputFiles  = document.getElementById('input-files');
  const inputFolder = document.getElementById('input-folder');
  const queueWrap   = document.getElementById('queue-wrap');
  const queueList   = document.getElementById('queue-list');
  const queueCount  = document.getElementById('queue-count');
  const btnUpload   = document.getElementById('btn-upload');
  const btnView     = document.getElementById('btn-view');
  const progSec     = document.getElementById('progress-section');
  const progFill    = document.getElementById('progress-fill');
  const progLbl     = document.getElementById('progress-lbl');
  const progCount   = document.getElementById('progress-count');
  const errorLog    = document.getElementById('error-log');
  const errorList   = document.getElementById('error-list');
  const summary     = document.getElementById('upload-summary');
  const statsCard   = document.getElementById('stats-card');

  // ── Helpers ──────────────────────────────────────────────
  function ext(n)  { return n.slice(n.lastIndexOf('.')).toLowerCase(); }
  function fmt(b)  {
    if (b < 1024)    return b + ' B';
    if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
    return (b/1048576).toFixed(1) + ' MB';
  }
  function esc(s)  { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function csrf()  { const m = document.cookie.match('(^|;)\\s*csrftoken=([^;]*)'); return m ? decodeURIComponent(m[2]) : ''; }
  function key(f)  { return CSS.escape((f.name + f.size + f.lastModified).replace(/\W/g,'_')); }

  function thumb(file) {
    const d = document.createElement('div');
    d.className = 'queue-thumb';
    if (file.type.startsWith('image/')) {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      d.appendChild(img);
    } else { d.textContent = '⬡'; }
    return d;
  }

  // ── Build queue ───────────────────────────────────────────
  function buildQueue(files) {
    pending    = [];
    preSkipped = 0;
    queueList.innerHTML = '';
    errorLog.classList.remove('visible');
    errorList.innerHTML = '';
    summary.classList.remove('visible');
    progSec.classList.remove('visible');
    btnView.style.display = 'none';

    let bytes = 0;
    files.forEach(f => {
      const e     = ext(f.name);
      const valid = ALLOWED.has(e) && f.size <= MAX_B;
      if (valid) { pending.push(f); bytes += f.size; }
      else       { preSkipped++; }

      const k   = key(f);
      const row = document.createElement('div');
      row.className    = 'queue-item' + (valid ? '' : ' skipped');
      row.dataset.fkey = k;

      const st = document.createElement('span');
      st.className    = 'queue-status';
      st.dataset.fkey = k;
      st.textContent  = valid ? '○' : '⚠';
      st.title        = valid ? 'Queued' : (!ALLOWED.has(e) ? 'Invalid type' : '>20 MB');

      const nm = document.createElement('span');
      nm.className   = 'queue-name';
      nm.textContent = f.name;

      const sz = document.createElement('span');
      sz.className   = 'queue-size';
      sz.textContent = fmt(f.size);

      const rm = document.createElement('button');
      rm.type      = 'button';
      rm.textContent = '✕';
      rm.title     = 'Remove';
      rm.style.cssText = 'background:none;border:none;color:#fff;cursor:pointer;font-size:13px;padding:0 2px;flex-shrink:0;transition:color .12s;opacity:0.6;';
      rm.onmouseenter = () => { rm.style.color = 'var(--danger)'; rm.style.opacity = '1'; };
      rm.onmouseleave = () => { rm.style.color = '#fff'; rm.style.opacity = '0.6'; };
      rm.onclick = () => {
        pending = pending.filter(p => key(p) !== k);
        row.remove();
        queueCount.textContent = pending.length;
        btnUpload.disabled = pending.length === 0;
        if (pending.length === 0) queueWrap.classList.remove('visible');
      };

      row.appendChild(thumb(f)); row.appendChild(nm);
      row.appendChild(sz);       row.appendChild(st);
      row.appendChild(rm);
      queueList.appendChild(row);
    });

    queueWrap.classList.add('visible');
    queueCount.textContent = pending.length;

    statsCard.style.display = '';
    document.getElementById('stat-found').textContent   = files.length;
    document.getElementById('stat-valid').textContent   = pending.length;
    document.getElementById('stat-preskip').textContent = preSkipped;
    document.getElementById('stat-size').textContent    = fmt(bytes);

    btnUpload.disabled = pending.length === 0;
  }

  // ── Clear ─────────────────────────────────────────────────
  window.clearQueue = function () {
    pending = []; preSkipped = 0;
    queueList.innerHTML = '';
    queueWrap.classList.remove('visible');
    progSec.classList.remove('visible');
    errorLog.classList.remove('visible');
    errorList.innerHTML = '';
    summary.classList.remove('visible');
    btnUpload.disabled = true;
    btnView.style.display = 'none';
    statsCard.style.display = 'none';
    inputFiles.value = '';
    inputFolder.value = '';
  };

  // ── Inputs ────────────────────────────────────────────────
  inputFiles.addEventListener('change', () => {
    if (inputFiles.files.length) buildQueue([...inputFiles.files]);
  });

  inputFolder.addEventListener('change', () => {
    const flat = [...inputFolder.files].filter(
      f => f.webkitRelativePath.split('/').length === 2
    );
    if (flat.length) buildQueue(flat);
  });

  // ── Drag & drop ───────────────────────────────────────────
  dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', ()=> dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', async e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const collected = [];
    for (const item of [...e.dataTransfer.items]) {
      const entry = item.webkitGetAsEntry?.();
      if (!entry) continue;
      if (entry.isDirectory) {
        await new Promise(res => {
          entry.createReader().readEntries(entries => {
            const fe = entries.filter(en => en.isFile);
            let n = fe.length;
            if (!n) { res(); return; }
            fe.forEach(en => en.file(f => { collected.push(f); if (!--n) res(); }));
          });
        });
      } else if (entry.isFile) {
        await new Promise(res => entry.file(f => { collected.push(f); res(); }));
      }
    }
    if (collected.length) buildQueue(collected);
  });

  // ── Upload ────────────────────────────────────────────────
  window.startUpload = async function () {
    if (running || !pending.length) return;
    const pid = document.getElementById('project-select').value;
    if (!pid) { alert('Please select a project first.'); return; }

    running = true;
    btnUpload.disabled = true;
    errorList.innerHTML = '';
    errorLog.classList.remove('visible');
    summary.classList.remove('visible');

    const total = pending.length;
    let ok = 0, fail = 0, idx = 0;

    progSec.classList.add('visible');
    progFill.style.width  = '0%';
    progLbl.textContent   = 'Uploading…';
    progCount.textContent = `0 / ${total}`;

    async function uploadOne(file) {
      const k   = key(file);
      const row = queueList.querySelector(`[data-fkey="${k}"]`);
      const st  = row?.querySelector('.queue-status');
      if (row) row.classList.add('uploading');
      if (st)  st.textContent = '↑';

      const fd = new FormData();
      fd.append('project',    pid);
      fd.append('image_file', file, file.name);

      try {
        const uploadUrl = document.getElementById('btn-upload').dataset.uploadUrl;
        const r = await fetch(uploadUrl, {
          method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: fd,
        });
        const d = await r.json();
        if (d.success) {
          ok++;
          if (row) { row.classList.remove('uploading'); row.classList.add('done'); }
          if (st)  st.textContent = '✓';
        } else {
          fail++;
          if (row) { row.classList.remove('uploading'); row.classList.add('error'); }
          if (st)  st.textContent = '✕';
          addError(file.name, d.error || 'Server error');
        }
      } catch (_) {
        fail++;
        if (row) { row.classList.remove('uploading'); row.classList.add('error'); }
        if (st)  st.textContent = '✕';
        addError(file.name, 'Network error');
      }

      const done = ok + fail;
      progFill.style.width  = Math.round(done / total * 100) + '%';
      progCount.textContent = `${done} / ${total}`;
      progLbl.textContent   = done < total ? 'Uploading…' : 'Finishing…';
    }

    async function worker() {
      while (idx < pending.length) await uploadOne(pending[idx++]);
    }

    await Promise.all(Array.from({ length: Math.min(3, total) }, worker));

    running = false;
    progLbl.textContent = 'Done';

    document.getElementById('sum-total').textContent   = total;
    document.getElementById('sum-ok').textContent      = ok;
    document.getElementById('sum-skipped').textContent = preSkipped;
    document.getElementById('sum-failed').textContent  = fail;
    summary.classList.add('visible');

    btnView.href = `/app/images/project/${pid}/`;    btnView.style.display = '';
  };

  function addError(name, reason) {
    errorLog.classList.add('visible');
    const r = document.createElement('div');
    r.className = 'error-log-row';
    r.innerHTML = `<span class="en">${esc(name)}</span><span class="er">${esc(reason)}</span>`;
    errorList.appendChild(r);
  }
})();/* LabelFlow – main.js */

document.addEventListener('DOMContentLoaded', () => {

  // ── Modal helpers ───────────────────────────────
  document.querySelectorAll('[data-open-modal]').forEach(btn => {
    btn.addEventListener('click', () => {
      const modalId = btn.dataset.openModal;
      const modal = document.getElementById(modalId);
      if (modal) modal.classList.add('open');
    });
  });

  document.querySelectorAll('.modal-close').forEach(btn => {
    btn.addEventListener('click', () => {
      const modal = btn.closest('.modal-overlay');
      if (modal) modal.classList.remove('open');
    });
  });

  document.addEventListener('keydown', e => {
    if (e.key === 'Escape')
      document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
  });

  document.addEventListener('click', e => {
    if (e.target.classList.contains('modal-overlay'))
      e.target.classList.remove('open');
  });

  // ── Tabs ───────────────────────────────────────
  window.switchTab = function(tabId) {
    const container = document.querySelector('[data-tabs]') || document;
    container.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    container.querySelectorAll('.tab-pane').forEach(pane => {
      pane.classList.toggle('active', pane.id === 'tab-' + tabId);
    });
  };

  // ── View toggle (grid/list) ───────────────────
  window.setView = function(mode) {
    const grid = document.getElementById('image-grid-view');
    const list = document.getElementById('image-list-view');
    const gbtn = document.getElementById('btn-grid');
    const lbtn = document.getElementById('btn-list');
    if (!grid) return;
    if (mode === 'grid') {
      grid.style.display = ''; list.style.display = 'none';
      gbtn.classList.add('active'); lbtn.classList.remove('active');
    } else {
      grid.style.display = 'none'; list.style.display = 'block';
      lbtn.classList.add('active'); gbtn.classList.remove('active');
    }
    localStorage.setItem('lf-view', mode);
  };

  const savedView = localStorage.getItem('lf-view');
  if (savedView) setView(savedView);

  // ── CSRF cookie helper ─────────────────────────
  window.getCookie = function(name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '=([^;]*)');
    return m ? decodeURIComponent(m[2]) : null;
  };

  // ── Auto-dismiss alerts ────────────────────────
  document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity .4s';
      el.style.opacity = '0';
      setTimeout(() => el.remove(), 400);
    }, 4000);
  });

    // ── Drop-zone upload ──────────────────────────
  window.initDropZone = function(zoneId, inputId, previewId) {
    const zone  = document.getElementById(zoneId);
    const input = document.getElementById(inputId);
    if (!zone || !input) return;

    zone.addEventListener('click', () => input.click());
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', e => {
      e.preventDefault();
      zone.classList.remove('dragover');

      const dt = e.dataTransfer;
      if (dt && dt.files && dt.files.length) {
        // Copy files into a DataTransfer to set input.files reliably
        const dataTransfer = new DataTransfer();
        Array.from(dt.files).forEach(f => dataTransfer.items.add(f));
        input.files = dataTransfer.files;
        handleFilePreview(input.files, previewId);
      }
    });

    input.addEventListener('change', () => handleFilePreview(input.files, previewId));
  };

  window.handleFilePreview = function(files, previewId) {
    const container = document.getElementById(previewId);
    const previewWrap = document.getElementById('file-preview-wrap');
    const countEl = document.getElementById('upload-file-count');
    const submitBtn = document.getElementById('upload-submit');

    if (!container) return;

    // Clear old previews (and revoke object URLs)
    const imgs = container.querySelectorAll('img[data-object-url]');
    imgs.forEach(img => {
      const url = img.getAttribute('data-object-url');
      if (url) URL.revokeObjectURL(url);
    });

    // No files -> clear preview and disable submit
    if (!files || files.length === 0) {
      container.innerHTML = '';
      if (previewWrap) previewWrap.style.display = 'none';
      if (countEl) countEl.textContent = '';
      if (submitBtn) submitBtn.disabled = true;
      return;
    }

    // Show preview wrapper and update count + enable submit
    container.innerHTML = '';
    if (previewWrap) previewWrap.style.display = '';
    if (countEl) countEl.textContent = `${files.length} file(s) selected`;
    if (submitBtn) submitBtn.disabled = false;

    // Render up to 10 thumbnails
    Array.from(files).slice(0, 10).forEach(f => {
      const wrap = document.createElement('div');
      wrap.style.cssText =
        'width:56px;height:56px;border-radius:7px;background:var(--surface2);border:1px solid var(--border);overflow:hidden;flex-shrink:0;display:inline-block;';

      if (f.type && f.type.startsWith('image/')) {
        const img = document.createElement('img');
        const objUrl = URL.createObjectURL(f);
        img.src = objUrl;
        img.setAttribute('data-object-url', objUrl);
        img.style.cssText = 'width:100%;height:100%;object-fit:cover;';
        wrap.appendChild(img);
      } else {
        wrap.innerHTML =
          '<span style="font-size:22px;display:flex;align-items:center;justify-content:center;height:100%">⬡</span>';
      }

      container.appendChild(wrap);
    });
  };

});

(function () {
  const ALLOWED = new Set(['.jpg','.jpeg','.png','.webp','.bmp','.gif']);
  const MAX_B   = 20 * 1024 * 1024;

  let pending      = [];
  let preSkipped   = 0;
  let running      = false;

  // DOM
  const dropZone    = document.getElementById('drop-zone');
  const inputFiles  = document.getElementById('input-files');
  const inputFolder = document.getElementById('input-folder');
  const queueWrap   = document.getElementById('queue-wrap');
  const queueList   = document.getElementById('queue-list');
  const queueCount  = document.getElementById('queue-count');
  const btnUpload   = document.getElementById('btn-upload');
  const btnView     = document.getElementById('btn-view');
  const progSec     = document.getElementById('progress-section');
  const progFill    = document.getElementById('progress-fill');
  const progLbl     = document.getElementById('progress-lbl');
  const progCount   = document.getElementById('progress-count');
  const errorLog    = document.getElementById('error-log');
  const errorList   = document.getElementById('error-list');
  const summary     = document.getElementById('upload-summary');
  const statsCard   = document.getElementById('stats-card');

  // ── Helpers ──────────────────────────────────────────────
  function ext(n)  { return n.slice(n.lastIndexOf('.')).toLowerCase(); }
  function fmt(b)  {
    if (b < 1024)    return b + ' B';
    if (b < 1048576) return (b/1024).toFixed(1) + ' KB';
    return (b/1048576).toFixed(1) + ' MB';
  }
  function esc(s)  { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;'); }
  function csrf()  { const m = document.cookie.match('(^|;)\\s*csrftoken=([^;]*)'); return m ? decodeURIComponent(m[2]) : ''; }
  function key(f)  { return CSS.escape((f.name + f.size + f.lastModified).replace(/\W/g,'_')); }

  function thumb(file) {
    const d = document.createElement('div');
    d.className = 'queue-thumb';
    if (file.type.startsWith('image/')) {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      d.appendChild(img);
    } else { d.textContent = '⬡'; }
    return d;
  }

  // ── Build queue ───────────────────────────────────────────
  function buildQueue(files) {
    pending    = [];
    preSkipped = 0;
    queueList.innerHTML = '';
    errorLog.classList.remove('visible');
    errorList.innerHTML = '';
    summary.classList.remove('visible');
    progSec.classList.remove('visible');
    btnView.style.display = 'none';

    let bytes = 0;
    files.forEach(f => {
      const e     = ext(f.name);
      const valid = ALLOWED.has(e) && f.size <= MAX_B;
      if (valid) { pending.push(f); bytes += f.size; }
      else       { preSkipped++; }

      const k   = key(f);
      const row = document.createElement('div');
      row.className    = 'queue-item' + (valid ? '' : ' skipped');
      row.dataset.fkey = k;

      const st = document.createElement('span');
      st.className    = 'queue-status';
      st.dataset.fkey = k;
      st.textContent  = valid ? '○' : '⚠';
      st.title        = valid ? 'Queued' : (!ALLOWED.has(e) ? 'Invalid type' : '>20 MB');

      const nm = document.createElement('span');
      nm.className   = 'queue-name';
      nm.textContent = f.name;

      const sz = document.createElement('span');
      sz.className   = 'queue-size';
      sz.textContent = fmt(f.size);

      const rm = document.createElement('button');
      rm.type      = 'button';
      rm.textContent = '✕';
      rm.title     = 'Remove';
      rm.style.cssText = 'background:none;border:none;color:#fff;cursor:pointer;font-size:13px;padding:0 2px;flex-shrink:0;transition:color .12s;opacity:0.6;';
      rm.onmouseenter = () => { rm.style.color = 'var(--danger)'; rm.style.opacity = '1'; };
      rm.onmouseleave = () => { rm.style.color = '#fff'; rm.style.opacity = '0.6'; };
      rm.onclick = () => {
        pending = pending.filter(p => key(p) !== k);
        row.remove();
        queueCount.textContent = pending.length;
        btnUpload.disabled = pending.length === 0;
        if (pending.length === 0) queueWrap.classList.remove('visible');
      };

      row.appendChild(thumb(f)); row.appendChild(nm);
      row.appendChild(sz);       row.appendChild(st);
      row.appendChild(rm);
      queueList.appendChild(row);
    });

    queueWrap.classList.add('visible');
    queueCount.textContent = pending.length;

    statsCard.style.display = '';
    document.getElementById('stat-found').textContent   = files.length;
    document.getElementById('stat-valid').textContent   = pending.length;
    document.getElementById('stat-preskip').textContent = preSkipped;
    document.getElementById('stat-size').textContent    = fmt(bytes);

    btnUpload.disabled = pending.length === 0;
  }

  // ── Clear ─────────────────────────────────────────────────
  window.clearQueue = function () {
    pending = []; preSkipped = 0;
    queueList.innerHTML = '';
    queueWrap.classList.remove('visible');
    progSec.classList.remove('visible');
    errorLog.classList.remove('visible');
    errorList.innerHTML = '';
    summary.classList.remove('visible');
    btnUpload.disabled = true;
    btnView.style.display = 'none';
    statsCard.style.display = 'none';
    inputFiles.value = '';
    inputFolder.value = '';
  };

  // ── Inputs ────────────────────────────────────────────────
  inputFiles.addEventListener('change', () => {
    if (inputFiles.files.length) buildQueue([...inputFiles.files]);
  });

  inputFolder.addEventListener('change', () => {
    const flat = [...inputFolder.files].filter(
      f => f.webkitRelativePath.split('/').length === 2
    );
    if (flat.length) buildQueue(flat);
  });

  // ── Drag & drop ───────────────────────────────────────────
  dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', ()=> dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', async e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const collected = [];
    for (const item of [...e.dataTransfer.items]) {
      const entry = item.webkitGetAsEntry?.();
      if (!entry) continue;
      if (entry.isDirectory) {
        await new Promise(res => {
          entry.createReader().readEntries(entries => {
            const fe = entries.filter(en => en.isFile);
            let n = fe.length;
            if (!n) { res(); return; }
            fe.forEach(en => en.file(f => { collected.push(f); if (!--n) res(); }));
          });
        });
      } else if (entry.isFile) {
        await new Promise(res => entry.file(f => { collected.push(f); res(); }));
      }
    }
    if (collected.length) buildQueue(collected);
  });

  // ── Upload ────────────────────────────────────────────────
  window.startUpload = async function () {
    if (running || !pending.length) return;
    const pid = document.getElementById('project-select').value;
    if (!pid) { alert('Please select a project first.'); return; }

    running = true;
    btnUpload.disabled = true;
    errorList.innerHTML = '';
    errorLog.classList.remove('visible');
    summary.classList.remove('visible');

    const total = pending.length;
    let ok = 0, fail = 0, idx = 0;

    progSec.classList.add('visible');
    progFill.style.width  = '0%';
    progLbl.textContent   = 'Uploading…';
    progCount.textContent = `0 / ${total}`;

    async function uploadOne(file) {
      const k   = key(file);
      const row = queueList.querySelector(`[data-fkey="${k}"]`);
      const st  = row?.querySelector('.queue-status');
      if (row) row.classList.add('uploading');
      if (st)  st.textContent = '↑';

      const fd = new FormData();
      fd.append('project',    pid);
      fd.append('image_file', file, file.name);

      try {
        const uploadUrl = document.getElementById('btn-upload').dataset.uploadUrl;
        const r = await fetch(uploadUrl, {
          method: 'POST', headers: { 'X-CSRFToken': csrf() }, body: fd,
        });
        const d = await r.json();
        if (d.success) {
          ok++;
          if (row) { row.classList.remove('uploading'); row.classList.add('done'); }
          if (st)  st.textContent = '✓';
        } else {
          fail++;
          if (row) { row.classList.remove('uploading'); row.classList.add('error'); }
          if (st)  st.textContent = '✕';
          addError(file.name, d.error || 'Server error');
        }
      } catch (_) {
        fail++;
        if (row) { row.classList.remove('uploading'); row.classList.add('error'); }
        if (st)  st.textContent = '✕';
        addError(file.name, 'Network error');
      }

      const done = ok + fail;
      progFill.style.width  = Math.round(done / total * 100) + '%';
      progCount.textContent = `${done} / ${total}`;
      progLbl.textContent   = done < total ? 'Uploading…' : 'Finishing…';
    }

    async function worker() {
      while (idx < pending.length) await uploadOne(pending[idx++]);
    }

    await Promise.all(Array.from({ length: Math.min(3, total) }, worker));

    running = false;
    progLbl.textContent = 'Done';

    document.getElementById('sum-total').textContent   = total;
    document.getElementById('sum-ok').textContent      = ok;
    document.getElementById('sum-skipped').textContent = preSkipped;
    document.getElementById('sum-failed').textContent  = fail;
    summary.classList.add('visible');

    btnView.href         = `/app/images/project/${pid}/`;
    btnView.style.display = '';
  };

  function addError(name, reason) {
    errorLog.classList.add('visible');
    const r = document.createElement('div');
    r.className = 'error-log-row';
    r.innerHTML = `<span class="en">${esc(name)}</span><span class="er">${esc(reason)}</span>`;
    errorList.appendChild(r);
  }
})();
