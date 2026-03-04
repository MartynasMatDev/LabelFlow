/* LabelFlow – main.js */

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
      e.preventDefault(); zone.classList.remove('dragover');
      input.files = e.dataTransfer.files;
      handleFilePreview(input.files, previewId);
    });
    input.addEventListener('change', () => handleFilePreview(input.files, previewId));
  };

  window.handleFilePreview = function(files, previewId) {
    const container = document.getElementById(previewId);
    if (!container || !files.length) return;
    container.innerHTML = '';
    container.style.display = 'flex';
    const countEl = document.getElementById('upload-file-count');
    if (countEl) countEl.textContent = `${files.length} file(s) selected`;
    const submitBtn = document.getElementById('upload-submit');
    if (submitBtn) submitBtn.disabled = false;

    Array.from(files).slice(0, 10).forEach(f => {
      const wrap = document.createElement('div');
      wrap.style.cssText = 'width:56px;height:56px;border-radius:7px;background:var(--surface2);border:1px solid var(--border);overflow:hidden;flex-shrink:0;';
      if (f.type.startsWith('image/')) {
        const reader = new FileReader();
        reader.onload = ev => {
          const img = document.createElement('img');
          img.src = ev.target.result;
          img.style.cssText = 'width:100%;height:100%;object-fit:cover;';
          wrap.appendChild(img);
        };
        reader.readAsDataURL(f);
      } else {
        wrap.innerHTML = '<span style="font-size:22px;display:flex;align-items:center;justify-content:center;height:100%">⬡</span>';
      }
      container.appendChild(wrap);
    });
  };

});