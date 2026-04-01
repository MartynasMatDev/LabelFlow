/* LabelFlow – main.js */

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

/* ── Upload page IIFE (runs only when drop-zone exists) ──── */
(function () {
  if (!document.getElementById('drop-zone')) return;   // not on upload page → skip

  const ALLOWED = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.gif']);
  const MAX_B   = 20 * 1024 * 1024;

  let pending    = [];
  let preSkipped = 0;
  let running    = false;

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

  function ext(n)  { return n.slice(n.lastIndexOf('.')).toLowerCase(); }
  function fmt(b)  {
    if (b < 1024)    return b + ' B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
    return (b / 1048576).toFixed(1) + ' MB';
  }
  function esc(s)  { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function csrf()  { const m = document.cookie.match('(^|;)\\s*csrftoken=([^;]*)'); return m ? decodeURIComponent(m[2]) : ''; }
  function key(f)  { return CSS.escape((f.name + f.size + f.lastModified).replace(/\W/g, '_')); }

  function thumb(file) {
    const d   = document.createElement('div');
    d.className = 'queue-thumb';
    if (file.type.startsWith('image/')) {
      const img = document.createElement('img');
      img.src   = URL.createObjectURL(file);
      d.appendChild(img);
    } else { d.textContent = '⬡'; }
    return d;
  }

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
      rm.type        = 'button';
      rm.textContent = '✕';
      rm.title       = 'Remove';
      rm.style.cssText = 'background:none;border:none;color:var(--text-muted);cursor:pointer;font-size:13px;padding:0 2px;flex-shrink:0;transition:color .12s;';
      rm.onmouseenter = () => { rm.style.color = 'var(--danger)'; };
      rm.onmouseleave = () => { rm.style.color = 'var(--text-muted)'; };
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
      const k   = key(file);
      const row = queueList.querySelector(`[data-fkey="${k}"]`);
      const st  = row?.querySelector('.queue-status');
      if (row) row.classList.add('uploading');
      if (st)  st.textContent = '↑';

      const fd = new FormData();
      fd.append('project',    pid);
      fd.append('image_file', file, file.name);

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

          // ✅ ADD THIS BLOCK
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
          legend: {
            labels: { color: getComputedStyle(document.documentElement).getPropertyValue('--text') }
          }
        },
        scales: {
          x: {
            ticks: {
              color: getComputedStyle(document.documentElement).getPropertyValue('--text')
            },
            grid: {
              display: true,
              color: 'rgba(120,120,160,0.15)',   // ✅ stronger grid
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
              color: 'rgba(120,120,160,0.15)',   // ✅ visible horizontal lines
              lineWidth: 1
            }
          }
        }
      }
    });
  }

})();