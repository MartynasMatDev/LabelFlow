/* LabelFlow — image preview lightbox */
(function () {
  function drawBoxes(img, svg, boxes) {
    svg.innerHTML = '';
    if (!boxes || !boxes.length) return;
    var iW = img.offsetWidth, iH = img.offsetHeight;
    boxes.forEach(function (b) {
      var color = (b.label && b.label.color) ? b.label.color : '#6366f1';
      var px = b.x / 100 * iW, py = b.y / 100 * iH;
      var pw = b.width / 100 * iW, ph = b.height / 100 * iH;

      var rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
      rect.setAttribute('x', px); rect.setAttribute('y', py);
      rect.setAttribute('width', pw); rect.setAttribute('height', ph);
      rect.setAttribute('fill', 'none');
      rect.setAttribute('stroke', color); rect.setAttribute('stroke-width', '2');
      rect.setAttribute('rx', '2');
      svg.appendChild(rect);

      if (b.label && b.label.name) {
        var text = b.label.name, badgeH = 18, badgeW = text.length * 7 + 14;
        var badgeY = Math.max(0, py - badgeH);
        var bg = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        bg.setAttribute('x', px); bg.setAttribute('y', badgeY);
        bg.setAttribute('width', badgeW); bg.setAttribute('height', badgeH);
        bg.setAttribute('rx', '4'); bg.setAttribute('fill', color);
        svg.appendChild(bg);
        var t = document.createElementNS('http://www.w3.org/2000/svg', 'text');
        t.setAttribute('x', px + 7); t.setAttribute('y', badgeY + 9);
        t.setAttribute('dominant-baseline', 'middle');
        t.setAttribute('fill', '#fff');
        t.setAttribute('font-family', 'DM Mono, monospace');
        t.setAttribute('font-size', '11'); t.setAttribute('font-weight', '600');
        t.textContent = text;
        svg.appendChild(t);
      }
    });
  }

  var _boxes = [];
  var modal   = document.getElementById('preview-modal');
  var img     = document.getElementById('preview-modal-img');
  var svg     = document.getElementById('preview-modal-svg');
  var nameEl  = document.getElementById('preview-modal-name');
  var linkEl  = document.getElementById('preview-annotate-link');
  var badgeEl = document.getElementById('preview-box-badge');

  window.openPreviewFromBtn = function (btn) {
    var url         = btn.getAttribute('data-preview-url');
    var name        = btn.getAttribute('data-preview-name');
    var boxesJson   = btn.getAttribute('data-preview-boxes');
    var annotateUrl = btn.getAttribute('data-preview-annotate');
    var boxes = [];
    try { boxes = JSON.parse(boxesJson || '[]'); } catch(e) { boxes = []; }
    openPreview(url, name, boxes, annotateUrl);
  };

  window.openPreview = function (url, name, boxes, annotateUrl) {
    _boxes = boxes || [];
    img.src = ''; img.alt = name;
    nameEl.textContent = name;
    linkEl.href = annotateUrl;
    svg.innerHTML = '';
    badgeEl.textContent = _boxes.length
      ? _boxes.length + ' box' + (_boxes.length !== 1 ? 'es' : '')
      : 'No annotations';
    modal.classList.add('open');
    document.body.style.overflow = 'hidden';
    img.onload = function () { drawBoxes(img, svg, _boxes); };
    img.src = url;
  };

  window.closePreview = function () {
    modal.classList.remove('open');
    document.body.style.overflow = '';
    img.src = ''; svg.innerHTML = '';
  };

  window.addEventListener('resize', function () {
    if (modal.classList.contains('open') && img.complete && img.naturalWidth)
      drawBoxes(img, svg, _boxes);
  });

  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape' && modal.classList.contains('open')) closePreview();
  });
})();
