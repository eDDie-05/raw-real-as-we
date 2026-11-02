(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const installBanner = document.querySelector('#pwa-install-banner');
  const installButton = document.querySelector('[data-pwa-install]');
  const helpDialog = document.querySelector('#pwa-help-dialog');
  let deferredInstallPrompt = null;
  const installedMode = window.matchMedia('(display-mode: standalone)').matches || window.navigator.standalone === true;
  const hideInstallBanner = (remember = false) => {
    if (installBanner) installBanner.hidden = true;
    if (remember) {
      try { window.localStorage.setItem('raw-install-dismissed', '1'); } catch (_) { /* storage can be disabled */ }
    }
  };
  const openInstallGuide = () => {
    if (!helpDialog) return;
    const ua = navigator.userAgent;
    const ios = /iPad|iPhone|iPod/.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
    const android = /Android/i.test(ua);
    const selector = ios ? '.pwa-ios-help' : android ? '.pwa-android-help' : /Mac|Win|Linux/i.test(navigator.platform) ? '.pwa-desktop-help' : '.pwa-generic-help';
    helpDialog.querySelectorAll('.pwa-ios-help, .pwa-android-help, .pwa-desktop-help, .pwa-generic-help').forEach((item) => { item.hidden = !item.matches(selector); });
    if (helpDialog.showModal) helpDialog.showModal();
  };
  window.addEventListener('beforeinstallprompt', (event) => {
    event.preventDefault();
    deferredInstallPrompt = event;
    if (installButton) installButton.textContent = 'INSTALL RAW APP ↗';
    if (installBanner && !installedMode) {
      let dismissed = false;
      try { dismissed = window.localStorage.getItem('raw-install-dismissed') === '1'; } catch (_) { /* storage can be disabled */ }
      if (!dismissed) installBanner.hidden = false;
    }
  });
  window.addEventListener('appinstalled', () => hideInstallBanner(true));
  installButton?.addEventListener('click', async () => {
    if (!deferredInstallPrompt) {
      openInstallGuide();
      return;
    }
    deferredInstallPrompt.prompt();
    const result = await deferredInstallPrompt.userChoice;
    deferredInstallPrompt = null;
    if (result?.outcome === 'accepted') hideInstallBanner(true);
  });
  document.querySelectorAll('[data-pwa-help]').forEach((button) => button.addEventListener('click', openInstallGuide));
  document.querySelectorAll('[data-pwa-help-close]').forEach((button) => button.addEventListener('click', () => helpDialog?.close()));
  document.querySelector('[data-pwa-dismiss]')?.addEventListener('click', () => hideInstallBanner(true));
  if (installBanner && !installedMode) {
    let dismissed = false;
    try { dismissed = window.localStorage.getItem('raw-install-dismissed') === '1'; } catch (_) { /* storage can be disabled */ }
    if (!dismissed) window.setTimeout(() => { installBanner.hidden = false; }, 1300);
  }
  if ('serviceWorker' in navigator && (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
    navigator.serviceWorker.register('/service-worker.js', { scope: '/' }).catch(() => {});
  }
  const campaignVideo = document.querySelector('[data-raw-campaign-video]');
  if (campaignVideo && !reduceMotion && 'IntersectionObserver' in window) {
    const videoObserver = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) campaignVideo.play().catch(() => {});
      else campaignVideo.pause();
    }), { threshold: 0.3 });
    videoObserver.observe(campaignVideo);
  }

  const transition = document.querySelector('.page-transition');
  if (transition && !reduceMotion) {
    transition.classList.add('is-entering');
    window.setTimeout(() => transition.classList.remove('is-entering'), 520);
    document.addEventListener('click', (event) => {
      const link = event.target.closest('a[href]');
      if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      if (link.target || link.hasAttribute('download') || link.hasAttribute('data-quick-view')) return;
      const destination = new URL(link.href, window.location.href);
      if (destination.origin !== window.location.origin || destination.href === window.location.href || destination.hash && destination.pathname === window.location.pathname) return;
      event.preventDefault();
      transition.classList.remove('is-entering');
      transition.classList.add('is-active');
      window.setTimeout(() => { window.location.href = destination.href; }, 190);
    });
  }

  const menu = document.querySelector('.menu-toggle');
  const nav = document.querySelector('#main-nav');
  menu?.addEventListener('click', () => {
    const open = menu.getAttribute('aria-expanded') !== 'true';
    menu.setAttribute('aria-expanded', String(open));
    menu.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    nav?.classList.toggle('is-open', open);
    document.body.classList.toggle('menu-open', open);
  });

  document.querySelectorAll('[data-dismiss], .toast button').forEach((button) => {
    button.addEventListener('click', () => button.closest('.toast')?.remove());
  });

  if (!reduceMotion && 'IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    }), { threshold: 0.12 });
    document.querySelectorAll('.reveal').forEach((element) => observer.observe(element));
  } else {
    document.querySelectorAll('.reveal').forEach((element) => element.classList.add('is-visible'));
  }

  function wireVariants(root = document) {
    root.querySelectorAll('.variant-picker-scope').forEach((scope) => {
      if (scope.dataset.ready) return;
      scope.dataset.ready = '1';
      const json = scope.querySelector('#product-variants');
      const variants = json ? JSON.parse(json.textContent) : [];
      const form = scope.closest('form');
      const sizeButtons = [...scope.querySelectorAll('[data-size-choice]')];
      const colourSelect = scope.querySelector('[data-colour-select]');
      const hiddenId = form?.querySelector('[name="variant_id"]');
      const addButton = form?.querySelector('[data-add-to-bag]');
      const note = scope.querySelector('[data-stock-message]');
      const price = scope.closest('.quick-view-copy, .product-detail-copy')?.querySelector('#quick-view-price, #variant-price');
      const selectedColour = scope.querySelector('.selected-colour');
      let selectedSize = '';
      const update = () => {
        const variant = variants.find((item) => item.size === selectedSize && item.colour === (colourSelect?.value || ''));
        if (hiddenId) hiddenId.value = variant?.available ? variant.id : '';
        if (addButton) addButton.disabled = !variant?.available;
        if (note) note.textContent = !selectedSize || !colourSelect?.value
          ? 'Choose a size and colour.'
          : variant?.available ? `${variant.stock} available · ready to add.` : 'This combination is currently unavailable.';
        if (price && variant) price.textContent = `${Number(variant.price).toLocaleString('en-US')} TZS`;
        if (selectedColour) selectedColour.textContent = colourSelect?.value ? `· ${colourSelect.value}` : '';
      };
      sizeButtons.forEach((button) => button.addEventListener('click', () => {
        selectedSize = button.dataset.sizeChoice;
        sizeButtons.forEach((item) => item.setAttribute('aria-pressed', String(item === button)));
        update();
      }));
      colourSelect?.addEventListener('change', update);
      update();
    });
  }
  wireVariants();

  document.querySelectorAll('[data-quantity-step]').forEach((button) => button.addEventListener('click', () => {
    const input = button.closest('.quantity-control')?.querySelector('input');
    if (!input) return;
    input.value = Math.max(Number(input.min || 1), Math.min(Number(input.max || 99), Number(input.value || 1) + Number(button.dataset.quantityStep)));
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }));

  document.querySelectorAll('[data-image-url]').forEach((button) => button.addEventListener('click', () => {
    const image = document.querySelector('#main-product-image');
    if (!image) return;
    image.src = button.dataset.imageUrl;
    image.alt = button.dataset.imageAlt || '';
    document.querySelectorAll('[data-image-url]').forEach((item) => item.classList.toggle('is-active', item === button));
  }));

  const dialog = document.querySelector('#quick-view-dialog');
  const quickContent = dialog?.querySelector('.quick-view-content');
  document.querySelectorAll('[data-quick-view]').forEach((link) => link.addEventListener('click', async (event) => {
    if (!dialog || !quickContent || !dialog.showModal) return;
    event.preventDefault();
    quickContent.innerHTML = '<p class="loading-note">RAW. ONE MOMENT.</p>';
    dialog.showModal();
    try {
      const response = await fetch(link.href, { headers: { 'X-Requested-With': 'XMLHttpRequest' } });
      if (!response.ok) throw new Error('Could not load this piece.');
      quickContent.innerHTML = await response.text();
      wireVariants(dialog);
    } catch (error) {
      quickContent.innerHTML = `<p>${error.message} <a href="${link.href}">View product</a></p>`;
    }
  }));
  dialog?.querySelector('.dialog-close')?.addEventListener('click', () => dialog.close());
  dialog?.addEventListener('click', (event) => { if (event.target === dialog) dialog.close(); });
  document.addEventListener('keydown', (event) => { if (event.key === 'Escape') nav?.classList.remove('is-open'); });
})();
