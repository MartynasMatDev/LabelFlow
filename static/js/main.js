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