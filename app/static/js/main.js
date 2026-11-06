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

document.querySelectorAll('[data-match-result-form]').forEach((form) => {
  const playerNames = [form.dataset.playerOne, form.dataset.playerTwo];
  const hiddenScore = form.querySelector('input[name="score"]');
  const summary = form.querySelector('[data-result-summary]');
  const winnerSummary = form.querySelector('[data-result-winner]');
  const hint = form.querySelector('[data-result-hint]');
  const setOutputs = [
    form.querySelector('[data-sets-won="1"]'),
    form.querySelector('[data-sets-won="2"]'),
  ];
  const inputs = [...form.querySelectorAll('.match-score-input')];
  let resultComplete = false;

  let clientError = form.querySelector('[data-client-score-error]');
  if (!clientError) {
    clientError = document.createElement('div');
    clientError.className = 'match-score-errors';
    clientError.dataset.clientScoreError = '';
    clientError.setAttribute('role', 'alert');
    clientError.hidden = true;
    hint.before(clientError);
  }

  const inputFor = (set, player) => form.querySelector(`.match-score-input[data-set="${set}"][data-player="${player}"]`);
  const valueOf = (set, player) => {
    const raw = inputFor(set, player)?.value.trim();
    if (raw === '') return null;
    const value = Number(raw);
    return Number.isInteger(value) && value >= 0 ? value : null;
  };
  const isStandardSet = (first, second) => {
    const high = Math.max(first, second);
    const low = Math.min(first, second);
    return (high === 6 && low <= 4) || (high === 7 && (low === 5 || low === 6));
  };
  const isMatchTiebreak = (first, second) => Math.max(first, second) >= 10 && Math.abs(first - second) >= 2;

  const evaluateSet = (set, validator) => {
    const first = valueOf(set, 1);
    const second = valueOf(set, 2);
    const cells = [1, 2].map((player) => inputFor(set, player)?.closest('[data-score-cell]'));
    cells.forEach((cell) => cell?.classList.remove('is-winner', 'is-loser'));
    if (first === null || second === null || first === second || !validator(first, second)) return 0;
    const winner = first > second ? 1 : 2;
    cells[winner - 1]?.classList.add('is-winner');
    cells[2 - winner]?.classList.add('is-loser');
    return winner;
  };

  const update = () => {
    const firstWinner = evaluateSet(1, isStandardSet);
    const secondWinner = evaluateSet(2, isStandardSet);
    const splitSets = firstWinner > 0 && secondWinner > 0 && firstWinner !== secondWinner;
    const straightSets = firstWinner > 0 && firstWinner === secondWinner;
    const thirdInputs = [inputFor(3, 1), inputFor(3, 2)];

    thirdInputs.forEach((input) => {
      input.disabled = !splitSets;
      input.closest('[data-score-cell]')?.classList.toggle('is-disabled', !splitSets);
      if (!splitSets) input.value = '';
    });
    const thirdWinner = splitSets ? evaluateSet(3, isMatchTiebreak) : 0;
    if (!splitSets) {
      [1, 2].forEach((player) => inputFor(3, player)?.closest('[data-score-cell]')?.classList.remove('is-winner', 'is-loser'));
    }

    const wins = [0, 0];
    [firstWinner, secondWinner, thirdWinner].forEach((winner) => {
      if (winner) wins[winner - 1] += 1;
    });
    setOutputs.forEach((output, index) => {
      output.value = String(wins[index]);
      output.textContent = String(wins[index]);
      output.classList.toggle('is-leading', wins[index] > wins[1 - index]);
    });

    const parts = [];
    [1, 2].forEach((set) => {
      const first = valueOf(set, 1);
      const second = valueOf(set, 2);
      if (first !== null && second !== null) parts.push(`${first}-${second}`);
    });
    if (splitSets) {
      const first = valueOf(3, 1);
      const second = valueOf(3, 2);
      if (first !== null && second !== null) parts.push(`${first}-${second}`);
    }
    hiddenScore.value = parts.join(', ');
    summary.textContent = parts.length ? parts.join(', ') : '—';

    resultComplete = straightSets || (splitSets && thirdWinner > 0);
    if (resultComplete) {
      const winnerIndex = wins[0] > wins[1] ? 0 : 1;
      winnerSummary.textContent = `${playerNames[winnerIndex]} · ${wins[0]}:${wins[1]}`;
      clientError.hidden = true;
    } else {
      winnerSummary.textContent = 'Rezultat še ni popoln';
    }

    if (splitSets) {
      hint.dataset.state = 'decider';
      hint.querySelector('p').textContent = 'Po dveh nizih je 1:1. Vpišite še odločilni 3. niz do najmanj 10 točk in na dve točki razlike.';
    } else if (straightSets) {
      hint.dataset.state = 'straight';
      hint.querySelector('p').textContent = 'Isti igralec je dobil oba niza. Tekma je zaključena z 2:0, zato tretji niz ni potreben.';
    } else {
      hint.dataset.state = 'incomplete';
      hint.querySelector('p').textContent = 'Vpišite prva dva niza. Če bo rezultat 1:1, se bo omogočil odločilni 3. niz do 10.';
    }
  };

  inputs.forEach((input) => {
    input.addEventListener('input', update);
    input.addEventListener('focus', () => input.select());
  });
  form.addEventListener('submit', (event) => {
    update();
    if (!resultComplete) {
      event.preventDefault();
      clientError.innerHTML = '<span>Vnesite veljaven končni rezultat tekme.</span>';
      clientError.hidden = false;
      const firstEmpty = inputs.find((input) => !input.disabled && input.value.trim() === '');
      (firstEmpty || inputs.find((input) => !input.disabled))?.focus();
    }
  });
  update();
});

