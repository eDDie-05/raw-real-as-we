(() => {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
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
