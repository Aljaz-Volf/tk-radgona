const toggle = document.querySelector('.menu-toggle');
const navigation = document.querySelector('.site-nav');

if (toggle && navigation) {
  toggle.addEventListener('click', () => {
    const open = toggle.getAttribute('aria-expanded') === 'true';
    toggle.setAttribute('aria-expanded', String(!open));
    navigation.classList.toggle('is-open', !open);
  });
  navigation.addEventListener('click', (event) => {
    if (event.target.closest('a')) {
      toggle.setAttribute('aria-expanded', 'false');
      navigation.classList.remove('is-open');
    }
  });
}

document.querySelectorAll('.flash button').forEach((button) => {
  button.addEventListener('click', () => button.closest('.flash').remove());
});

document.querySelectorAll('[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

const lightbox = document.querySelector('[data-lightbox]');
if (lightbox) {
  const image = lightbox.querySelector('img');
  const caption = lightbox.querySelector('figcaption');
  const links = [...document.querySelectorAll('[data-lightbox-item]')];
  let current = 0;
  const show = (index) => {
    current = (index + links.length) % links.length;
    image.src = links[current].href;
    image.alt = links[current].dataset.caption || '';
    caption.textContent = links[current].dataset.caption || '';
  };
  links.forEach((link, index) => link.addEventListener('click', (event) => {
    event.preventDefault(); show(index); lightbox.showModal();
  }));
  lightbox.querySelector('[data-prev]')?.addEventListener('click', () => show(current - 1));
  lightbox.querySelector('[data-next]')?.addEventListener('click', () => show(current + 1));
  lightbox.querySelector('[data-close]')?.addEventListener('click', () => lightbox.close());
}

