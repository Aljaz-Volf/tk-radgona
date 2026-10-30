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
      navigation.querySelectorAll('.nav-dropdown[open]').forEach((dropdown) => dropdown.removeAttribute('open'));
    }
  });
}

const dropdowns = [...document.querySelectorAll('.nav-dropdown')];
dropdowns.forEach((dropdown) => {
  dropdown.addEventListener('toggle', () => {
    if (!dropdown.open) return;
    dropdowns.forEach((other) => {
      if (other !== dropdown) other.removeAttribute('open');
    });
  });
});

document.addEventListener('click', (event) => {
  dropdowns.forEach((dropdown) => {
    if (dropdown.open && !dropdown.contains(event.target)) dropdown.removeAttribute('open');
  });
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') dropdowns.forEach((dropdown) => dropdown.removeAttribute('open'));
});

document.querySelectorAll('.flash button').forEach((button) => {
  button.addEventListener('click', () => button.closest('.flash').remove());
});

document.querySelectorAll('[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});

document.querySelectorAll('[data-news-homepage-picker]').forEach((picker) => {
  const modeInput = picker.querySelector('[data-homepage-mode]');
  const help = picker.querySelector('[data-mode-help]');
  const options = picker.querySelector('[data-pinned-options]');
  const buttons = [...picker.querySelectorAll('[data-mode-choice]')];

  const setMode = (mode) => {
    picker.dataset.mode = mode;
    modeInput.value = mode;
    buttons.forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.modeChoice === mode));
    });
    options.setAttribute('aria-hidden', String(mode !== 'pinned'));
    help.textContent = mode === 'pinned'
      ? 'Na domači strani bo prikazana samo izbrana novica.'
      : 'Na domači strani bo vedno prikazana najnovejša objavljena novica.';
  };

  buttons.forEach((button) => {
    button.addEventListener('click', () => setMode(button.dataset.modeChoice));
  });
});

document.querySelectorAll('[data-news-status]').forEach((control) => {
  const select = control.querySelector('select');
  const trigger = control.querySelector('[data-status-trigger]');
  const label = control.querySelector('[data-status-label]');
  const options = [...control.querySelectorAll('[data-status-value]')];

  const close = (returnFocus = false) => {
    control.classList.remove('is-open');
    trigger.setAttribute('aria-expanded', 'false');
    if (returnFocus) trigger.focus();
  };
  const open = () => {
    control.classList.add('is-open');
    trigger.setAttribute('aria-expanded', 'true');
  };
  const update = (value) => {
    select.value = value;
    control.dataset.status = value;
    label.textContent = value === 'published' ? 'Objavljeno' : 'Osnutek';
    options.forEach((option) => {
      option.setAttribute('aria-selected', String(option.dataset.statusValue === value));
    });
    select.dispatchEvent(new Event('change', { bubbles: true }));
  };

  trigger.addEventListener('click', () => {
    if (control.classList.contains('is-open')) close(); else open();
  });
  trigger.addEventListener('keydown', (event) => {
    if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
      event.preventDefault();
      open();
      const selectedIndex = options.findIndex((option) => option.getAttribute('aria-selected') === 'true');
      options[event.key === 'ArrowDown' ? (selectedIndex + 1) % options.length : (selectedIndex - 1 + options.length) % options.length].focus();
    }
    if (event.key === 'Escape') close();
  });
  options.forEach((option, index) => {
    option.addEventListener('click', () => {
      update(option.dataset.statusValue);
      close(true);
    });
    option.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        event.preventDefault(); close(true);
      }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        const offset = event.key === 'ArrowDown' ? 1 : -1;
        options[(index + offset + options.length) % options.length].focus();
      }
    });
  });
  document.addEventListener('click', (event) => {
    if (!control.contains(event.target)) close();
  });
  update(select.value || 'draft');
});