document.querySelectorAll('[data-league-sorter]').forEach((sorter) => {
  const assignmentInput = sorter.querySelector('[data-league-assignments]');
  const columns = [...sorter.querySelectorAll('[data-league-column]')];
  const cards = [...sorter.querySelectorAll('[data-player-id]')];
  const cardsById = new Map(cards.map((card) => [String(card.dataset.playerId), card]));
  const suggestionElement = sorter.querySelector('[data-league-suggestion]');
  const suggestButton = document.querySelector('[data-league-suggest]');
  const search = sorter.querySelector('[data-player-search]');
  const filterButtons = [...sorter.querySelectorAll('[data-player-filter]')];
  let activeFilter = 'all';
  let selectedCard = null;

  const listForGroup = (groupId) => columns.find((column) => column.dataset.groupId === String(groupId))?.querySelector('[data-player-list]');
  const cardsIn = (column) => [...column.querySelector('[data-player-list]').querySelectorAll('[data-player-id]')];
  const canReceive = (column, card) => {
    if (!column.dataset.groupId) return true;
    const capacity = Number(column.dataset.capacity);
    return card.closest('[data-league-column]') === column || cardsIn(column).length < capacity;
  };

  const updateTag = (card) => {
    const tag = card.querySelector('[data-player-tag]');
    const column = card.closest('[data-league-column]');
    const currentIndex = Number(column.dataset.groupIndex);
    const previousIndex = card.dataset.previousIndex === '' ? null : Number(card.dataset.previousIndex);
    tag.className = '';

    if (card.dataset.isNew === 'true') {
      tag.textContent = 'Nov';
      tag.classList.add('is-new');
    } else if (currentIndex < 0 || previousIndex === currentIndex) {
      tag.textContent = `${card.dataset.previousLabel || 'Prej'}: ${card.dataset.previousName}`;
    } else if (previousIndex !== null && currentIndex < previousIndex) {
      tag.textContent = `↑ iz ${card.dataset.previousName}`;
      tag.classList.add('is-promoted');
    } else if (previousIndex !== null && currentIndex > previousIndex) {
      tag.textContent = `↓ iz ${card.dataset.previousName}`;
      tag.classList.add('is-relegated');
    } else {
      tag.textContent = card.dataset.previousName;
    }
  };

  const sync = () => {
    const payload = { groups: {}, unassigned: [] };
    columns.forEach((column) => {
      const columnCards = cardsIn(column);
      const count = column.querySelector('[data-column-count]');
      count.textContent = String(columnCards.length);
      column.classList.toggle('is-full', Boolean(column.dataset.groupId) && columnCards.length >= Number(column.dataset.capacity));
      const capacityBar = column.querySelector('[data-capacity-bar]');
      if (capacityBar) capacityBar.style.width = `${Math.min(100, columnCards.length / Number(column.dataset.capacity) * 100)}%`;

      columnCards.forEach((card, index) => {
        const seed = card.querySelector('[data-player-seed]');
        seed.textContent = column.dataset.groupId ? String(index + 1) : '';
        updateTag(card);
      });
      const ids = columnCards.map((card) => Number(card.dataset.playerId));
      if (column.dataset.groupId) payload.groups[column.dataset.groupId] = ids;
      else payload.unassigned = ids;
    });
    assignmentInput.value = JSON.stringify(payload);
    applyFilter();
  };

  const applyFilter = () => {
    const query = (search?.value || '').trim().toLocaleLowerCase('sl');
    const unassignedColumn = columns.find((column) => !column.dataset.groupId);
    if (!unassignedColumn) return;
    columns.filter((column) => column.dataset.groupId).forEach((column) => {
      cardsIn(column).forEach((card) => { card.hidden = false; });
    });
    cardsIn(unassignedColumn).forEach((card) => {
      const matchesSearch = !query || card.dataset.playerName.includes(query);
      const matchesFilter = activeFilter === 'all'
        || (activeFilter === 'new' && card.dataset.isNew === 'true')
        || (activeFilter === 'returning' && card.dataset.isNew !== 'true');
      card.hidden = !(matchesSearch && matchesFilter);
    });
  };

  const selectCard = (card) => {
    if (selectedCard && selectedCard !== card) selectedCard.setAttribute('aria-pressed', 'false');
    selectedCard = selectedCard === card ? null : card;
    card.setAttribute('aria-pressed', String(selectedCard === card));
  };

  const moveCard = (card, column, before = null) => {
    if (!card || !canReceive(column, card)) return false;
    const list = column.querySelector('[data-player-list]');
    list.insertBefore(card, before);
    card.setAttribute('aria-pressed', 'false');
    selectedCard = null;
    sync();
    return true;
  };

  const cardAfterPointer = (list, pointerY) => {
    const candidates = [...list.querySelectorAll('[data-player-id]:not(.is-dragging):not([hidden])')];
    return candidates.reduce((closest, card) => {
      const box = card.getBoundingClientRect();
      const offset = pointerY - box.top - box.height / 2;
      return offset < 0 && offset > closest.offset ? { offset, card } : closest;
    }, { offset: Number.NEGATIVE_INFINITY, card: null }).card;
  };

  cards.forEach((card) => {
    card.addEventListener('click', () => selectCard(card));
    card.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ' ') {
        event.preventDefault();
        selectCard(card);
      }
    });
    card.addEventListener('dragstart', (event) => {
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', card.dataset.playerId);
      card.classList.add('is-dragging');
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('is-dragging');
      columns.forEach((column) => column.classList.remove('is-drag-over'));
    });
  });

  columns.forEach((column) => {
    column.addEventListener('dragover', (event) => {
      const card = sorter.querySelector('.league-player-card.is-dragging');
      if (!card || !canReceive(column, card)) return;
      event.preventDefault();
      event.dataTransfer.dropEffect = 'move';
      columns.forEach((item) => item.classList.toggle('is-drag-over', item === column));
    });
    column.addEventListener('dragleave', (event) => {
      if (!column.contains(event.relatedTarget)) column.classList.remove('is-drag-over');
    });
    column.addEventListener('drop', (event) => {
      event.preventDefault();
      const card = cardsById.get(event.dataTransfer.getData('text/plain'));
      const list = column.querySelector('[data-player-list]');
      moveCard(card, column, cardAfterPointer(list, event.clientY));
      columns.forEach((item) => item.classList.remove('is-drag-over'));
    });
    column.querySelector('[data-drop-zone]')?.addEventListener('click', () => moveCard(selectedCard, column));
    column.addEventListener('click', (event) => {
      if (selectedCard && !event.target.closest('[data-player-id], button, input')) moveCard(selectedCard, column);
    });
  });

  search?.addEventListener('input', applyFilter);
  filterButtons.forEach((button) => button.addEventListener('click', () => {
    activeFilter = button.dataset.playerFilter;
    filterButtons.forEach((item) => item.classList.toggle('is-active', item === button));
    applyFilter();
  }));

  suggestButton?.addEventListener('click', () => {
    const suggestion = JSON.parse(suggestionElement.textContent);
    Object.entries(suggestion.groups).forEach(([groupId, playerIds]) => {
      const list = listForGroup(groupId);
      playerIds.forEach((playerId) => list?.appendChild(cardsById.get(String(playerId))));
    });
    const unassignedList = listForGroup('');
    suggestion.unassigned.forEach((playerId) => unassignedList?.appendChild(cardsById.get(String(playerId))));
    sync();
  });

  sync();
});

