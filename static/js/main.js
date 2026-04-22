/* LabelFlow – main.js */

/* ── Toast notifications ─────────────────────────────────── */
window.showToast = function (message, type, duration) {
  type     = type     || 'success';       // 'success' | 'error' | 'info'
  duration = duration || 2600;            // ms

  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    container.className = 'toast-container';
    document.body.appendChild(container);
  }

  const icons = { success: '\u2713', error: '\u2715', info: 'i' };
  const toast = document.createElement('div');
  toast.className = 'toast toast-' + type;
  toast.innerHTML =
    '<span class="toast-icon">' + (icons[type] || '\u2713') + '</span>' +
    '<span class="toast-msg"></span>';
  toast.querySelector('.toast-msg').textContent = message;
  container.appendChild(toast);

  // Trigger entry animation
  requestAnimationFrame(function () { toast.classList.add('visible'); });

  setTimeout(function () {
    toast.classList.remove('visible');
    setTimeout(function () { toast.remove(); }, 250);
  }, duration);
};

/* ── Copy-to-clipboard helper (works over plain HTTP) ──── */
window.copyTextToClipboard = function (text) {
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text);
  }
  return new Promise(function (resolve, reject) {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.left = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    ta.setSelectionRange(0, ta.value.length);
    try {
      const ok = document.execCommand('copy');
      document.body.removeChild(ta);
      ok ? resolve() : reject(new Error('execCommand copy failed'));
    } catch (err) {
      document.body.removeChild(ta);
      reject(err);
    }
  });
};

/* ── Theme ───────────────────────────────────────────────── */
(function () {
  const saved = localStorage.getItem('lf-theme') || 'dark';
  document.documentElement.setAttribute('data-theme', saved);
})();

window.toggleTheme = function () {
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const next    = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('lf-theme', next);

  // Update button label/icon in sidebar
  const btn   = document.getElementById('theme-toggle-btn');
  const icon  = document.getElementById('theme-icon');
  const label = document.getElementById('theme-label');
  if (icon)  icon.textContent  = next === 'dark' ? '☀️' : '🌙';
  if (label) label.textContent = next === 'dark' ? 'Light mode' : 'Dark mode';
};

document.addEventListener('DOMContentLoaded', () => {

  // ── Sync theme button state on load ──────────────────────
  const current = document.documentElement.getAttribute('data-theme') || 'dark';
  const icon    = document.getElementById('theme-icon');
  const label   = document.getElementById('theme-label');
  if (icon)  icon.textContent  = current === 'dark' ? '☀️' : '🌙';
  if (label) label.textContent = current === 'dark' ? 'Light mode' : 'Dark mode';

  // ── Modal helpers ──────────────────────────────────────
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

  // ── Dropdowns ───────────────────────────────────────────
  window.toggleDropdown = function (id) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle('open');
  };
  document.addEventListener('click', function (e) {
    document.querySelectorAll('.dropdown.open').forEach(function (dd) {
      if (!dd.contains(e.target)) dd.classList.remove('open');
    });
  });

  // ── Tabs ────────────────────────────────────────────────
  window.switchTab = function (tabId) {
    const container = document.querySelector('[data-tabs]') || document;
    container.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.toggle('active', btn.dataset.tab === tabId);
    });
    container.querySelectorAll('.tab-pane').forEach(pane => {
      pane.classList.toggle('active', pane.id === 'tab-' + tabId);
    });
  };

  // ── View toggle (grid / list) ────────────────────────────
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

  // ── CSRF cookie helper ───────────────────────────────────
  window.getCookie = function (name) {
    const m = document.cookie.match('(^|;)\\s*' + name + '=([^;]*)');
    return m ? decodeURIComponent(m[2]) : null;
  };

  // ── Auto-dismiss alerts ──────────────────────────────────
  document.querySelectorAll('.alert').forEach(el => {
    setTimeout(() => {
      el.style.transition = 'opacity .4s';
      el.style.opacity    = '0';
      setTimeout(() => el.remove(), 400);
    }, 4000);
  });

});

/* ── Batch selection helpers ─────────────────────────────── */
window.getChecked = function () {
  return [...document.querySelectorAll('.img-checkbox:checked')].map(c => c.value);
};

window.onCheckChange = function () {
  const checked = getChecked();
  const bar     = document.getElementById('batch-bar');
  const num     = document.getElementById('batch-count-num');
  if (!bar) return;
  num.textContent = checked.length;
  bar.classList.toggle('visible', checked.length > 0);
  document.querySelectorAll('.image-grid-card').forEach(card => {
    const cb = card.querySelector('.img-checkbox');
    if (cb) card.classList.toggle('selected', cb.checked);
  });
};

window.selectAll = function (on) {
  document.querySelectorAll('.img-checkbox').forEach(cb => { cb.checked = on; });
  onCheckChange();
};

