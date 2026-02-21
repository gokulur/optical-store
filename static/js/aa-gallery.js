/**
 * AA Product Gallery — Universal, Amazon/Flipkart grade
 * Self-initializing. Works with any .aa-gal container.
 * Exposes window.__aaGal for external control.
 */
(function () {
  'use strict';

  function AaGallery() {
    var gal = document.getElementById('aaGal');
    if (!gal) return;

    var rail       = document.getElementById('aaGalRail');
    var stage      = document.getElementById('aaGalStage');
    var mainImg    = document.getElementById('aaGalMain');
    var zoomLens   = document.getElementById('aaZoomLens');
    var zoomPane   = document.getElementById('aaZoomPane');
    var zoomImg    = document.getElementById('aaZoomImg');
    var counter    = document.getElementById('aaGalCounter');
    var prevBtn    = document.getElementById('aaGalPrev');
    var nextBtn    = document.getElementById('aaGalNext');
    var fullBtn    = document.getElementById('aaGalFullscreen');
    var lb         = document.getElementById('aaGalLb');
    var lbImg      = document.getElementById('aaLbImg');
    var lbStrip    = document.getElementById('aaLbStrip');
    var lbCount    = document.getElementById('aaLbCount');

    if (!stage || !mainImg) return;

    var thumbs  = Array.from(rail.querySelectorAll('.aa-gal__thumb'));
    var srcs    = thumbs.map(function(t) { return t.dataset.src || ''; });
    var total   = srcs.length;
    var cur     = 0;
    var isMobile = window.innerWidth <= 1280;
    var tapZoomed = false;

    // ── Build lightbox strip ──
    srcs.forEach(function(src, i) {
      var dot = document.createElement('div');
      dot.className = 'aa-gal__lb-dot' + (i === 0 ? ' is-active' : '');
      var im = document.createElement('img');
      im.src = src; im.loading = 'lazy';
      dot.appendChild(im);
      dot.addEventListener('click', function() { lbGoTo(i); });
      lbStrip.appendChild(dot);
    });

    // ── Arrow / counter visibility ──
    if (total <= 1) {
      prevBtn && prevBtn.classList.add('is-hidden');
      nextBtn && nextBtn.classList.add('is-hidden');
      counter && counter.classList.add('is-single');
    }
    updateCounter();

    // ── Go to index ──
    function goTo(idx, force) {
      if (!force && idx === cur) return;
      if (idx < 0) idx = total - 1;
      if (idx >= total) idx = 0;

      var newSrc = srcs[idx];
      if (!newSrc) return;

      mainImg.classList.add('is-loading');

      var tmp = new Image();
      tmp.onload = function() {
        mainImg.src = newSrc;
        zoomImg.src = newSrc;
        mainImg.classList.remove('is-loading');
      };
      tmp.onerror = function() {
        mainImg.src = newSrc;
        zoomImg.src = newSrc;
        mainImg.classList.remove('is-loading');
      };
      tmp.src = newSrc;

      // Update thumbs
      thumbs.forEach(function(t, i) {
        t.classList.toggle('is-active', i === idx);
        t.setAttribute('aria-selected', i === idx ? 'true' : 'false');
        t.tabIndex = i === idx ? 0 : -1;
      });
      // Scroll active thumb into view
      if (thumbs[idx]) {
        thumbs[idx].scrollIntoView({ behavior: 'smooth', block: 'nearest', inline: 'center' });
      }

      cur = idx;
      updateCounter();

      // If lightbox open, sync it
      if (lb.classList.contains('is-open')) {
        lbGoTo(idx);
      }
    }

    function updateCounter() {
      if (counter) counter.textContent = (cur + 1) + ' / ' + total;
      var lbDots = Array.from(lbStrip.querySelectorAll('.aa-gal__lb-dot'));
      lbDots.forEach(function(d, i) { d.classList.toggle('is-active', i === cur); });
      if (lbCount) lbCount.textContent = (cur + 1) + ' / ' + total;
    }

    // ── Thumbnail clicks ──
    thumbs.forEach(function(t, i) {
      t.addEventListener('click', function() { goTo(i, true); });
      t.addEventListener('keydown', function(e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goTo(i, true); }
        if (e.key === 'ArrowDown' || e.key === 'ArrowRight') { e.preventDefault(); if (thumbs[i+1]) thumbs[i+1].focus(); }
        if (e.key === 'ArrowUp' || e.key === 'ArrowLeft') { e.preventDefault(); if (thumbs[i-1]) thumbs[i-1].focus(); }
      });
    });

    // ── Arrow buttons ──
    prevBtn && prevBtn.addEventListener('click', function(e) { e.stopPropagation(); goTo(cur - 1); });
    nextBtn && nextBtn.addEventListener('click', function(e) { e.stopPropagation(); goTo(cur + 1); });

    // ── Stage keyboard ──
    stage.addEventListener('keydown', function(e) {
      if (e.key === 'ArrowLeft')  { e.preventDefault(); goTo(cur - 1); }
      if (e.key === 'ArrowRight') { e.preventDefault(); goTo(cur + 1); }
      if (e.key === 'Enter' || e.key === 'f') { openLb(); }
      if (e.key === 'Escape') { stage.classList.remove('is-zooming'); }
    });

    // ── Fullscreen ──
    fullBtn && fullBtn.addEventListener('click', function(e) { e.stopPropagation(); openLb(); });

    // ── Zoom (desktop) ──
    var ZOOM_FACTOR = 2.8;
    var lensW = 120, lensH = 120;

    function setupZoom() {
      if (!mainImg) return;
      // Set pane dimensions based on stage size
      var sr = stage.getBoundingClientRect();
      zoomPane && (zoomPane.style.width = (sr.width * 0.85) + 'px');
      zoomPane && (zoomPane.style.height = (sr.height * 0.85) + 'px');
      if (zoomImg && mainImg.src) zoomImg.src = mainImg.src;
    }

    stage.addEventListener('mouseenter', function() {
      isMobile = window.innerWidth <= 1280;
      if (isMobile) return;
      if (!srcs[cur]) return;
      zoomImg.src = srcs[cur];
      stage.classList.add('is-zooming');
      setupZoom();
    });

    stage.addEventListener('mouseleave', function() {
      stage.classList.remove('is-zooming');
    });

    stage.addEventListener('mousemove', function(e) {
      isMobile = window.innerWidth <= 1280;
      if (isMobile || !stage.classList.contains('is-zooming')) return;

      var sr = stage.getBoundingClientRect();
      var mx = e.clientX - sr.left;
      var my = e.clientY - sr.top;

      // Clamp
      var lx = Math.max(lensW/2, Math.min(mx, sr.width - lensW/2));
      var ly = Math.max(lensH/2, Math.min(my, sr.height - lensH/2));

      // Position lens
      zoomLens.style.left   = (lx - lensW/2) + 'px';
      zoomLens.style.top    = (ly - lensH/2) + 'px';
      zoomLens.style.width  = lensW + 'px';
      zoomLens.style.height = lensH + 'px';

      // Position zoom image inside pane
      var paneW = zoomPane.offsetWidth;
      var paneH = zoomPane.offsetHeight;

      // Natural image size estimate
      var imgNatW = mainImg.naturalWidth || sr.width * ZOOM_FACTOR;
      var imgNatH = mainImg.naturalHeight || sr.height * ZOOM_FACTOR;
      var scaleW  = paneW / (sr.width / imgNatW);
      var scaleH  = paneH / (sr.height / imgNatH);

      var ratio = Math.min(scaleW, scaleH);
      var rW = imgNatW * (paneW / (lensW * (imgNatW / sr.width)));
      var rH = imgNatH * (paneH / (lensH * (imgNatH / sr.height)));

      // Simpler: scale image to fill pane × ZOOM_FACTOR
      var scaledW = sr.width * ZOOM_FACTOR;
      var scaledH = sr.height * ZOOM_FACTOR;

      var bgX = -((lx / sr.width) * scaledW - paneW / 2);
      var bgY = -((ly / sr.height) * scaledH - paneH / 2);

      // Clamp bg offset
      bgX = Math.min(0, Math.max(bgX, -(scaledW - paneW)));
      bgY = Math.min(0, Math.max(bgY, -(scaledH - paneH)));

      zoomImg.style.width    = scaledW + 'px';
      zoomImg.style.height   = scaledH + 'px';
      zoomImg.style.left     = bgX + 'px';
      zoomImg.style.top      = bgY + 'px';
    });

    // ── Tap zoom (mobile — pinch-style tap) ──
    stage.addEventListener('click', function(e) {
      if (e.target.closest('.aa-gal__arrow, .aa-gal__fullscreen')) return;
      isMobile = window.innerWidth <= 1280;
      if (!isMobile) return;

      if (!tapZoomed) {
        // Open lightbox on mobile tap
        openLb();
      }
    });

    // ── Touch swipe ──
    var txStart = 0, tyStart = 0;
    stage.addEventListener('touchstart', function(e) {
      txStart = e.changedTouches[0].screenX;
      tyStart = e.changedTouches[0].screenY;
    }, { passive: true });
    stage.addEventListener('touchend', function(e) {
      var dx = txStart - e.changedTouches[0].screenX;
      var dy = tyStart - e.changedTouches[0].screenY;
      if (Math.abs(dx) > 50 && Math.abs(dy) < 60) {
        dx > 0 ? goTo(cur + 1) : goTo(cur - 1);
      }
    }, { passive: true });

    // ── Lightbox ──
    function openLb() {
      lbGoTo(cur);
      lb.classList.add('is-open');
      document.body.style.overflow = 'hidden';
    }
    function closeLb() {
      lb.classList.remove('is-open');
      document.body.style.overflow = '';
    }
    function lbGoTo(idx) {
      if (idx < 0) idx = total - 1;
      if (idx >= total) idx = 0;
      lbImg.style.cssText = 'opacity:0;transform:scale(0.94);transition:opacity .22s,transform .22s;';
      var src = srcs[idx];
      setTimeout(function() {
        lbImg.src = src;
        lbImg.style.cssText = 'opacity:1;transform:scale(1);transition:opacity .22s,transform .22s;';
      }, 120);
      cur = idx;
      updateCounter();
      var dots = lbStrip.querySelectorAll('.aa-gal__lb-dot');
      dots.forEach(function(d, i) {
        d.classList.toggle('is-active', i === idx);
      });
      if (dots[idx]) dots[idx].scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
    }

    lb.addEventListener('click', function(e) {
      if (e.target === lb) closeLb();
    });

    document.addEventListener('keydown', function(e) {
      if (!lb.classList.contains('is-open')) return;
      if (e.key === 'ArrowLeft')  lbGoTo(cur - 1);
      if (e.key === 'ArrowRight') lbGoTo(cur + 1);
      if (e.key === 'Escape') closeLb();
    });

    // ── Public API ──
    window.__aaGal = {
      goTo: goTo,
      goToSrc: function(src) {
        var idx = srcs.indexOf(src);
        if (idx !== -1) { goTo(idx, true); return; }
        // src not in list — inject it temporarily
        mainImg.classList.add('is-loading');
        setTimeout(function() {
          mainImg.src = src;
          zoomImg && (zoomImg.src = src);
          mainImg.classList.remove('is-loading');
        }, 100);
      },
      next: function() { goTo(cur + 1); },
      prev: function() { goTo(cur - 1); },
      openLb: openLb,
      closeLb: closeLb,
      lbNav: function(d) { lbGoTo(cur + d); }
    };

    // ── Init zoom image ──
    zoomImg && mainImg && (zoomImg.src = mainImg.src);

    window.addEventListener('resize', function() {
      isMobile = window.innerWidth <= 1280;
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', AaGallery);
  } else {
    AaGallery();
  }
})();