document.querySelectorAll('[data-season-create-form]').forEach((form) => {
  const list = form.querySelector('[data-season-league-list]');
  const defaults = JSON.parse(form.querySelector('[data-default-leagues]').textContent);
  const addButton = form.querySelector('[data-add-league]');
  const resetButton = form.querySelector('[data-reset-leagues]');
  const promotionsToggle = form.querySelector('input[name="apply_promotions"]');
  const promotionsCount = form.querySelector('input[name="promotions_per_boundary"]');
  let draggedRow = null;

  const bindRow = (row) => {
    const handle = row.querySelector('.season-league-handle');
    row.querySelector('[data-delete-league]').addEventListener('click', () => row.remove());
    handle.addEventListener('dragstart', (event) => {
      draggedRow = row;
      row.classList.add('is-dragging');
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', 'league-row');
    });
    handle.addEventListener('dragend', () => {
      row.classList.remove('is-dragging');
      draggedRow = null;
    });
  };

  const createRow = (data = {}) => {
    const row = document.createElement('div');
    row.className = 'season-league-row';
    row.dataset.seasonLeagueRow = '';
    row.innerHTML = `
      <button class="season-league-handle" type="button" draggable="true" aria-label="Premakni ligo" tabindex="-1">⠿</button>
      <input type="hidden" name="league_source_group_id">
      <label><span>Ime lige</span><input class="input" type="text" name="league_name" maxlength="100" required></label>
      <label class="season-league-capacity"><span>Največ</span><input class="input" type="number" name="league_max_players" min="1" max="64" required><small>igralcev</small></label>
      <button class="season-league-delete" type="button" data-delete-league aria-label="Izbriši ligo">×</button>`;
    row.querySelector('[name="league_source_group_id"]').value = data.source_group_id || '';
    row.querySelector('[name="league_name"]').value = data.name || '';
    row.querySelector('[name="league_max_players"]').value = data.max_players || 8;
    bindRow(row);
    return row;
  };

  list.querySelectorAll('[data-season-league-row]').forEach(bindRow);
  list.addEventListener('dragover', (event) => {
    if (!draggedRow) return;
    event.preventDefault();
    const candidates = [...list.querySelectorAll('[data-season-league-row]:not(.is-dragging)')];
    const after = candidates.reduce((closest, row) => {
      const box = row.getBoundingClientRect();
      const offset = event.clientY - box.top - box.height / 2;
      return offset < 0 && offset > closest.offset ? { offset, row } : closest;
    }, { offset: Number.NEGATIVE_INFINITY, row: null }).row;
    list.insertBefore(draggedRow, after);
  });
  list.addEventListener('drop', (event) => event.preventDefault());
  addButton.addEventListener('click', () => {
    const row = createRow({ name: `${list.children.length + 1}. Liga`, max_players: 8 });
    list.appendChild(row);
    row.querySelector('[name="league_name"]').select();
  });
  resetButton.addEventListener('click', () => {
    list.replaceChildren(...defaults.map(createRow));
  });

  const syncPromotionOption = () => {
    promotionsCount.readOnly = !promotionsToggle.checked;
    promotionsToggle.closest('.season-promotion-option').classList.toggle('is-disabled', !promotionsToggle.checked);
  };
  promotionsToggle.addEventListener('change', syncPromotionOption);
  syncPromotionOption();
});