document.querySelectorAll('input[type="file"][accept*="image"]').forEach((input) => {
  const existingContainer = input.closest('[data-news-images]');
  const existingCount = Number(existingContainer?.dataset.existing || 0);
  const configuredMaximum = Number(input.dataset.maxFiles || 0);
  const maximum = configuredMaximum ? Math.max(0, configuredMaximum - existingCount) : Infinity;
  const component = document.createElement('div');
  component.className = 'image-uploader';
  component.innerHTML = `
    <div class="image-upload-zone" data-image-dropzone>
      <svg class="image-upload-icon" viewBox="0 0 64 52" aria-hidden="true">
        <path d="M18 47h31a13 13 0 0 0 2-25.8A19 19 0 0 0 15.3 17 15 15 0 0 0 18 47Z" fill="currentColor"/>
        <path d="M32 37V18m0 0-8 8m8-8 8 8" fill="none" stroke="var(--surface)" stroke-width="4" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <strong>Povlecite in spustite fotografije sem</strong>
      <span>Podprto: JPG, PNG, WebP</span>
      <small>ali</small>
      <button type="button" class="image-browse-button" data-image-browse>Izberi fotografije</button>
      ${Number.isFinite(maximum) ? `<em>Izberete lahko še največ ${maximum} fotografij.</em>` : ''}
    </div>
    <p class="image-upload-message" data-image-message aria-live="polite"></p>
    <div class="image-upload-selection" data-image-selection hidden>
      <div class="image-upload-selection-heading"><strong>Izbrane fotografije</strong><span data-image-total></span></div>
      <div class="image-upload-files" data-image-files></div>
    </div>`;

  input.parentNode.insertBefore(component, input);
  component.appendChild(input);
  input.classList.add('sr-only', 'image-upload-native');

  const zone = component.querySelector('[data-image-dropzone]');
  const browse = component.querySelector('[data-image-browse]');
  const message = component.querySelector('[data-image-message]');
  const selection = component.querySelector('[data-image-selection]');
  const filesContainer = component.querySelector('[data-image-files]');
  const total = component.querySelector('[data-image-total]');
  const newsCounter = existingContainer?.querySelector('[data-news-image-count]');
  let selectedFiles = [];
  let previewUrls = [];

  const formatSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };
  const isSupported = (file) => ['image/jpeg', 'image/png', 'image/webp'].includes(file.type)
    || /\.(jpe?g|png|webp)$/i.test(file.name);
  const uniqueFiles = (files) => files.filter((file, index, all) => all.findIndex((candidate) => (
    candidate.name === file.name && candidate.size === file.size && candidate.lastModified === file.lastModified
  )) === index);

  const syncNativeInput = () => {
    const transfer = new DataTransfer();
    selectedFiles.forEach((file) => transfer.items.add(file));
    input.files = transfer.files;
    input.dispatchEvent(new Event('input', { bubbles: true }));
  };

  const renderFiles = () => {
    previewUrls.forEach((url) => URL.revokeObjectURL(url));
    previewUrls = [];
    filesContainer.innerHTML = '';
    selection.hidden = selectedFiles.length === 0;
    total.textContent = `${selectedFiles.length} ${selectedFiles.length === 1 ? 'datoteka' : 'datotek'}`;

    selectedFiles.forEach((file, index) => {
      const previewUrl = URL.createObjectURL(file);
      previewUrls.push(previewUrl);
      const row = document.createElement('div');
      row.className = 'image-upload-file';

      const image = document.createElement('img');
      image.src = previewUrl;
      image.alt = '';
      const details = document.createElement('div');
      details.className = 'image-upload-file-details';
      const name = document.createElement('strong');
      name.textContent = file.name;
      const metadata = document.createElement('span');
      const modified = file.lastModified
        ? new Intl.DateTimeFormat('sl-SI').format(new Date(file.lastModified))
        : 'Danes';
      metadata.textContent = `${modified} • ${formatSize(file.size)}`;
      details.append(name, metadata);

      const remove = document.createElement('button');
      remove.type = 'button';
      remove.className = 'image-upload-remove';
      remove.setAttribute('aria-label', `Odstrani ${file.name}`);
      remove.addEventListener('click', () => {
        selectedFiles.splice(index, 1);
        message.textContent = '';
        message.classList.remove('is-error');
        syncNativeInput();
        renderFiles();
      });
      row.append(image, details, remove);
      filesContainer.appendChild(row);
    });

    if (newsCounter) {
      newsCounter.textContent = `${existingCount + selectedFiles.length} od 100 fotografij v članku`;
      newsCounter.classList.remove('is-over-limit');
    }
  };

  const addFiles = (incoming) => {
    const combined = input.multiple ? uniqueFiles([...selectedFiles, ...incoming]) : incoming.slice(0, 1);
    const supported = combined.filter(isSupported);
    const rejectedCount = combined.length - supported.length;
    const limited = supported.slice(0, maximum);
    selectedFiles = limited;
    syncNativeInput();
    renderFiles();

    const notices = [];
    if (rejectedCount) notices.push(`${rejectedCount} nepodprtih datotek ni bilo dodanih.`);
    if (supported.length > maximum) notices.push(`Dodate lahko še največ ${maximum} fotografij.`);
    message.textContent = notices.join(' ');
    message.classList.toggle('is-error', notices.length > 0);
  };

  browse.addEventListener('click', (event) => {
    event.stopPropagation();
    input.click();
  });
  zone.addEventListener('click', (event) => {
    if (!event.target.closest('button')) input.click();
  });
  input.addEventListener('change', () => addFiles([...input.files]));

  let dragDepth = 0;
  zone.addEventListener('dragenter', (event) => {
    event.preventDefault();
    dragDepth += 1;
    zone.classList.add('is-dragging');
  });
  zone.addEventListener('dragover', (event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'copy';
  });
  zone.addEventListener('dragleave', () => {
    dragDepth -= 1;
    if (dragDepth <= 0) {
      dragDepth = 0;
      zone.classList.remove('is-dragging');
    }
  });
  zone.addEventListener('drop', (event) => {
    event.preventDefault();
    dragDepth = 0;
    zone.classList.remove('is-dragging');
    addFiles([...event.dataTransfer.files]);
  });
});