window.openTagModal = function (action) {
  const ids = getChecked();
  if (!ids.length) return;
  const container = document.getElementById('tag-image-inputs');
  container.innerHTML = ids.map(id => `<input type="hidden" name="image_ids" value="${id}">`).join('');
  document.getElementById('tag-action').value   = action;
  document.getElementById('tag-modal-title').textContent =
    action === 'remove' ? 'Remove tag' : 'Add tag';
  document.getElementById('tag-submit-btn').textContent =
    action === 'remove' ? 'Remove' : 'Add';
  document.getElementById('tag-form').classList.toggle('hide-new-tag', action === 'remove');
  document.getElementById('tag-modal').classList.add('open');
};

window.closeTagModal   = () => document.getElementById('tag-modal').classList.remove('open');

window.openDeleteModal = function () {
  const ids = getChecked();
  if (!ids.length) return;
  const container = document.getElementById('delete-image-inputs');
  container.innerHTML = ids.map(id => `<input type="hidden" name="image_ids" value="${id}">`).join('');
  document.getElementById('delete-count-label').textContent = `${ids.length} image(s)`;
  document.getElementById('delete-modal').classList.add('open');
};

window.closeDeleteModal = () => document.getElementById('delete-modal').classList.remove('open');

  let editIdx = -1;
  let editTempDeg = 0;
  let editTempCrop = null;
  let editTempResize = 0;
  let editTempFormat = '';
  let editTempQuality = 92;
  let editObjectURL = null;
  let editLoadedImg = null;
  let cropDragState = null;
  const unsavedBuf = new Map();