document.querySelectorAll('[data-movements-form]').forEach((form) => {
  const checkboxes = [...form.querySelectorAll('input[name="moves"]')];
  const confirmCount = form.querySelector('[data-confirm-count]');
  const proposedCount = form.querySelector('[data-proposed-count]');
  const updateCount = () => {
    const count = checkboxes.filter((checkbox) => checkbox.checked).length;
    confirmCount.textContent = String(count);
    proposedCount.textContent = String(count);
  };
  checkboxes.forEach((checkbox) => checkbox.addEventListener('change', updateCount));
  updateCount();
});

document.querySelectorAll('[data-match-form]').forEach((form) => {
  const data = JSON.parse(form.querySelector('[data-match-player-data]').textContent);
  const seasonSelect = form.querySelector('[data-match-season]');
  const groupSelect = form.querySelector('[data-match-group]');
  const pickers = [...form.querySelectorAll('[data-match-player-picker]')].map((element) => ({
    element,
    number: Number(element.dataset.matchPlayerPicker),
    select: element.querySelector('[data-match-player-select]'),
    trigger: element.querySelector('[data-player-trigger]'),
    triggerLabel: element.querySelector('[data-trigger-label]'),
    triggerAvatar: element.querySelector('[data-trigger-avatar]'),
    popover: element.querySelector('[data-player-popover]'),
    search: element.querySelector('[data-player-search]'),
    options: element.querySelector('[data-player-options]'),
    empty: element.querySelector('[data-player-empty]'),
    groupLabel: element.querySelector('[data-picker-group-label]'),
    showAllButton: element.querySelector('[data-show-all-players]'),
    showAll: false,
  }));

  const currentGroup = () => data.groups[String(groupSelect.value)] || null;
  const playerById = (id) => data.players[String(id)] || null;
  const pickerByNumber = (number) => pickers.find((picker) => picker.number === number);
  const pairKey = (firstId, secondId) => [Number(firstId), Number(secondId)].sort((a, b) => a - b).join(':');

  const closePicker = (picker, returnFocus = false) => {
    picker.popover.hidden = true;
    picker.element.classList.remove('is-open');
    picker.trigger.setAttribute('aria-expanded', 'false');
    if (returnFocus) picker.trigger.focus();
  };
  const closeAll = (except = null) => pickers.forEach((picker) => {
    if (picker !== except) closePicker(picker);
  });

  const updateTrigger = (picker) => {
    const player = playerById(picker.select.value);
    if (!player) {
      picker.triggerLabel.textContent = picker.number === 1 ? 'Izberi prvega igralca' : 'Izberi nasprotnika';
      picker.triggerAvatar.hidden = true;
      return;
    }
    picker.triggerLabel.textContent = player.name;
    picker.triggerAvatar.textContent = player.initials;
    picker.triggerAvatar.hidden = false;
  };

  const renderPicker = (picker) => {
    const group = currentGroup();
    const query = picker.search.value.trim().toLocaleLowerCase('sl');
    const groupPlayers = group?.players || [];
    const groupPlayerMap = new Map(groupPlayers.map((player) => [String(player.id), player]));
    const players = picker.showAll
      ? Object.values(data.players).sort((first, second) => first.name.localeCompare(second.name, 'sl'))
      : groupPlayers;
    const otherPicker = pickerByNumber(picker.number === 1 ? 2 : 1);
    const otherSelectedId = Number(otherPicker.select.value || 0);
    const firstPlayerId = Number(pickerByNumber(1).select.value || 0);

    picker.options.innerHTML = '';
    let visibleCount = 0;
    players.forEach((player) => {
      if (query && !player.name.toLocaleLowerCase('sl').includes(query)) return;
      const groupPlayer = groupPlayerMap.get(String(player.id));
      const isDuplicate = player.id === otherSelectedId && otherSelectedId > 0;
      const isSelected = String(player.id) === picker.select.value;
      const option = document.createElement('button');
      option.type = 'button';
      option.className = 'match-picker-option';
      option.setAttribute('role', 'option');
      option.setAttribute('aria-selected', String(isSelected));
      option.classList.toggle('is-selected', isSelected);
      option.disabled = isDuplicate;

      const avatar = document.createElement('span');
      avatar.className = 'match-picker-option-avatar';
      avatar.textContent = player.initials;
      const copy = document.createElement('span');
      copy.className = 'match-picker-option-copy';
      const name = document.createElement('strong');
      name.textContent = player.name;
      const meta = document.createElement('small');
      meta.textContent = groupPlayer
        ? `${groupPlayer.rank}. mesto · ${groupPlayer.points} ${groupPlayer.points === 1 ? 'točka' : 'točk'}`
        : `Ni v ligi ${group?.name || ''}`;
      copy.append(name, meta);
      option.append(avatar, copy);

      const tag = document.createElement('span');
      tag.className = 'match-picker-tag';
      if (isDuplicate) {
        tag.textContent = 'Izbran';
        option.appendChild(tag);
      } else if (picker.number === 2 && firstPlayerId > 0) {
        const count = group?.history?.[pairKey(firstPlayerId, player.id)] || 0;
        tag.textContent = count ? `Odigrano ${count}×` : 'Še ni odigrano';
        tag.classList.toggle('is-unplayed', count === 0);
        option.appendChild(tag);
      }

      option.addEventListener('click', () => {
        picker.select.value = String(player.id);
        picker.select.dispatchEvent(new Event('change', { bubbles: true }));
        updateTrigger(picker);
        closePicker(picker, true);
        if (picker.number === 1) renderPicker(pickerByNumber(2));
      });
      option.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
          event.preventDefault();
          closePicker(picker, true);
        }
        if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
          event.preventDefault();
          const available = [...picker.options.querySelectorAll('button:not(:disabled)')];
          const index = available.indexOf(option);
          const offset = event.key === 'ArrowDown' ? 1 : -1;
          available[(index + offset + available.length) % available.length]?.focus();
        }
      });
      picker.options.appendChild(option);
      visibleCount += 1;
    });

    picker.empty.hidden = visibleCount > 0;
    picker.groupLabel.textContent = picker.showAll
      ? `Vsi aktivni igralci · ${visibleCount}`
      : group ? `${group.name} · ${groupPlayers.length} igralcev` : 'Izberite skupino';
    picker.showAllButton.textContent = picker.showAll ? 'Pokaži samo igralce iz lige' : 'Pokaži vse igralce';
  };

  const openPicker = (picker) => {
    closeAll(picker);
    picker.popover.hidden = false;
    picker.element.classList.add('is-open');
    picker.trigger.setAttribute('aria-expanded', 'true');
    picker.search.value = '';
    renderPicker(picker);
    requestAnimationFrame(() => picker.search.focus());
  };

  pickers.forEach((picker) => {
    updateTrigger(picker);
    picker.trigger.addEventListener('click', () => {
      if (picker.popover.hidden) openPicker(picker); else closePicker(picker);
    });
    picker.trigger.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        openPicker(picker);
      }
    });
    picker.search.addEventListener('input', () => renderPicker(picker));
    picker.search.addEventListener('keydown', (event) => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        picker.options.querySelector('button:not(:disabled)')?.focus();
      }
      if (event.key === 'Escape') {
        event.preventDefault();
        closePicker(picker, true);
      }
    });
    picker.showAllButton.addEventListener('click', () => {
      picker.showAll = !picker.showAll;
      picker.search.value = '';
      renderPicker(picker);
      picker.search.focus();
    });
  });

  const filterGroupsForSeason = () => {
    const seasonId = Number(seasonSelect.value);
    const options = [...groupSelect.options];
    options.forEach((option) => {
      const group = data.groups[String(option.value)];
      const visible = group && Number(group.season_id) === seasonId;
      option.hidden = !visible;
      option.disabled = !visible;
    });
    if (groupSelect.selectedOptions[0]?.disabled) {
      const first = options.find((option) => !option.disabled);
      if (first) groupSelect.value = first.value;
    }
  };
  const refreshPickers = () => {
    pickers.forEach((picker) => {
      picker.showAll = false;
      updateTrigger(picker);
      if (!picker.popover.hidden) renderPicker(picker);
    });
  };
  seasonSelect.addEventListener('change', () => {
    filterGroupsForSeason();
    refreshPickers();
  });
  groupSelect.addEventListener('change', refreshPickers);
  filterGroupsForSeason();
  document.addEventListener('click', (event) => {
    pickers.forEach((picker) => {
      if (!picker.element.contains(event.target)) closePicker(picker);
    });
  });
  document.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') pickers.forEach((picker) => closePicker(picker));
  });
});