const calendarInputs = [...document.querySelectorAll('input[type="date"], input[type="datetime-local"]')];
if (calendarInputs.length) {
  const monthNames = [
    'januar', 'februar', 'marec', 'april', 'maj', 'junij',
    'julij', 'avgust', 'september', 'oktober', 'november', 'december',
  ];
  const weekdayNames = ['Po', 'To', 'Sr', 'Če', 'Pe', 'So', 'Ne'];
  const pad = (value) => String(value).padStart(2, '0');
  const toIsoDate = (date) => `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
  const parseDate = (value) => {
    const match = String(value || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
    if (!match) return null;
    const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    return Number.isNaN(date.getTime()) ? null : date;
  };
  const sameDay = (first, second) => first && second
    && first.getFullYear() === second.getFullYear()
    && first.getMonth() === second.getMonth()
    && first.getDate() === second.getDate();

  const layer = document.createElement('div');
  layer.className = 'calendar-picker-layer';
  layer.setAttribute('aria-hidden', 'true');
  layer.innerHTML = `
    <div class="calendar-picker" role="dialog" aria-modal="true" aria-label="Izberite datum">
      <div class="calendar-picker-header">
        <button type="button" class="calendar-nav" data-calendar-prev aria-label="Prejšnji mesec">‹</button>
        <button type="button" class="calendar-title-button" data-calendar-title-toggle aria-expanded="false">
          <span data-calendar-title></span><span class="calendar-title-arrow" aria-hidden="true"></span>
        </button>
        <button type="button" class="calendar-nav" data-calendar-next aria-label="Naslednji mesec">›</button>
      </div>
      <div class="calendar-month-year" data-calendar-month-year>
        <div class="calendar-year-control">
          <button type="button" data-calendar-year-prev aria-label="Prejšnje leto">‹</button>
          <input type="number" min="1" max="9999" inputmode="numeric" data-calendar-year aria-label="Leto">
          <button type="button" data-calendar-year-next aria-label="Naslednje leto">›</button>
        </div>
        <div class="calendar-months" data-calendar-months></div>
      </div>
      <div class="calendar-weekdays" aria-hidden="true"></div>
      <div class="calendar-days" data-calendar-days></div>
      <div class="calendar-time" data-calendar-time>
        <span>Čas</span>
        <div class="calendar-time-fields">
          <input type="number" min="0" max="23" inputmode="numeric" data-calendar-hour aria-label="Ura">
          <span>:</span>
          <input type="number" min="0" max="59" inputmode="numeric" data-calendar-minute aria-label="Minute">
        </div>
      </div>
      <div class="calendar-picker-actions">
        <button type="button" class="calendar-cancel" data-calendar-cancel>Prekliči</button>
        <button type="button" class="calendar-confirm" data-calendar-confirm>V redu</button>
      </div>
    </div>`;
  document.body.appendChild(layer);

  const picker = layer.querySelector('.calendar-picker');
  const title = layer.querySelector('[data-calendar-title]');
  const titleToggle = layer.querySelector('[data-calendar-title-toggle]');
  const monthYearPanel = layer.querySelector('[data-calendar-month-year]');
  const yearInput = layer.querySelector('[data-calendar-year]');
  const months = layer.querySelector('[data-calendar-months]');
  const weekdays = layer.querySelector('.calendar-weekdays');
  const days = layer.querySelector('[data-calendar-days]');
  const timeRow = layer.querySelector('[data-calendar-time]');
  const hourInput = layer.querySelector('[data-calendar-hour]');
  const minuteInput = layer.querySelector('[data-calendar-minute]');
  weekdays.innerHTML = weekdayNames.map((name) => `<span>${name}</span>`).join('');

  let activeInput = null;
  let selectedDate = null;
  let viewDate = null;

  const setMonthYearOpen = (open) => {
    picker.classList.toggle('is-month-year-open', open);
    titleToggle.setAttribute('aria-expanded', String(open));
    monthYearPanel.setAttribute('aria-hidden', String(!open));
    if (open) requestAnimationFrame(() => yearInput.select());
  };

  const inputLimit = (name) => activeInput?.getAttribute(name)
    ? parseDate(activeInput.getAttribute(name))
    : null;

  const isUnavailable = (date) => {
    const min = inputLimit('min');
    const max = inputLimit('max');
    const value = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
    return (min && value < min.getTime()) || (max && value > max.getTime());
  };

  const renderCalendar = () => {
    title.textContent = `${monthNames[viewDate.getMonth()]} ${viewDate.getFullYear()}`;
    yearInput.value = String(viewDate.getFullYear());
    months.innerHTML = '';
    monthNames.forEach((name, monthIndex) => {
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = name.slice(0, 3);
      button.setAttribute('aria-label', name);
      if (monthIndex === viewDate.getMonth()) {
        button.classList.add('is-selected');
        button.setAttribute('aria-current', 'true');
      }
      button.addEventListener('click', () => {
        viewDate = new Date(viewDate.getFullYear(), monthIndex, 1);
        setMonthYearOpen(false);
        renderCalendar();
        requestAnimationFrame(positionPicker);
      });
      months.appendChild(button);
    });
    const firstOfMonth = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1);
    const mondayOffset = (firstOfMonth.getDay() + 6) % 7;
    const gridStart = new Date(viewDate.getFullYear(), viewDate.getMonth(), 1 - mondayOffset);
    const today = new Date();
    days.innerHTML = '';

    for (let index = 0; index < 42; index += 1) {
      const date = new Date(gridStart.getFullYear(), gridStart.getMonth(), gridStart.getDate() + index);
      const button = document.createElement('button');
      button.type = 'button';
      button.textContent = String(date.getDate());
      button.dataset.date = toIsoDate(date);
      button.setAttribute('aria-label', `${date.getDate()}. ${monthNames[date.getMonth()]} ${date.getFullYear()}`);
      if (date.getMonth() !== viewDate.getMonth()) button.classList.add('is-outside');
      if (sameDay(date, today)) button.classList.add('is-today');
      if (sameDay(date, selectedDate)) {
        button.classList.add('is-selected');
        button.setAttribute('aria-current', 'date');
      }
      if (isUnavailable(date)) button.disabled = true;
      button.addEventListener('click', () => {
        selectedDate = date;
        if (date.getMonth() !== viewDate.getMonth()) {
          viewDate = new Date(date.getFullYear(), date.getMonth(), 1);
        }
        renderCalendar();
      });
      days.appendChild(button);
    }
  };

  const positionPicker = () => {
    if (!activeInput || !layer.classList.contains('is-open')) return;
    picker.classList.toggle('is-centered', window.innerWidth <= 680);
    picker.style.left = '';
    picker.style.top = '';
    if (window.innerWidth <= 680) return;

    const anchor = activeInput.closest('.date-picker-input-shell') || activeInput;
    const anchorRect = anchor.getBoundingClientRect();
    const pickerRect = picker.getBoundingClientRect();
    const left = Math.max(10, Math.min(anchorRect.left, window.innerWidth - pickerRect.width - 10));
    let top = anchorRect.bottom + 8;
    if (top + pickerRect.height > window.innerHeight - 10) {
      top = Math.max(10, anchorRect.top - pickerRect.height - 8);
    }
    picker.style.left = `${left}px`;
    picker.style.top = `${top}px`;
  };

  const closePicker = (save) => {
    if (!activeInput) return;
    const input = activeInput;
    if (save && selectedDate) {
      let value = toIsoDate(selectedDate);
      if (input.type === 'datetime-local') {
        const hours = Math.max(0, Math.min(23, Number(hourInput.value) || 0));
        const minutes = Math.max(0, Math.min(59, Number(minuteInput.value) || 0));
        value += `T${pad(hours)}:${pad(minutes)}`;
      }
      input.value = value;
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
    layer.classList.remove('is-open');
    layer.setAttribute('aria-hidden', 'true');
    activeInput = null;
    input.focus();
  };

  const openPicker = (input) => {
    activeInput = input;
    const now = new Date();
    selectedDate = parseDate(input.value) || new Date(now.getFullYear(), now.getMonth(), now.getDate());
    viewDate = new Date(selectedDate.getFullYear(), selectedDate.getMonth(), 1);
    const timeMatch = input.value.match(/T(\d{2}):(\d{2})/);
    hourInput.value = timeMatch ? timeMatch[1] : pad(now.getHours());
    minuteInput.value = timeMatch ? timeMatch[2] : pad(now.getMinutes());
    timeRow.hidden = input.type !== 'datetime-local';
    setMonthYearOpen(false);
    renderCalendar();
    layer.classList.add('is-open');
    layer.setAttribute('aria-hidden', 'false');
    requestAnimationFrame(() => {
      positionPicker();
      (days.querySelector('.is-selected') || days.querySelector('button:not(:disabled)'))?.focus();
    });
  };

  calendarInputs.forEach((input) => {
    const shell = document.createElement('div');
    shell.className = 'date-picker-input-shell';
    input.parentNode.insertBefore(shell, input);
    shell.appendChild(input);
    input.classList.add('date-picker-input');
    input.readOnly = true;
    input.setAttribute('autocomplete', 'off');

    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'date-picker-input-button';
    button.setAttribute('aria-label', 'Odpri koledar');
    shell.appendChild(button);

    input.addEventListener('click', () => openPicker(input));
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ' || event.key === 'ArrowDown') {
        event.preventDefault();
        openPicker(input);
      }
      if ((event.key === 'Backspace' || event.key === 'Delete') && !input.required) {
        input.value = '';
        input.dispatchEvent(new Event('change', { bubbles: true }));
      }
    });
    button.addEventListener('click', () => openPicker(input));
  });

  titleToggle.addEventListener('click', () => {
    setMonthYearOpen(!picker.classList.contains('is-month-year-open'));
    requestAnimationFrame(positionPicker);
  });
  const changeViewYear = (year) => {
    if (!Number.isInteger(year) || year < 1 || year > 9999) return;
    const nextView = new Date(viewDate);
    nextView.setDate(1);
    nextView.setFullYear(year);
    viewDate = nextView;
    renderCalendar();
  };
  layer.querySelector('[data-calendar-year-prev]').addEventListener('click', () => {
    changeViewYear(viewDate.getFullYear() - 1);
  });
  layer.querySelector('[data-calendar-year-next]').addEventListener('click', () => {
    changeViewYear(viewDate.getFullYear() + 1);
  });
  yearInput.addEventListener('change', () => changeViewYear(Number(yearInput.value)));
  yearInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      changeViewYear(Number(yearInput.value));
    }
  });
  layer.querySelector('[data-calendar-prev]').addEventListener('click', () => {
    viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() - 1, 1);
    renderCalendar();
  });
  layer.querySelector('[data-calendar-next]').addEventListener('click', () => {
    viewDate = new Date(viewDate.getFullYear(), viewDate.getMonth() + 1, 1);
    renderCalendar();
  });
  layer.querySelector('[data-calendar-cancel]').addEventListener('click', () => closePicker(false));
  layer.querySelector('[data-calendar-confirm]').addEventListener('click', () => closePicker(true));
  layer.addEventListener('click', (event) => {
    if (event.target === layer) closePicker(false);
  });
  days.addEventListener('keydown', (event) => {
    const dayButtons = [...days.querySelectorAll('button:not(:disabled)')];
    const index = dayButtons.indexOf(document.activeElement);
    const offsets = { ArrowLeft: -1, ArrowRight: 1, ArrowUp: -7, ArrowDown: 7 };
    if (index >= 0 && offsets[event.key]) {
      event.preventDefault();
      dayButtons[Math.max(0, Math.min(dayButtons.length - 1, index + offsets[event.key]))]?.focus();
    }
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape' && layer.classList.contains('is-open')) closePicker(false);
  });
  window.addEventListener('resize', positionPicker);
}

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
    const description = links[current].dataset.caption || '';
    caption.textContent = `${description}${description ? ' · ' : ''}${current + 1} / ${links.length}`;
  };
  links.forEach((link, index) => link.addEventListener('click', (event) => {
    event.preventDefault(); show(index); lightbox.showModal();
  }));
  lightbox.querySelector('[data-prev]')?.addEventListener('click', () => show(current - 1));
  lightbox.querySelector('[data-next]')?.addEventListener('click', () => show(current + 1));
  lightbox.querySelector('[data-close]')?.addEventListener('click', () => lightbox.close());
  if (links.length > 1) {
    lightbox.classList.add('has-multiple');
    image.addEventListener('click', () => show(current + 1));
  }
}