/* ── Upload page IIFE (runs only when drop-zone exists) ──── */
(function () {
  if (!document.getElementById('drop-zone')) return;   // not on upload page → skip

  const ALLOWED = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif']);
  const MAX_B   = 20 * 1024 * 1024;

  let pending    = [];
  let preSkipped = 0;
  let running    = false;

  const rotations = new Map();
  const crops = new Map();
  const resizes = new Map();
  const formats = new Map();
  const qualities = new Map();

  const editOverlay  = document.getElementById('edit-modal-overlay');
  const editCanvas   = document.getElementById('edit-preview-canvas');
  const editCropBox  = document.getElementById('edit-crop-box');
  const editCtx      = editCanvas.getContext('2d');

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
  const editFilename    = document.getElementById('edit-modal-filename');
  const editNavPrev     = document.getElementById('edit-nav-prev');
  const editNavNext     = document.getElementById('edit-nav-next');
  const editNavCtr      = document.getElementById('edit-nav-counter');
  const editFormatSel   = document.getElementById('edit-format-select');
  const editQualSlider  = document.getElementById('edit-quality-slider');
  const editQualLabel   = document.getElementById('edit-quality-label');
  const editOutputBadge = document.getElementById('edit-output-badge');
  const qualityWrap     = document.getElementById('quality-wrap');


  function ext(n)  { return n.slice(n.lastIndexOf('.')).toLowerCase(); }
  function fmt(b)  {
    if (b < 1024)    return b + ' B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
    return (b / 1048576).toFixed(1) + ' MB';
  }
  function esc(s)  { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function csrf()  { const m = document.cookie.match('(^|;)\\s*csrftoken=([^;]*)'); return m ? decodeURIComponent(m[2]) : ''; }
  const fileIds = new WeakMap();
  let nextFileId = 1;

  function fileKey(f) {
    if (!fileIds.has(f)) fileIds.set(f, `file_${nextFileId++}`);
    return fileIds.get(f);
  }
  function buildThumb(file) {
    const d = document.createElement('div');
    d.className = 'queue-thumb';
    if (file.type.startsWith('image/')) {
      const img = document.createElement('img');
      img.src = URL.createObjectURL(file);
      const deg = rotations.get(fileKey(file)) || 0;
      if (deg) {
        img.style.transform = `rotate(${deg}deg)`;
        const badge = document.createElement('span');
        badge.className   = 'rot-badge';
        badge.textContent = deg + '°';
        d.appendChild(badge);
      }
      d.appendChild(img);
    } else { d.textContent = '⬡'; }
    return d;
  }

  function refreshThumb(file) {
    const k   = fileKey(file);
    const row = queueList.querySelector(`[data-fkey="${CSS.escape(fileKey(file))}"]`);    if (!row) return;
    const old = row.querySelector('.queue-thumb');
    if (old) {
      old.querySelectorAll('img').forEach(img => {
        if (img.src && img.src.startsWith('blob:')) URL.revokeObjectURL(img.src);
      });
      old.replaceWith(buildThumb(file));
    }
  }

  function buildQueue(files) {
    pending    = [];
    preSkipped = 0;
    rotations.clear();
    crops.clear();
    resizes.clear();
    formats.clear();
    qualities.clear();
    unsavedBuf.clear();
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

      const k   = fileKey(f);
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

  const actions = document.createElement('div');
  actions.className = 'queue-item-actions';

  if (valid) {
    const editBtn = document.createElement('button');
    editBtn.type      = 'button';
    editBtn.className = 'qi-btn edit-btn';
    editBtn.title     = 'Rotate / edit';
    editBtn.textContent = '✎';
    editBtn.onclick = () => {
      const idx = pending.indexOf(f);
      if (idx !== -1) window.openEditModal(idx);
  };
  actions.appendChild(editBtn);
  }

  const rm = document.createElement('button');
  rm.type        = 'button';
  rm.className   = 'qi-btn rm-btn';
  rm.textContent = '✕';
  rm.title       = 'Remove';
  rm.onclick = () => {
    pending = pending.filter(p => fileKey(p) !== k);
    rotations.delete(k);
    row.remove();
    queueCount.textContent = pending.length;
    btnUpload.disabled = pending.length === 0;
    if (pending.length === 0) queueWrap.classList.remove('visible');
  };
  actions.appendChild(rm);

  row.appendChild(buildThumb(f)); row.appendChild(nm);
  row.appendChild(sz);            row.appendChild(st);
  row.appendChild(actions);
  queueList.appendChild(row);
    });

    queueWrap.classList.add('visible');
    queueCount.textContent = pending.length;

    if (statsCard) {
      statsCard.style.display = '';
      document.getElementById('stat-found').textContent   = files.length;
      document.getElementById('stat-valid').textContent   = pending.length;
      document.getElementById('stat-preskip').textContent = preSkipped;
      document.getElementById('stat-size').textContent    = fmt(bytes);
    }

    btnUpload.disabled = pending.length === 0;
  }

  window.clearQueue = function () {
    pending = []; preSkipped = 0;
    rotations.clear();
    crops.clear();
    resizes.clear();
    formats.clear();
    qualities.clear();
    queueList.innerHTML = '';
    queueWrap.classList.remove('visible');
    progSec.classList.remove('visible');
    errorLog.classList.remove('visible');
    errorList.innerHTML = '';
    summary.classList.remove('visible');
    btnUpload.disabled  = true;
    btnView.style.display = 'none';
    if (statsCard) statsCard.style.display = 'none';
    inputFiles.value  = '';
    inputFolder.value = '';
  };

  inputFiles.addEventListener('change', () => {
    if (inputFiles.files.length) buildQueue([...inputFiles.files]);
  });

  inputFolder.addEventListener('change', () => {
    const flat = [...inputFolder.files].filter(
      f => f.webkitRelativePath.split('/').length === 2
    );
    if (flat.length) buildQueue(flat);
  });

  dropZone.addEventListener('dragover',  e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
  dropZone.addEventListener('dragleave', ()  => dropZone.classList.remove('drag-over'));
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

  window.startUpload = async function () {
    if (running || !pending.length) return;
    const pid = document.getElementById('project-select').value;
    if (!pid) { alert('Please select a project first.'); return; }

    running = true;
    btnUpload.disabled  = true;
    errorList.innerHTML = '';
    errorLog.classList.remove('visible');
    summary.classList.remove('visible');

    const total = pending.length;
    let ok = 0, fail = 0, idx = 0;

    progSec.classList.add('visible');
    progFill.style.width  = '0%';
    progLbl.textContent   = 'Uploading…';
    progCount.textContent = `0 / ${total}`;

    const uploadUrl = btnUpload.dataset.uploadUrl;

    async function uploadOne(file) {
      const k   = fileKey(file);
      const row = queueList.querySelector(`[data-fkey="${CSS.escape(k)}"]`);      const st  = row?.querySelector('.queue-status');
      if (row) row.classList.add('uploading');
      if (st)  st.textContent = '↑';

      const uploadFile = await getRotatedFile(file);
      const fd = new FormData();
      fd.append('project',    pid);
      fd.append('image_file', uploadFile, uploadFile.name);

      try {
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

    // ── FIX: Use base URL from hidden element ──
    const baseUrl = document.getElementById('project-detail-base')?.dataset.url;
    if (baseUrl) {
        btnView.href = baseUrl.replace('0', pid);
        btnView.style.display = '';
    }
  };

  function addError(name, reason) {
    errorLog.classList.add('visible');
    const r = document.createElement('div');
    r.className = 'error-log-row';
    r.innerHTML = `<span class="en">${esc(name)}</span><span class="er">${esc(reason)}</span>`;
    errorList.appendChild(r);
  }

  function syncModalUI() {
    if (editIdx < 0 || !pending[editIdx]) return;

    const file = pending[editIdx];
    editFilename.textContent = file.name;
    editNavCtr.textContent   = `${editIdx + 1} / ${pending.length}`;
    editNavPrev.disabled     = editIdx === 0;
    editNavNext.disabled     = editIdx === pending.length - 1;

    if (!editLoadedImg) return;

    const w = editCanvas.width;
    const h = editCanvas.height;
    if (!w || !h) return;

    const c = editTempCrop || fullCrop();

    editCropBox.hidden = false;
    editCropBox.style.left   = `${c.x * w}px`;
    editCropBox.style.top    = `${c.y * h}px`;
    editCropBox.style.width  = `${c.w * w}px`;
    editCropBox.style.height = `${c.h * h}px`;
  }
  function clamp(v, min, max) {
    return Math.max(min, Math.min(max, v));
  }

  function cloneCrop(c) {
    return c ? { x: c.x, y: c.y, w: c.w, h: c.h } : null;
  }

  function fullCrop() {
    return { x: 0, y: 0, w: 1, h: 1 };
  }

  function cropIsFull(c) {
    return !!c && c.x <= 0.001 && c.y <= 0.001 && c.x + c.w >= 0.999 && c.y + c.h >= 0.999;
  }

  function normalizeCrop(c) {
    let x = clamp(c.x, 0, 1);
    let y = clamp(c.y, 0, 1);
    let w = clamp(c.w, 0.02, 1 - x);
    let h = clamp(c.h, 0.02, 1 - y);
    return { x, y, w, h };
  }

  function transformCrop(rect, delta) {
    if (!rect) return fullCrop();
    const step = (((delta % 360) + 360) % 360);
    if (step === 0) return cloneCrop(rect);

    const pts = [
      [rect.x, rect.y],
      [rect.x + rect.w, rect.y],
      [rect.x, rect.y + rect.h],
      [rect.x + rect.w, rect.y + rect.h]
    ];

    const map = step === 90
        ? ([x, y]) => [1 - y, x]
        : step === 180
            ? ([x, y]) => [1 - x, 1 - y]
            : ([x, y]) => [y, 1 - x]; // 270

    const mapped = pts.map(map);
    const xs = mapped.map(p => p[0]);
    const ys = mapped.map(p => p[1]);

    return normalizeCrop({
      x: Math.min(...xs),
      y: Math.min(...ys),
      w: Math.max(...xs) - Math.min(...xs),
      h: Math.max(...ys) - Math.min(...ys)
    });
  }

  function renderEditPreview() {

    if (!editLoadedImg || editIdx < 0) return;

    const rot = ((editTempDeg % 360) + 360) % 360;
    const baseW = (rot === 90 || rot === 270) ? editLoadedImg.naturalHeight : editLoadedImg.naturalWidth;
    const baseH = (rot === 90 || rot === 270) ? editLoadedImg.naturalWidth  : editLoadedImg.naturalHeight;

    const maxW = 520;
    const maxH = 360;
    const scale = Math.min(maxW / baseW, maxH / baseH, 1);

    const w = Math.max(1, Math.round(baseW * scale));
    const h = Math.max(1, Math.round(baseH * scale));

    editCanvas.width = w;
    editCanvas.height = h;
    editCanvas.style.width = `${w}px`;
    editCanvas.style.height = `${h}px`;

    editCtx.setTransform(1, 0, 0, 1, 0, 0);
    editCtx.clearRect(0, 0, w, h);

    const drawW = editLoadedImg.naturalWidth * scale;
    const drawH = editLoadedImg.naturalHeight * scale;

    editCtx.save();
    editCtx.translate(w / 2, h / 2);
    editCtx.rotate(rot * Math.PI / 180);
    editCtx.drawImage(
      editLoadedImg,
      -editLoadedImg.naturalWidth * scale / 2,
      -editLoadedImg.naturalHeight * scale / 2,
      editLoadedImg.naturalWidth * scale,
      editLoadedImg.naturalHeight * scale
    );
    editCtx.restore();

    syncModalUI();
  }

  function startCropDrag(e) {
    if (!editLoadedImg) return;

    const box = editCanvas.getBoundingClientRect();
    cropDragState = {
      mode: e.target.dataset.handle ? 'resize' : 'move',
      handle: e.target.dataset.handle || null,
      startX: e.clientX,
      startY: e.clientY,
      start: cloneCrop(editTempCrop || fullCrop()),
      boxW: box.width,
      boxH: box.height
    };

    e.preventDefault();
    e.stopPropagation();
    window.addEventListener('pointermove', onCropDrag);
    window.addEventListener('pointerup', stopCropDrag, { once: true });
  }

  function onCropDrag(e) {
    if (!cropDragState) return;

    const dx = (e.clientX - cropDragState.startX) / cropDragState.boxW;
    const dy = (e.clientY - cropDragState.startY) / cropDragState.boxH;
    const minW = Math.max(24 / cropDragState.boxW, 0.02);
    const minH = Math.max(24 / cropDragState.boxH, 0.02);

    let c = cloneCrop(cropDragState.start);

    if (cropDragState.mode === 'move') {
      c.x = clamp(cropDragState.start.x + dx, 0, 1 - cropDragState.start.w);
      c.y = clamp(cropDragState.start.y + dy, 0, 1 - cropDragState.start.h);
    } else {
      let x = cropDragState.start.x;
      let y = cropDragState.start.y;
      let w = cropDragState.start.w;
      let h = cropDragState.start.h;

      if (cropDragState.handle.includes('e')) w = clamp(cropDragState.start.w + dx, minW, 1 - x);
      if (cropDragState.handle.includes('s')) h = clamp(cropDragState.start.h + dy, minH, 1 - y);

      if (cropDragState.handle.includes('w')) {
        x = clamp(cropDragState.start.x + dx, 0, cropDragState.start.x + cropDragState.start.w - minW);
        w = clamp(cropDragState.start.x + cropDragState.start.w - x, minW, 1 - x);
      }

      if (cropDragState.handle.includes('n')) {
        y = clamp(cropDragState.start.y + dy, 0, cropDragState.start.y + cropDragState.start.h - minH);
        h = clamp(cropDragState.start.y + cropDragState.start.h - y, minH, 1 - y);
      }

      c = { x, y, w, h };
    }

    editTempCrop = normalizeCrop(c);
    syncModalUI();
  }

  function stopCropDrag() {
    window.removeEventListener('pointermove', onCropDrag);
    cropDragState = null;
  }

  editCropBox.addEventListener('pointerdown', startCropDrag);

  window.openEditModal = function (idx) {
    if (idx < 0 || idx >= pending.length) return;

    const fk = fileKey(pending[idx]);
    const cached = unsavedBuf.get(fk);

    editIdx = idx;
    editTempDeg     = cached ? cached.deg    : (rotations.get(fk) || 0);
    editTempCrop    = cached ? cloneCrop(cached.crop) : (crops.get(fk) ? cloneCrop(crops.get(fk)) : fullCrop());
    editTempResize  = cached ? (cached.resize  || 0)   : (resizes.get(fk)  || 0);
    editTempFormat  = cached ? (cached.format  || '')   : (formats.get(fk)  || '');
    editTempQuality = cached ? (cached.quality || 92)   : (qualities.get(fk) || 92);

    if (editObjectURL) {
      URL.revokeObjectURL(editObjectURL);
      editObjectURL = null;
    }

    editLoadedImg = null;
    editCropBox.hidden = true;

    const url = URL.createObjectURL(pending[idx]);
    editObjectURL = url;

    const img = new Image();
    img.onload = () => {
      editLoadedImg = img;
      editOverlay.classList.add('open');
      renderEditPreview();
      syncConversionUI();
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      alert('Could not load image.');
    };
    img.src = url;
  };

  window.editNavigate = function (dir) {
    if (editIdx < 0) return;

    const next = editIdx + dir;
    if (next < 0 || next >= pending.length) return;

    unsavedBuf.set(fileKey(pending[editIdx]), {
      deg: editTempDeg, crop: cloneCrop(editTempCrop),
      resize: editTempResize, format: editTempFormat, quality: editTempQuality,
    });

    editIdx = next;
    const fk = fileKey(pending[editIdx]);
    const cached = unsavedBuf.get(fk);

    editTempDeg     = cached ? cached.deg    : (rotations.get(fk) || 0);
    editTempCrop    = cached ? cloneCrop(cached.crop) : (crops.get(fk) ? cloneCrop(crops.get(fk)) : fullCrop());
    editTempResize  = cached ? (cached.resize  || 0)   : (resizes.get(fk)  || 0);
    editTempFormat  = cached ? (cached.format  || '')   : (formats.get(fk)  || '');
    editTempQuality = cached ? (cached.quality || 92)   : (qualities.get(fk) || 92);

    if (editObjectURL) {
      URL.revokeObjectURL(editObjectURL);
      editObjectURL = null;
    }

    editLoadedImg = null;
    editCropBox.hidden = true;

    const url = URL.createObjectURL(pending[editIdx]);
    editObjectURL = url;

    const img = new Image();
    img.onload = () => {
      editLoadedImg = img;
      renderEditPreview();
      syncConversionUI();
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      alert('Could not load image.');
    };
    img.src = url;
  };

  window.applyResize = function (maxDim) {
    editTempResize = parseInt(maxDim) || 0;
    syncConversionUI();
  };

  window.applyFormat = function (fmt) {
    editTempFormat = fmt;
    syncConversionUI();
  };

  window.applyQuality = function (q) {
    editTempQuality = parseInt(q);
    syncConversionUI();
  };

  function syncConversionUI() {
    document.querySelectorAll('.resize-btn').forEach(btn => {
      btn.classList.toggle('active', parseInt(btn.dataset.maxdim) === editTempResize);
    });

    if (editFormatSel) editFormatSel.value = editTempFormat;
    if (editQualSlider) editQualSlider.value = editTempQuality;
    if (editQualLabel)  editQualLabel.textContent = editTempQuality + '%';

    const needsQuality = editTempFormat === 'jpeg' || editTempFormat === 'webp' ||
      (editTempFormat === '' && editIdx >= 0 && !['image/png'].includes(pending[editIdx]?.type));
    if (qualityWrap) qualityWrap.style.display = needsQuality ? 'flex' : 'none';

    updateOutputBadge();
  }

  function updateOutputBadge() {
    if (!editOutputBadge || !editLoadedImg || editIdx < 0) return;

    const rot = ((editTempDeg % 360) + 360) % 360;
    let baseW = (rot === 90 || rot === 270) ? editLoadedImg.naturalHeight : editLoadedImg.naturalWidth;
    let baseH = (rot === 90 || rot === 270) ? editLoadedImg.naturalWidth  : editLoadedImg.naturalHeight;

    const c = editTempCrop;
    if (c && !cropIsFull(c)) {
      baseW = Math.max(1, Math.round(c.w * baseW));
      baseH = Math.max(1, Math.round(c.h * baseH));
    }

    let outW = baseW, outH = baseH;
    if (editTempResize > 0 && (baseW > editTempResize || baseH > editTempResize)) {
      const scale = editTempResize / Math.max(baseW, baseH);
      outW = Math.max(1, Math.round(baseW * scale));
      outH = Math.max(1, Math.round(baseH * scale));
    }

    const file = pending[editIdx];
    const autoFmt = ['image/png', 'image/webp'].includes(file?.type) ? file.type.split('/')[1] : 'jpeg';
    const outFmt  = editTempFormat || autoFmt;
    const showQ   = outFmt === 'jpeg' || outFmt === 'webp';
    const changed = !!(editTempResize || editTempFormat);

    editOutputBadge.textContent =
      `${outW} × ${outH} px  ${outFmt.toUpperCase()}${showQ ? '  ' + editTempQuality + '%' : ''}`;
    editOutputBadge.style.display = '';
    editOutputBadge.classList.toggle('changed', changed);
  }

  window.applyRotation = function (delta) {
    editTempCrop = transformCrop(editTempCrop || fullCrop(), delta);
    editTempDeg = (((editTempDeg + delta) % 360) + 360) % 360;
    renderEditPreview();
    updateOutputBadge();
  };

  window.resetRotation = function () {
    if (!editTempDeg) return;
    editTempCrop = transformCrop(editTempCrop || fullCrop(), -editTempDeg);
    editTempDeg = 0;
    renderEditPreview();
    updateOutputBadge();
  };

  window.saveRotation = function () {
    if (editIdx < 0 || editIdx >= pending.length) return;

    const k = fileKey(pending[editIdx]);

    if (editTempDeg === 0) rotations.delete(k);
    else rotations.set(k, editTempDeg);

    if (cropIsFull(editTempCrop)) crops.delete(k);
    else crops.set(k, cloneCrop(editTempCrop));

    if (editTempResize) resizes.set(k, editTempResize);
    else resizes.delete(k);

    if (editTempFormat) formats.set(k, editTempFormat);
    else formats.delete(k);

    qualities.set(k, editTempQuality);

    unsavedBuf.delete(k);
    refreshThumb(pending[editIdx]);
    closeOverlay();
  };

  window.closeEditModal = function () {
    closeOverlay();
  };

  function closeOverlay() {
    editOverlay.classList.remove('open');

    setTimeout(() => {
      if (editObjectURL) {
        URL.revokeObjectURL(editObjectURL);
        editObjectURL = null;
      }
      editLoadedImg = null;
      editCropBox.hidden = true;
      editCanvas.width = 1;
      editCanvas.height = 1;
      editCanvas.style.width = '';
      editCanvas.style.height = '';
      editCtx.clearRect(0, 0, 1, 1);
    }, 220);

    editIdx = -1;
    editTempDeg = 0;
    editTempCrop = null;
    editTempResize = 0;
    editTempFormat = '';
    editTempQuality = 92;
    cropDragState = null;
    unsavedBuf.clear();
  }

  document.addEventListener('keydown', e => {
    if (!editOverlay || !editOverlay.classList.contains('open')) return;

    if (e.key === 'Escape') { window.closeEditModal(); return; }
    if (e.key === 'Enter')  { window.saveRotation(); return; }
    if (e.key === 'ArrowLeft')  { window.editNavigate(-1); return; }
    if (e.key === 'ArrowRight') { window.editNavigate(1); return; }
    if (e.key === 'ArrowUp')    { e.preventDefault(); window.applyRotation(-90); return; }
    if (e.key === 'ArrowDown')  { e.preventDefault(); window.applyRotation(90); return; }
  });

  editOverlay.addEventListener('click', e => {
    if (e.target === editOverlay) window.closeEditModal();
  });

  function renderThumbUrl(file) {
    const fk = fileKey(file);
    const deg = rotations.get(fk) || 0;
    const crop = crops.get(fk);

    if (!deg && !crop) {
      return Promise.resolve(URL.createObjectURL(file));
    }

    return new Promise(resolve => {
      const img = new Image();
      const url = URL.createObjectURL(file);

      img.onload = () => {
        const rot = ((deg % 360) + 360) % 360;
        const baseW = (rot === 90 || rot === 270) ? img.height : img.width;
        const baseH = (rot === 90 || rot === 270) ? img.width : img.height;

        const src = document.createElement('canvas');
        src.width = baseW;
        src.height = baseH;

        const sctx = src.getContext('2d');
        sctx.translate(baseW / 2, baseH / 2);
        sctx.rotate(rot * Math.PI / 180);
        sctx.drawImage(img, -img.width / 2, -img.height / 2);

        let out = src;

        if (crop) {
          const x = Math.round(crop.x * baseW);
          const y = Math.round(crop.y * baseH);
          const w = Math.max(1, Math.round(crop.w * baseW));
          const h = Math.max(1, Math.round(crop.h * baseH));

          const max = 120;
          const scale = Math.min(max / w, max / h, 1);
          const dst = document.createElement('canvas');
          dst.width = Math.max(1, Math.round(w * scale));
          dst.height = Math.max(1, Math.round(h * scale));

          dst.getContext('2d').drawImage(src, x, y, w, h, 0, 0, dst.width, dst.height);
          out = dst;
        } else {
          const max = 120;
          const scale = Math.min(max / baseW, max / baseH, 1);
          if (scale < 1) {
            const dst = document.createElement('canvas');
            dst.width = Math.max(1, Math.round(baseW * scale));
            dst.height = Math.max(1, Math.round(baseH * scale));
            dst.getContext('2d').drawImage(src, 0, 0, dst.width, dst.height);
            out = dst;
          }
        }

        URL.revokeObjectURL(url);

        const mime = ['image/png', 'image/webp'].includes(file.type) ? file.type : 'image/jpeg';
        out.toBlob(blob => {
          resolve(blob ? URL.createObjectURL(blob) : URL.createObjectURL(file));
        }, mime, 0.92);
      };

      img.onerror = () => {
        URL.revokeObjectURL(url);
        resolve(URL.createObjectURL(file));
      };

      img.src = url;
    });
  }

  async function refreshThumb(file) {
    const k = fileKey(file);
    const row = queueList.querySelector(`[data-fkey="${CSS.escape(k)}"]`);
    if (!row) return;

    const img = row.querySelector('.queue-thumb img');
    if (!img) return;

    const oldSrc = img.src;
    const url = await renderThumbUrl(file);

    if (!img.isConnected) {
      URL.revokeObjectURL(url);
      return;
    }

    img.src = url;
    img.style.transform = '';
    const badge = row.querySelector('.rot-badge');
    const deg = rotations.get(k) || 0;
    const crop = crops.get(k);

    if (badge) {
      if (deg && crop) badge.textContent = `${deg}° + crop`;
      else if (deg) badge.textContent = `${deg}°`;
      else if (crop) badge.textContent = 'crop';
      else badge.remove();
    }

    if (oldSrc && oldSrc.startsWith('blob:')) URL.revokeObjectURL(oldSrc);
  }

  function getRotatedFile(file) {
    const fk     = fileKey(file);
    const deg    = rotations.get(fk)  || 0;
    const crop   = crops.get(fk)      || null;
    const resize = resizes.get(fk)    || 0;
    const fmt    = formats.get(fk)    || '';
    const quality = qualities.get(fk) || 92;

    if (deg === 0 && !crop && !resize && !fmt) return Promise.resolve(file);

    return new Promise(resolve => {
      const img = new Image();
      const url = URL.createObjectURL(file);

      img.onload = () => {
        const rot = ((deg % 360) + 360) % 360;
        const baseW = (rot === 90 || rot === 270) ? img.height : img.width;
        const baseH = (rot === 90 || rot === 270) ? img.width : img.height;

        const src = document.createElement('canvas');
        src.width = baseW;
        src.height = baseH;

        const sctx = src.getContext('2d');
        sctx.translate(baseW / 2, baseH / 2);
        sctx.rotate(rot * Math.PI / 180);
        sctx.drawImage(img, -img.width / 2, -img.height / 2);

        let out = src;

        if (crop) {
          const x = Math.round(crop.x * baseW);
          const y = Math.round(crop.y * baseH);
          const w = Math.max(1, Math.round(crop.w * baseW));
          const h = Math.max(1, Math.round(crop.h * baseH));

          const dst = document.createElement('canvas');
          dst.width = w;
          dst.height = h;
          dst.getContext('2d').drawImage(src, x, y, w, h, 0, 0, w, h);
          out = dst;
        }

        // Apply resize
        if (resize > 0 && (out.width > resize || out.height > resize)) {
          const scale = resize / Math.max(out.width, out.height);
          const rs = document.createElement('canvas');
          rs.width  = Math.max(1, Math.round(out.width  * scale));
          rs.height = Math.max(1, Math.round(out.height * scale));
          rs.getContext('2d').drawImage(out, 0, 0, rs.width, rs.height);
          out = rs;
        }

        URL.revokeObjectURL(url);

        const fmtMap  = { jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp' };
        const autoMime = ['image/png', 'image/webp'].includes(file.type) ? file.type : 'image/jpeg';
        const mime     = (fmt && fmtMap[fmt]) || autoMime;
        const q        = (mime === 'image/jpeg' || mime === 'image/webp') ? quality / 100 : undefined;

        const extMap = { 'image/jpeg': '.jpg', 'image/png': '.png', 'image/webp': '.webp' };
        const outName = (fmt && mime !== autoMime)
          ? file.name.replace(/\.[^.]+$/, extMap[mime] || '')
          : file.name;

        out.toBlob(blob => {
          resolve(blob ? new File([blob], outName, { type: mime, lastModified: file.lastModified }) : file);
        }, mime, q);
      };

      img.onerror = () => {
        URL.revokeObjectURL(url);
        resolve(file);
      };

      img.src = url;
    });
  };

})();

/* ── Project Metrics Charts ───────────────────────────── */
(function () {
  const container = document.getElementById('metrics-data');
  if (!container) return; // not on project page

  function parseList(str) {
    if (!str) return [];
    return str.split(',').map(s => s.trim()).filter(Boolean);
  }

  function parseNumbers(str) {
    return parseList(str).map(Number);
  }

  // ── Extract data from HTML ────────────────────────────
  const imagesLabels = parseList(container.dataset.imagesLabels);
  const imagesData   = parseNumbers(container.dataset.imagesValues);

  const boxesLabels  = parseList(container.dataset.boxesLabels);
  const boxesData    = parseNumbers(container.dataset.boxesValues);

  const annLabels    = parseList(container.dataset.annotationsLabels);
  const annData      = parseNumbers(container.dataset.annotationsValues);

  const timeLabels   = parseList(container.dataset.timelineLabels);
  const timeData     = parseNumbers(container.dataset.timelineValues);

  // ── Colors (match your theme) ─────────────────────────
  const colors = [
    'rgba(99,102,241,0.6)',
    'rgba(52,211,153,0.6)',
    'rgba(251,191,36,0.6)',
    'rgba(248,113,113,0.6)',
    'rgba(56,189,248,0.6)',
  ];

  // ── Polar chart creator ───────────────────────────────
  function createPolar(canvasId, labels, data, title) {
    const el = document.getElementById(canvasId);
    if (!el) return;

    new Chart(el, {
      type: 'polarArea',
      data: {
        labels: labels,
        datasets: [{
          data: data,
          backgroundColor: colors,
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,

        plugins: {
          legend: {
            position: 'top'
          },
          title: {
            display: true,
            text: title,
            color: getComputedStyle(document.documentElement)
              .getPropertyValue('--text-muted')
              .trim(),
            font: {
              size: 14,
              weight: '600'
            },
            padding: {
              top: 6,
              bottom: 10
            }
          }
        },

        scales: {
          r: {
            beginAtZero: true,
            ticks: {
              color: getComputedStyle(document.documentElement)
                .getPropertyValue('--text')
            },
            grid: {
              color: 'rgba(120,120,160,0.15)'
            },
            angleLines: {
              color: 'rgba(120,120,160,0.15)'
            },
            pointLabels: {
              color: getComputedStyle(document.documentElement)
                .getPropertyValue('--text')
            }
          }
        }
      }
    });
  }

  // ── Build charts ──────────────────────────────────────
  createPolar('chart-images-user', imagesLabels, imagesData, 'Images per User');
  createPolar('chart-boxes-user', boxesLabels, boxesData, 'Boxes per User');
  createPolar('chart-annotations-user', annLabels, annData, 'Completed per User');

  // ── Timeline (stepped line) ───────────────────────────
  const timelineCanvas = document.getElementById('chart-timeline');
  if (timelineCanvas) {
    new Chart(timelineCanvas, {
      type: 'line',
      data: {
        labels: timeLabels,
        datasets: [{
          label: 'Uploads',
          data: timeData,
          borderColor: 'rgba(99,102,241,1)',
          fill: false,
          stepped: true
        }]
      },
      options: {
        responsive: true,
        interaction: {
          intersect: false,
          axis: 'x'
        },
        plugins: {
          title: {
            display: true,
            text: 'Uploads Timeline',
            color: getComputedStyle(document.documentElement).getPropertyValue('--text-muted'),
            font: {
              size: 12,
              weight: '600'
            },
            padding: {
              bottom: 8
            }
          },
          legend: {
            labels: {
              color: getComputedStyle(document.documentElement).getPropertyValue('--text')
            }
          }
        },
        scales: {
          x: {
            ticks: {
              color: getComputedStyle(document.documentElement).getPropertyValue('--text')
            },
            grid: {
              display: true,
              color: 'rgba(120,120,160,0.15)',
              lineWidth: 1
            }
          },
          y: {
            beginAtZero: true,
            ticks: {
              precision: 0,
              color: getComputedStyle(document.documentElement).getPropertyValue('--text')
            },
            grid: {
              display: true,
              color: 'rgba(120,120,160,0.15)',
              lineWidth: 1
            }
          }
        }
      }
    });
  }
})();