document.querySelectorAll('[data-fixture-generator]').forEach((form) => {
  const season = form.querySelector('[data-fixture-season]');
  const start = form.querySelector('[data-fixture-start]');
  const weekday = form.querySelector('[data-fixture-weekday]');
  const weekdays = ['Nedelja', 'Ponedeljek', 'Torek', 'Sreda', 'Četrtek', 'Petek', 'Sobota'];
  const updateWeekday = () => {
    const value = start.value ? new Date(`${start.value}T12:00:00`) : null;
    weekday.textContent = value && !Number.isNaN(value.getTime()) ? weekdays[value.getDay()] : '—';
  };
  season.addEventListener('change', () => {
    window.location.assign(`${window.location.pathname}?season_id=${encodeURIComponent(season.value)}`);
  });
  start.addEventListener('change', updateWeekday);
  updateWeekday();

  form.querySelectorAll('.fixture-league-row.has-existing').forEach((row) => {
    const group = row.querySelector('input[name="group_ids"]');
    const replace = row.querySelector('input[name="replace_unplayed_group_ids"]');
    if (!group || !replace) return;
    replace.addEventListener('change', () => { if (replace.checked) group.checked = true; });
    group.addEventListener('change', () => { if (!group.checked) replace.checked = false; });
  });
});

document.querySelectorAll('[data-fixture-preview]').forEach((form) => {
  const payloadField = form.querySelector('[data-schedule-payload]');
  const payload = JSON.parse(payloadField.value);
  const groupById = new Map(payload.groups.map((group) => [String(group.group_id), group]));

  form.querySelectorAll('[data-fixture-tab]').forEach((tab) => {
    tab.addEventListener('click', () => {
      form.querySelectorAll('[data-fixture-tab]').forEach((item) => item.classList.toggle('is-active', item === tab));
      form.querySelectorAll('[data-fixture-group]').forEach((group) => group.classList.toggle('is-active', group.dataset.fixtureGroup === tab.dataset.fixtureTab));
    });
  });

  const syncGroup = (groupElement) => {
    const group = groupById.get(groupElement.dataset.fixtureGroup);
    const names = new Map(group.players.map((player) => [String(player.id), player.name]));
    group.rounds = [...groupElement.querySelectorAll('[data-fixture-round]')].map((roundElement) => ({
      round_number: Number(roundElement.dataset.roundNumber),
      leg: Number(roundElement.dataset.leg),
      date: roundElement.querySelector('[data-round-date]').value,
      matches: [...roundElement.querySelectorAll('[data-fixture-match]')].map((matchElement) => ({
        home_player_id: Number(matchElement.dataset.homeId),
        guest_player_id: Number(matchElement.dataset.guestId),
        home_name: names.get(matchElement.dataset.homeId),
        guest_name: names.get(matchElement.dataset.guestId),
        scheduled_at: matchElement.querySelector('[data-match-time]').value,
      })),
    }));

    const playerIds = group.players.map((player) => Number(player.id));
    const expectedPairs = playerIds.length * (playerIds.length - 1) / 2;
    const unordered = new Map();
    const ordered = new Map();
    const homes = new Map(playerIds.map((id) => [id, [0, 0]]));
    const guests = new Map(playerIds.map((id) => [id, [0, 0]]));
    let noSelf = true;
    let onePerRound = true;
    group.rounds.forEach((round) => {
      const seen = new Map();
      round.matches.forEach((match) => {
        noSelf = noSelf && match.home_player_id !== match.guest_player_id;
        [match.home_player_id, match.guest_player_id].forEach((id) => seen.set(id, (seen.get(id) || 0) + 1));
        const pair = [match.home_player_id, match.guest_player_id].sort((a, b) => a - b).join(':');
        const direction = `${match.home_player_id}:${match.guest_player_id}`;
        unordered.set(pair, (unordered.get(pair) || 0) + 1);
        ordered.set(direction, (ordered.get(direction) || 0) + 1);
        if (homes.has(match.home_player_id) && round.leg >= 1 && round.leg <= 2) homes.get(match.home_player_id)[round.leg - 1] += 1;
        if (guests.has(match.guest_player_id) && round.leg >= 1 && round.leg <= 2) guests.get(match.guest_player_id)[round.leg - 1] += 1;
      });
      if ([...seen.values()].some((count) => count > 1)) onePerRound = false;
    });
    const pairsTwice = unordered.size === expectedPairs && [...unordered.entries()].every(([pair, count]) => {
      const [first, second] = pair.split(':');
      return count === 2 && ordered.get(`${first}:${second}`) === 1 && ordered.get(`${second}:${first}`) === 1;
    });
    const balanced = playerIds.every((id) => {
      const home = homes.get(id); const guest = guests.get(id);
      return Math.abs(home[0] - guest[0]) <= 1 && Math.abs(home[1] - guest[1]) <= 1
        && home[0] + home[1] === guest[0] + guest[1];
    });
    const checks = { pairs_twice: pairsTwice, balanced, no_self_play: noSelf, one_match_per_round: onePerRound };
    Object.entries(checks).forEach(([name, valid]) => {
      const item = groupElement.querySelector(`[data-check="${name}"]`);
      item.classList.toggle('is-valid', valid);
      item.classList.toggle('is-warning', !valid && name !== 'no_self_play');
      item.classList.toggle('is-invalid', !valid && name === 'no_self_play');
    });
    payloadField.value = JSON.stringify(payload);
  };

  form.querySelectorAll('[data-fixture-group]').forEach((groupElement) => {
    groupElement.querySelectorAll('[data-fixture-match]').forEach((matchElement) => {
      matchElement.querySelector('[data-swap-fixture]').addEventListener('click', () => {
        [matchElement.dataset.homeId, matchElement.dataset.guestId] = [matchElement.dataset.guestId, matchElement.dataset.homeId];
        const home = matchElement.querySelector('[data-home-name]');
        const guest = matchElement.querySelector('[data-guest-name]');
        [home.textContent, guest.textContent] = [guest.textContent, home.textContent];
        syncGroup(groupElement);
      });
      matchElement.querySelector('[data-delete-fixture]').addEventListener('click', () => {
        matchElement.remove();
        syncGroup(groupElement);
      });
      matchElement.querySelector('[data-match-time]').addEventListener('change', () => syncGroup(groupElement));
    });
    groupElement.querySelectorAll('[data-round-date]').forEach((input) => {
      input.addEventListener('change', () => {
        input.closest('[data-fixture-round]').querySelectorAll('[data-match-time]').forEach((matchTime) => {
          const timeValue = matchTime.value.includes('T') ? matchTime.value.split('T')[1] : '18:00';
          matchTime.value = `${input.value}T${timeValue}`;
        });
        syncGroup(groupElement);
      });
    });
    syncGroup(groupElement);
  });
  form.addEventListener('submit', () => form.querySelectorAll('[data-fixture-group]').forEach(syncGroup));
});

