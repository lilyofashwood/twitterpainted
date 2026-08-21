const panels = {
  encode: document.getElementById('encode-panel'),
  decode: document.getElementById('decode-panel'),
};

const modeButtons = document.querySelectorAll('.mode-btn');
const toolStatusEl = document.getElementById('tool-status-list');
const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const ALLOWED_IMAGE_TYPES = new Set(['image/png', 'image/jpeg']);
const ALLOWED_IMAGE_EXTS = ['.png', '.jpg', '.jpeg'];
const ENCODE_METHOD_STORAGE_KEY = 'twitterpaintedEncodeMethod:v3';
const TWITTERPAINT_PATH_STORAGE_KEY = 'twitterpaintedPath:v1';
const TWITTERPAINT_CHANNEL_STORAGE_KEY = 'twitterpaintedChannels:v1';
const CARRIER_PREP_LAB_STORAGE_KEY = 'twitterpaintedCarrierPrepLab:v1';
const CARRIER_PREP_TWITTER_STORAGE_KEY = 'twitterpaintedCarrierPrepTwitter:v1';
const ANALYSIS_PROFILE_STORAGE_KEY = 'analysisProfile:v2';

const decodeOptionPriority = [
  'auto_detect',
  'lsb',
  'pvd',
  'dct',
  'f5',
  'spread_spectrum',
  'palette',
  'chroma',
  'png_chunks',
];

const restOrder = [
  'advanced_lsb',
  'simple_lsb',
  'simple_zlib',
  'stegg',
  'zero_width',
  'invisible_unicode',
  'randomizer_decode',
  'payload_unwrap',
  'xor_flag_sweep',
  'pre_analysis',
  'binwalk',
  'foremost',
  'exiftool',
  'steghide',
  'outguess',
  'zsteg',
  'decomposer',
  'plane_carver',
  'entropy_analyzer',
  'jpeg_qtable_analyzer',
  'statistical_steg',
  'identify',
  'convert',
  'jpeginfo',
  'jpegtran',
  'cjpeg',
  'djpeg',
  'jpegsnoop',
  'jhead',
  'exiv2',
  'exifprobe',
  'pngcheck',
  'optipng',
  'pngcrush',
  'pngtools',
  'stegdetect',
  'jsteg',
  'stegbreak',
  'stegseek',
  'stegcracker',
  'fcrackzip',
  'bulk_extractor',
  'scalpel',
  'testdisk',
  'photorec',
  'stegoveritas',
  'zbarimg',
  'qrencode',
  'tesseract',
  'ffprobe',
  'ffmpeg',
  'mediainfo',
  'sox',
  'pdfinfo',
  'pdftotext',
  'pdfimages',
  'qpdf',
  'radare2',
  'rizin',
  'hexyl',
  'bvi',
  'xxd',
  'rg',
  'tshark',
  'wireshark',
  'sleuthkit',
  'volatility',
  'stegsolve',
  'stegosuite',
  'stegpy',
  'stegolsb',
  'lsbsteg',
  'stegano_lsb',
  'stegano_lsb_set',
  'stegano_red',
  'cloackedpixel',
  'cloackedpixel_analyse',
  'jphide',
  'jphs',
  'jpseek',
  'stegsnow',
  'hideme',
  'mp3stego_encode',
  'mp3stego_decode',
  'openpuff',
  'deepsound',
  'sonic_visualiser',
  'stegify',
  'openstego',
];

const profileState = {
  profiles: [],
  byId: {},
  defaultProfile: 'light',
  tools: {},
  analyzers: [],
  analyzerById: {},
  defaultSelectedTools: [],
  selectedToolsByProfile: {},
  advancedOptionsByProfile: {},
  infoMode: false,
};

const unicode_lower = {
  a: '𝐚',
  b: '𝖻',
  c: '𝖼',
  d: '𝖽',
  e: '𝐞',
  f: '𝖿',
  g: '𝗀',
  h: '𝗁',
  i: '𝐢',
  j: '𝗃',
  k: '𝗄',
  l: '𝗅',
  m: '𝗆',
  n: '𝗇',
  o: '𝐨',
  p: '𝗉',
  q: '𝗊',
  r: '𝗋',
  s: '𝗌',
  t: '𝗍',
  u: '𝐮',
  v: '𝗏',
  w: '𝗐',
  x: '𝗑',
  y: '𝗒',
  z: '𝗓',
};

function stylizeUi(text) {
  return String(text ?? '')
    .toLowerCase()
    .replace(/[a-z]/g, (ch) => unicode_lower[ch] || ch);
}

function escapeHtml(value) {
  return String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function hasSupportedExtension(name) {
  const lower = (name || '').toLowerCase();
  return ALLOWED_IMAGE_EXTS.some((ext) => lower.endsWith(ext));
}

function isSupportedImage(file) {
  if (!file) return false;
  const mime = String(file.type || '').toLowerCase();
  return ALLOWED_IMAGE_TYPES.has(mime) || hasSupportedExtension(file.name);
}

function validateImageFile(file) {
  if (!file) return stylizeUi('please choose an image to upload.');
  if (!isSupportedImage(file)) return stylizeUi('unsupported image type. please use png or jpg.');
  if (file.size > MAX_IMAGE_BYTES) return stylizeUi(`image too large. try under ${(MAX_IMAGE_BYTES / 1024).toFixed(0)} kb.`);
  return null;
}

function validateAnalysisFile(file) {
  if (!file) return stylizeUi('please choose a carrier to analyze.');
  if (file.size > MAX_IMAGE_BYTES) return stylizeUi(`carrier too large. try under ${(MAX_IMAGE_BYTES / 1024).toFixed(0)} kb.`);
  return null;
}

function formatFileSize(bytes) {
  const kb = bytes / 1024;
  if (kb < 1024) return `${kb.toFixed(1)} kb`;
  return `${(kb / 1024).toFixed(2)} mb (${kb.toFixed(0)} kb)`;
}

function formatDurationMs(ms) {
  const totalSec = Math.max(0, Math.round(Number(ms || 0) / 1000));
  const mins = Math.floor(totalSec / 60);
  const secs = totalSec % 60;
  if (!mins) return `${secs}s`;
  return `${mins}m ${secs.toString().padStart(2, '0')}s`;
}

function formatClock(seconds) {
  const mins = Math.floor(seconds / 60).toString().padStart(2, '0');
  const secs = Math.floor(seconds % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
}

async function readResponse(res) {
  const text = await res.text();
  if (!text) return { data: null, text: '' };
  try {
    return { data: JSON.parse(text), text };
  } catch (_) {
    return { data: null, text };
  }
}

function responseMessage(res, data, text) {
  const status = `${res.status}${res.statusText ? ` ${res.statusText}` : ''}`;
  if (data && data.error) return stylizeUi(`server response (${status}): ${data.error}`);
  if (text) return stylizeUi(`server response (${status}): ${text.replace(/\s+/g, ' ').slice(0, 180)}`);
  return stylizeUi(`server response (${status})`);
}

function showPanel(targetId, persist = true) {
  if (persist && targetId) localStorage.setItem('activePanel', targetId);
  modeButtons.forEach((btn) => btn.classList.remove('active'));

  Object.entries(panels).forEach(([key, panel]) => {
    if (!panel) return;
    const id = `${key}-panel`;
    const active = id === targetId;
    panel.classList.toggle('active', active);
    const tab = document.querySelector(`.mode-btn[data-target="${id}"]`);
    if (tab) tab.classList.toggle('active', active);
    if (active && id === 'decode-panel') {
      loadProfilesAndTools();
    }
  });
}

modeButtons.forEach((btn) => {
  btn.addEventListener('click', () => showPanel(btn.dataset.target, true));
});

showPanel('encode-panel', false);

const encodeMethodSelect = document.getElementById('encode-method');
const carrierPrepSelect = document.getElementById('carrier-prep');
const carrierPrepHint = document.getElementById('carrier-prep-hint');
const simplePlaneField = document.getElementById('simple-plane-field');
const twitterpaintField = document.getElementById('twitterpaint-field');
const twitterpaintModeRadios = document.querySelectorAll('input[name="twitterpaintMode"]');
const twitterpaintCombinedPanel = document.getElementById('twitterpaint-combined-panel');
const twitterpaintIndividualPanel = document.getElementById('twitterpaint-individual-panel');
const twitterpaintCombinedText = document.getElementById('twitterpaint-combined-text');
const jpegFormatRadio = document.querySelector('input[name="outputFormat"][value="jpeg"]');
const pngFormatRadio = document.querySelector('input[name="outputFormat"][value="png"]');
const outputFormatHint = document.getElementById('output-format-hint');
const methodPanels = document.querySelectorAll('[data-encode-method]');
const methodOptionsField = document.getElementById('encode-method-options');
const payloadModeRadios = document.querySelectorAll('input[name="payloadMode"]');
const payloadTextPanel = document.getElementById('payload-text-panel');
const payloadFilePanel = document.getElementById('payload-file-panel');
const payloadFileInput = document.getElementById('payload-file-input');
const payloadFileName = document.getElementById('payload-file-name');
const payloadTextArea = document.querySelector('#payload-text-panel textarea[name="text"]');

const carrierPrepDescriptions = {
  twitterpaint: 'feed armor input: fit within 680px and prepare metadata-free opaque rgb png under 900 kib.',
  none: 'leave the body: do not resize or pre-convert the carrier; geometry and alpha reach the encoder as intact as that method allows.',
  legacy: 'blunt axe: optimize as png, then halve both dimensions until the carrier falls under 900 kib.',
  gentle: 'velvet knife: proportional fit within 1600px, preserve alpha, and save as lossless png.',
  compact: 'tiny coffin: proportional fit within 512px, flatten to metadata-free opaque rgb, and optimize as png.',
};

function carrierPrepStorageKey(method) {
  return method === 'twitterpaint'
    ? CARRIER_PREP_TWITTER_STORAGE_KEY
    : CARRIER_PREP_LAB_STORAGE_KEY;
}

function updateCarrierPrepHint() {
  if (!carrierPrepSelect || !carrierPrepHint) return;
  const method = encodeMethodSelect ? encodeMethodSelect.value : 'twitterpaint';
  let description = carrierPrepDescriptions[carrierPrepSelect.value]
    || carrierPrepDescriptions.none;
  if (carrierPrepSelect.value === 'twitterpaint') {
    description = method === 'twitterpaint'
      ? 'feed armor: fit within 680px and prepare metadata-free opaque rgb png input. twitterpaint mode also checks the final survivor profile.'
      : 'feed armor input: 680px max edge, metadata-free opaque rgb png, under 900 kib. final format and verification still belong to the chosen encoder.';
  }
  carrierPrepHint.textContent = stylizeUi(description);
}

function syncCarrierPrepForMethod(method) {
  if (!carrierPrepSelect) return;
  const fallback = method === 'twitterpaint' ? 'twitterpaint' : 'none';
  const saved = localStorage.getItem(carrierPrepStorageKey(method));
  const known = Array.from(carrierPrepSelect.options)
    .some((option) => option.value === saved);
  carrierPrepSelect.value = known ? saved : fallback;
  updateCarrierPrepHint();
}

function syncOutputFormatForMethod(method) {
  if (!jpegFormatRadio || !pngFormatRadio) return;
  const pngOnly = ['lsb', 'pvd', 'palette', 'chroma', 'png_chunks'];
  const jpegOnly = ['f5', 'dct'];
  const force = pngOnly.includes(method) ? 'png' : (jpegOnly.includes(method) ? 'jpeg' : '');

  jpegFormatRadio.disabled = force === 'png';
  pngFormatRadio.disabled = force === 'jpeg';

  if (!force) {
    if (outputFormatHint) {
      if (method === 'twitterpaint' || method === 'simple_lsb' || method === 'advanced_lsb') {
        const jpegSelected = jpegFormatRadio.checked;
        const twitterPrep = carrierPrepSelect && carrierPrepSelect.value === 'twitterpaint';
        const verifiedTwitterpaint = method === 'twitterpaint' && twitterPrep;
        outputFormatHint.textContent = stylizeUi(jpegSelected
          ? (method === 'twitterpaint'
            ? 'experimental jpeg q95 / 4:4:4: recompression is likely to erase pixel lsb data. the exported file will be decoded immediately and reported as pass or fail.'
            : 'experimental jpeg q95 / 4:4:4: recompression is likely to erase pixel lsb data. this encoder does not issue twitterpaint survivor status.')
          : (verifiedTwitterpaint
            ? 'png is the intended x / twitter route. twitterpaint prep makes it opaque rgb, 680px max edge, under 900 kib, and exact-self-checked.'
            : (twitterPrep
              ? 'twitterpaint prep hardens the input; this encoder keeps its own output rules and does not issue survivor status.'
              : 'local lsb export only: choose twitterpaint mode plus feed armor to issue survivor status.')));
      } else {
        outputFormatHint.textContent = stylizeUi('spread spectrum can write png or jpeg; choose either output.');
      }
    }
    return;
  }
  if (force === 'png') {
    pngFormatRadio.checked = true;
    if (outputFormatHint) {
      outputFormatHint.textContent = stylizeUi(`${method.replaceAll('_', ' ')} writes png only in this build; jpeg is unavailable.`);
    }
  } else {
    jpegFormatRadio.checked = true;
    if (outputFormatHint) {
      outputFormatHint.textContent = stylizeUi(`${method} writes a jpeg frequency-domain carrier; png is unavailable.`);
    }
  }
}

function getPayloadMode() {
  const selected = document.querySelector('input[name="payloadMode"]:checked');
  return selected ? selected.value : 'text';
}

function setPayloadModeUI() {
  const mode = getPayloadMode();
  const useFile = mode === 'file';
  const active = !encodeMethodSelect || encodeMethodSelect.value !== 'twitterpaint';
  if (payloadTextPanel) payloadTextPanel.classList.toggle('hidden', useFile);
  if (payloadFilePanel) payloadFilePanel.classList.toggle('hidden', !useFile);
  payloadModeRadios.forEach((radio) => { radio.disabled = !active; });
  if (payloadTextArea) payloadTextArea.disabled = !active || useFile;
  if (payloadFileInput) payloadFileInput.disabled = !active || !useFile;
}

function getTwitterpaintMode() {
  const selected = document.querySelector('input[name="twitterpaintMode"]:checked');
  return selected ? selected.value : 'combined';
}

function setTwitterpaintModeUI() {
  const active = !encodeMethodSelect || encodeMethodSelect.value === 'twitterpaint';
  const individual = getTwitterpaintMode() === 'individual';
  twitterpaintModeRadios.forEach((radio) => { radio.disabled = !active; });
  if (twitterpaintCombinedPanel) twitterpaintCombinedPanel.classList.toggle('hidden', individual);
  if (twitterpaintIndividualPanel) twitterpaintIndividualPanel.classList.toggle('hidden', !individual);
  if (twitterpaintCombinedText) twitterpaintCombinedText.disabled = !active || individual;
  document.querySelectorAll('[data-twitterpaint-channel]').forEach((card) => {
    const enabled = card.querySelector('.twitterpaint-channel-enabled');
    const textField = card.querySelector('.twitterpaint-channel-text');
    if (enabled) enabled.disabled = !active || !individual;
    if (textField) textField.disabled = !active || !individual || !enabled || !enabled.checked;
  });
  if (active) localStorage.setItem(TWITTERPAINT_PATH_STORAGE_KEY, getTwitterpaintMode());
}

function setEncodeMethodUI() {
  const method = encodeMethodSelect ? encodeMethodSelect.value : 'twitterpaint';
  const isTwitterpaint = method === 'twitterpaint';
  if (twitterpaintField) twitterpaintField.style.display = isTwitterpaint ? 'flex' : 'none';
  if (simplePlaneField) simplePlaneField.style.display = isTwitterpaint ? 'none' : 'flex';

  let hasActivePanel = false;
  methodPanels.forEach((panel) => {
    const active = panel.dataset.encodeMethod === method;
    panel.classList.toggle('hidden', !active);
    panel.querySelectorAll('input, select, textarea').forEach((el) => {
      el.disabled = !active;
    });
    if (active) hasActivePanel = true;
  });

  if (methodOptionsField) methodOptionsField.style.display = hasActivePanel ? 'flex' : 'none';
  syncCarrierPrepForMethod(method);
  syncOutputFormatForMethod(method);
  setPayloadModeUI();
  setTwitterpaintModeUI();
  localStorage.setItem(ENCODE_METHOD_STORAGE_KEY, method);
}

if (encodeMethodSelect) {
  // v3 intentionally starts existing installations on the Twitterpaint default.
  // Once chosen in this version, a user's real method preference persists.
  const savedMethod = localStorage.getItem(ENCODE_METHOD_STORAGE_KEY);
  const knownMethod = Array.from(encodeMethodSelect.options)
    .some((option) => option.value === savedMethod);
  if (savedMethod && knownMethod) encodeMethodSelect.value = savedMethod;
  encodeMethodSelect.addEventListener('change', setEncodeMethodUI);
}
if (carrierPrepSelect) {
  carrierPrepSelect.addEventListener('change', () => {
    const method = encodeMethodSelect ? encodeMethodSelect.value : 'twitterpaint';
    localStorage.setItem(carrierPrepStorageKey(method), carrierPrepSelect.value);
    updateCarrierPrepHint();
    syncOutputFormatForMethod(method);
  });
}
payloadModeRadios.forEach((radio) => radio.addEventListener('change', setPayloadModeUI));
const savedTwitterpaintPath = localStorage.getItem(TWITTERPAINT_PATH_STORAGE_KEY);
if (['combined', 'individual'].includes(savedTwitterpaintPath)) {
  const savedRadio = document.querySelector(`input[name="twitterpaintMode"][value="${savedTwitterpaintPath}"]`);
  if (savedRadio) savedRadio.checked = true;
}
twitterpaintModeRadios.forEach((radio) => radio.addEventListener('change', setTwitterpaintModeUI));
[pngFormatRadio, jpegFormatRadio].forEach((radio) => {
  if (radio) radio.addEventListener('change', () => syncOutputFormatForMethod(encodeMethodSelect ? encodeMethodSelect.value : 'twitterpaint'));
});
setEncodeMethodUI();

const carrierInput = document.getElementById('carrier-image');
const carrierFilename = document.getElementById('carrier-filename');
const analyzeInput = document.getElementById('analyze-image');
const analyzeFilename = document.getElementById('analyze-filename');

function bindFileLabel(inputEl, labelEl, emptyLabel) {
  if (!inputEl || !labelEl) return;
  const update = () => {
    const file = inputEl.files && inputEl.files[0] ? inputEl.files[0] : null;
    const name = file ? `${file.name} (${formatFileSize(file.size)})` : stylizeUi(emptyLabel);
    labelEl.textContent = name;
  };
  inputEl.addEventListener('change', update);
  update();
}

bindFileLabel(carrierInput, carrierFilename, 'no photo chosen');
bindFileLabel(analyzeInput, analyzeFilename, 'no carrier chosen');
bindFileLabel(payloadFileInput, payloadFileName, 'no file');

function toggleTwitterpaintChannelBodies() {
  document.querySelectorAll('[data-twitterpaint-channel]').forEach((card) => {
    const enabledToggle = card.querySelector('.twitterpaint-channel-enabled');
    if (!enabledToggle) return;
    card.classList.toggle('channel-collapsed', !enabledToggle.checked);
  });
  setTwitterpaintModeUI();
}

function saveTwitterpaintChannelState() {
  const state = {};
  document.querySelectorAll('[data-twitterpaint-channel]').forEach((card) => {
    const ch = card.dataset.twitterpaintChannel;
    const enabledToggle = card.querySelector('.twitterpaint-channel-enabled');
    const textField = card.querySelector('.twitterpaint-channel-text');
    if (!enabledToggle || !textField) return;
    state[ch] = { enabled: enabledToggle.checked, text: textField.value };
  });
  localStorage.setItem(TWITTERPAINT_CHANNEL_STORAGE_KEY, JSON.stringify(state));
}

function loadTwitterpaintChannelState() {
  const saved = localStorage.getItem(TWITTERPAINT_CHANNEL_STORAGE_KEY);
  if (!saved) return;
  try {
    const state = JSON.parse(saved);
    document.querySelectorAll('[data-twitterpaint-channel]').forEach((card) => {
      const ch = card.dataset.twitterpaintChannel;
      const cfg = state[ch];
      if (!cfg) return;
      const enabledToggle = card.querySelector('.twitterpaint-channel-enabled');
      const textField = card.querySelector('.twitterpaint-channel-text');
      if (enabledToggle) enabledToggle.checked = !!cfg.enabled;
      if (textField) textField.value = cfg.text || '';
    });
  } catch (_) {
    /* ignore */
  }
}

document.querySelectorAll('[data-twitterpaint-channel]').forEach((card) => {
  const enabled = card.querySelector('.twitterpaint-channel-enabled');
  const textArea = card.querySelector('.twitterpaint-channel-text');
  if (enabled) {
    enabled.addEventListener('change', () => {
      toggleTwitterpaintChannelBodies();
      saveTwitterpaintChannelState();
    });
  }
  if (textArea) textArea.addEventListener('input', saveTwitterpaintChannelState);
});

loadTwitterpaintChannelState();
toggleTwitterpaintChannelBodies();

const encodeForm = document.getElementById('encode-form');
const encodeOutput = document.getElementById('encode-output');

function renderEncodeResult(data) {
  const verification = data && data.verification ? data.verification : null;
  const verificationHtml = verification
    ? `<div class="status-line verification-${verification.status === 'passed' ? 'passed' : 'failed'}">${escapeHtml(stylizeUi(verification.message || `export self-check ${verification.status}`))}</div>`
    : '';
  encodeOutput.innerHTML = `
    <div class="result-grid">
      <div class="result-card">
        <h3>${escapeHtml(stylizeUi('encoded image'))}</h3>
        <img src="${data.data_url}" alt="encoded" style="width:100%;border-radius:10px;border:1px solid rgba(255,255,255,0.1);background:rgba(255,255,255,0.02);">
        ${verificationHtml}
        <div class="downloads" style="margin-top:10px;">
          <a href="${data.data_url}" download="${escapeHtml(data.filename)}">${escapeHtml(stylizeUi(`download ${data.filename}`))}</a>
        </div>
      </div>
    </div>
  `;
}

if (encodeForm) {
  encodeForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const carrierFile = carrierInput && carrierInput.files ? carrierInput.files[0] : null;
    const carrierError = validateImageFile(carrierFile);
    if (carrierError) {
      encodeOutput.innerHTML = `<div class="status-line error">${escapeHtml(carrierError)}</div>`;
      return;
    }

    encodeOutput.innerHTML = `<div class="status-line">${escapeHtml(stylizeUi('encoding…'))}</div>`;

    const encodeMethod = encodeMethodSelect ? encodeMethodSelect.value : 'twitterpaint';
    const payloadMode = getPayloadMode();
    const payloadFile = payloadFileInput && payloadFileInput.files ? payloadFileInput.files[0] : null;
    const payloadText = payloadTextArea ? payloadTextArea.value.trim() : '';

    if (encodeMethod !== 'twitterpaint') {
      if (payloadMode === 'file' && !payloadFile) {
        encodeOutput.innerHTML = `<div class="status-line error">${escapeHtml(stylizeUi('choose a payload file first.'))}</div>`;
        return;
      }
      if (payloadMode === 'text' && !payloadText) {
        encodeOutput.innerHTML = `<div class="status-line error">${escapeHtml(stylizeUi('enter a payload message first.'))}</div>`;
        return;
      }
    }

    const fd = new FormData(encodeForm);
    fd.set('encodeMethod', encodeMethod);

    try {
      if (encodeMethod === 'twitterpaint') {
        const twitterpaintMode = getTwitterpaintMode();
        fd.set('twitterpaintMode', twitterpaintMode);
        if (twitterpaintMode === 'combined') {
          const text = twitterpaintCombinedText ? twitterpaintCombinedText.value.trim() : '';
          if (!text) {
            throw new Error('enter a combined rgb message first.');
          }
          fd.set('twitterpaintText', text);
        } else {
          let enabledCount = 0;
          const channels = {};
          document.querySelectorAll('[data-twitterpaint-channel]').forEach((card) => {
            const ch = card.dataset.twitterpaintChannel;
            const enabledToggle = card.querySelector('.twitterpaint-channel-enabled');
            const textField = card.querySelector('.twitterpaint-channel-text');
            if (!ch || !enabledToggle || !textField) return;
            const enabled = enabledToggle.checked;
            const text = textField.value.trim();
            channels[ch] = { enabled, type: 'text', text };
            if (enabled) enabledCount += 1;
          });
          if (!enabledCount) {
            throw new Error('choose at least one individual r, g, or b channel.');
          }
          const emptyChannel = Object.entries(channels)
            .find(([, config]) => config.enabled && !config.text);
          if (emptyChannel) {
            throw new Error(`enter a message for the enabled ${emptyChannel[0]} channel.`);
          }
          fd.set('channels', JSON.stringify(channels));
        }
      } else if (encodeMethod === 'advanced_lsb') {
        const channels = {};
        fd.set('channels', JSON.stringify(channels));
      } else if (encodeMethod === 'simple_lsb') {
        fd.set('mode', payloadMode === 'file' ? 'zlib' : 'text');
      }

      const res = await fetch('/api/encode', { method: 'POST', body: fd });
      const { data, text } = await readResponse(res);
      if (!res.ok) throw new Error(responseMessage(res, data, text));
      if (!data) throw new Error(responseMessage(res, data, text));
      if (data.error) throw new Error(data.error);
      renderEncodeResult(data);
    } catch (err) {
      encodeOutput.innerHTML = `<div class="status-line error">${escapeHtml(stylizeUi(err.message || String(err)))}</div>`;
    }
  });
}

const decodeForm = document.getElementById('decode-form');
const decodeOutput = document.getElementById('decode-output');
const analysisProfileSelect = document.getElementById('analysis-profile');
const profileDescriptionEl = document.getElementById('profile-description');
const analysisEtaEl = document.getElementById('analysis-eta');
const analysisToolsEl = document.getElementById('analysis-active-tools');
const analysisTimerEl = document.getElementById('analysis-timer');
const analyzerGridEl = document.getElementById('analyzer-grid');
const selectedToolsInputEl = document.getElementById('selected-tools-input');
const selectAllToolsBtn = document.getElementById('select-all-tools');
const selectNoToolsBtn = document.getElementById('select-no-tools');
const selectProfileToolsBtn = document.getElementById('select-profile-tools');
const toggleAnalyzerInfoBtn = document.getElementById('toggle-analyzer-info');

const spreadToggle = document.querySelector('input[name="spreadSpectrum"]');
const binwalkToggle = document.querySelector('input[name="binwalkExtract"]');
const unicodeToggle = document.querySelector('input[name="unicodeSweep"]');
const unicodeTier1Toggle = document.querySelector('input[name="unicodeTier1"]');
const unicodeSeparatorsToggle = document.querySelector('input[name="unicodeSeparators"]');
const unicodeAggressivenessSelect = document.querySelector('select[name="unicodeAggressiveness"]');
const unicodeOptions = document.getElementById('unicode-options');
const ADVANCED_OPTIONS_STORAGE_PREFIX = 'analysisAdvancedOptions:v2:';

const ADVANCED_OPTION_ANALYZERS = {
  spreadSpectrum: ['spread_spectrum'],
  binwalkExtract: ['binwalk'],
  unicodeSweep: ['invisible_unicode', 'invisible_unicode_decode'],
  unicodeTier1: ['invisible_unicode'],
  unicodeSeparators: ['invisible_unicode'],
  unicodeAggressiveness: ['invisible_unicode', 'invisible_unicode_decode'],
};

const advancedOptionDefaults = {
  light:    { spread: false, binwalk: false, unicode: false, tier1: false, separators: false, aggressiveness: 'low' },
  quick:    { spread: false, binwalk: false, unicode: false, tier1: false, separators: false, aggressiveness: 'low' },
  balanced: { spread: false, binwalk: false, unicode: false, tier1: false, separators: false, aggressiveness: 'low' },
  deep:     { spread: true,  binwalk: true,  unicode: false, tier1: false, separators: false, aggressiveness: 'balanced' },
  forensic: { spread: true,  binwalk: true,  unicode: true,  tier1: true,  separators: true,  aggressiveness: 'high' },
};

function advancedOptionsStorageKey(profileId) {
  return `${ADVANCED_OPTIONS_STORAGE_PREFIX}${profileId}`;
}

function normalizeAdvancedOptions(value, defaults) {
  const source = value && typeof value === 'object' ? value : {};
  const aggressiveness = ['low', 'balanced', 'high'].includes(source.aggressiveness)
    ? source.aggressiveness
    : defaults.aggressiveness;
  return {
    spread: typeof source.spread === 'boolean' ? source.spread : defaults.spread,
    binwalk: typeof source.binwalk === 'boolean' ? source.binwalk : defaults.binwalk,
    unicode: typeof source.unicode === 'boolean' ? source.unicode : defaults.unicode,
    tier1: typeof source.tier1 === 'boolean' ? source.tier1 : defaults.tier1,
    separators: typeof source.separators === 'boolean' ? source.separators : defaults.separators,
    aggressiveness,
  };
}

function readAdvancedOptionsFromUi() {
  return {
    spread: !!spreadToggle?.checked,
    binwalk: !!binwalkToggle?.checked,
    unicode: !!unicodeToggle?.checked,
    tier1: !!unicodeTier1Toggle?.checked,
    separators: !!unicodeSeparatorsToggle?.checked,
    aggressiveness: unicodeAggressivenessSelect?.value || 'low',
  };
}

function applyAdvancedOptionsToUi(state) {
  if (spreadToggle) spreadToggle.checked = state.spread;
  if (binwalkToggle) binwalkToggle.checked = state.binwalk;
  if (unicodeToggle) unicodeToggle.checked = state.unicode;
  if (unicodeTier1Toggle) unicodeTier1Toggle.checked = state.tier1;
  if (unicodeSeparatorsToggle) unicodeSeparatorsToggle.checked = state.separators;
  if (unicodeAggressivenessSelect) unicodeAggressivenessSelect.value = state.aggressiveness;
}

function persistAdvancedOptions(profileId = selectedProfileId()) {
  const state = readAdvancedOptionsFromUi();
  profileState.advancedOptionsByProfile[profileId] = state;
  localStorage.setItem(advancedOptionsStorageKey(profileId), JSON.stringify(state));
  return state;
}

function selectedAnalyzerSet(profileId = selectedProfileId()) {
  return loadSelectedToolsForProfile(profileId);
}

function syncUnicodeOptions() {
  if (!unicodeOptions) return;
  const selected = selectedAnalyzerSet();
  const analyzerSelected = selected.has('invisible_unicode') || selected.has('invisible_unicode_decode');
  const visible = !!unicodeToggle?.checked || analyzerSelected;
  unicodeOptions.classList.toggle('visible', visible);
  unicodeOptions.querySelectorAll('input, select').forEach((element) => {
    element.disabled = !visible;
  });
}

function syncRelevantAdvancedOptions() {
  const selected = selectedAnalyzerSet();
  document.querySelectorAll('[data-analyzer-option-for]').forEach((row) => {
    const analyzerIds = String(row.dataset.analyzerOptionFor || '').split(/\s+/).filter(Boolean);
    row.classList.toggle('analyzer-selected', analyzerIds.some((id) => selected.has(id)));
  });
  syncUnicodeOptions();
}

function turnOffOrphanedAdvancedOptions(selected) {
  let changed = false;
  if (spreadToggle?.checked && !selected.has('spread_spectrum')) {
    spreadToggle.checked = false;
    changed = true;
  }
  if (binwalkToggle?.checked && !selected.has('binwalk')) {
    binwalkToggle.checked = false;
    changed = true;
  }
  const unicodeSelected = selected.has('invisible_unicode') || selected.has('invisible_unicode_decode');
  if (unicodeToggle?.checked && !unicodeSelected) {
    unicodeToggle.checked = false;
    changed = true;
  }
  if (unicodeTier1Toggle?.checked && !selected.has('invisible_unicode')) {
    unicodeTier1Toggle.checked = false;
    changed = true;
  }
  if (unicodeSeparatorsToggle?.checked && !selected.has('invisible_unicode')) {
    unicodeSeparatorsToggle.checked = false;
    changed = true;
  }
  if (changed) persistAdvancedOptions();
  syncRelevantAdvancedOptions();
}

function ensureAnalyzersSelected(analyzerIds) {
  const profileId = selectedProfileId();
  const selected = selectedAnalyzerSet(profileId);
  let changed = false;
  analyzerIds.forEach((id) => {
    if (!profileState.analyzerById[id] || selected.has(id)) return;
    selected.add(id);
    changed = true;
  });
  if (!changed) return false;
  persistSelectedToolsForProfile(profileId, selected);
  renderAnalyzerSelector(profileId);
  syncProfileUI();
  return true;
}

function enabledAdvancedAnalyzerIds() {
  const ids = [];
  if (spreadToggle?.checked) ids.push(...ADVANCED_OPTION_ANALYZERS.spreadSpectrum);
  if (binwalkToggle?.checked) ids.push(...ADVANCED_OPTION_ANALYZERS.binwalkExtract);
  if (unicodeToggle?.checked) ids.push(...ADVANCED_OPTION_ANALYZERS.unicodeSweep);
  if (unicodeTier1Toggle?.checked) ids.push(...ADVANCED_OPTION_ANALYZERS.unicodeTier1);
  if (unicodeSeparatorsToggle?.checked) ids.push(...ADVANCED_OPTION_ANALYZERS.unicodeSeparators);
  return Array.from(new Set(ids));
}

function syncAdvancedOptions(profileId) {
  const defaults = advancedOptionDefaults[profileId] || advancedOptionDefaults.light;
  let state = profileState.advancedOptionsByProfile[profileId];
  if (!state) {
    try {
      state = normalizeAdvancedOptions(
        JSON.parse(localStorage.getItem(advancedOptionsStorageKey(profileId)) || 'null'),
        defaults
      );
    } catch {
      state = normalizeAdvancedOptions(null, defaults);
    }
    profileState.advancedOptionsByProfile[profileId] = state;
    localStorage.setItem(advancedOptionsStorageKey(profileId), JSON.stringify(state));
  }
  applyAdvancedOptionsToUi(state);
  ensureAnalyzersSelected(enabledAdvancedAnalyzerIds());
  syncRelevantAdvancedOptions();
}

function handleAdvancedOptionChange(event) {
  const control = event.currentTarget;
  if (!(control instanceof HTMLInputElement) && !(control instanceof HTMLSelectElement)) return;
  persistAdvancedOptions();

  const analyzerIds = ADVANCED_OPTION_ANALYZERS[control.name] || [];
  const activatesAnalyzer = control instanceof HTMLSelectElement || control.checked;
  if (activatesAnalyzer) ensureAnalyzersSelected(analyzerIds);
  syncRelevantAdvancedOptions();
}

[
  spreadToggle,
  binwalkToggle,
  unicodeToggle,
  unicodeTier1Toggle,
  unicodeSeparatorsToggle,
  unicodeAggressivenessSelect,
].forEach((control) => {
  if (control) control.addEventListener('change', handleAdvancedOptionChange);
});

function startLiveTimer(prefix) {
  if (!analysisTimerEl) return () => '00:00';
  const started = Date.now();
  analysisTimerEl.textContent = `${prefix} · 00:00`;
  const timerId = setInterval(() => {
    const elapsedSec = (Date.now() - started) / 1000;
    analysisTimerEl.textContent = `${prefix} · ${formatClock(elapsedSec)}`;
  }, 1000);

  return (finalStatus = 'complete') => {
    clearInterval(timerId);
    const elapsedSec = (Date.now() - started) / 1000;
    analysisTimerEl.textContent = `${finalStatus} · ${formatClock(elapsedSec)}`;
    return elapsedSec;
  };
}

async function loadProfilesAndTools() {
  try {
    const [profileRes, toolsRes] = await Promise.all([
      fetch('/api/profiles'),
      fetch('/api/tools'),
    ]);
    const profileData = await profileRes.json();
    const toolsData = await toolsRes.json();

    const profiles = Array.isArray(profileData.profiles) ? profileData.profiles : [];
    profileState.profiles = profiles;
    profileState.byId = Object.fromEntries(profiles.map((row) => [row.id, row]));
    const serverDefault = profileData.default_profile || 'light';
    profileState.defaultProfile = profileState.byId.light ? 'light' : serverDefault;
    profileState.tools = toolsData.tools || {};
    profileState.analyzers = Array.isArray(profileData.analyzers) ? profileData.analyzers : [];
    profileState.analyzerById = Object.fromEntries(
      profileState.analyzers.map((row) => [row.id, row])
    );
    profileState.defaultSelectedTools = Array.isArray(profileData.default_selected_tools)
      ? profileData.default_selected_tools
      : [];

    if (analysisProfileSelect) {
      const currentSaved = localStorage.getItem(ANALYSIS_PROFILE_STORAGE_KEY);
      const legacySaved = localStorage.getItem('analysisProfile');
      const migratedSaved = (currentSaved || legacySaved) === 'simple'
        ? 'light'
        : (currentSaved || legacySaved);
      const saved = migratedSaved || profileState.defaultProfile;
      analysisProfileSelect.value = profileState.byId[saved] ? saved : profileState.defaultProfile;
    }

    const initialProfile = selectedProfileId();
    await loadAnalyzerCatalog(initialProfile);
    syncProfileUI();
    syncAdvancedOptions(initialProfile);
  } catch {
    if (toolStatusEl) toolStatusEl.innerHTML = `<div class="status-line">${stylizeUi('tool status unavailable')}</div>`;
    if (profileDescriptionEl) profileDescriptionEl.textContent = stylizeUi('unable to load analysis profiles.');
  }
}

function selectedProfileId() {
  if (!analysisProfileSelect) return profileState.defaultProfile;
  return analysisProfileSelect.value || profileState.defaultProfile;
}

function selectedToolsStorageKey(profileId) {
  return `selectedAnalyzers:v2:${profileId}`;
}

const ANALYZER_CATEGORY_ORDER = [
  'guided inspection',
  'carrier inspection',
  'learned and research steganalysis',
  'pixel and bit planes',
  'pixel and frequency',
  'frequency domain',
  'metadata and structure',
  'payload recovery',
  'text and transforms',
  'text and unicode',
  'audio and media',
  'audio',
  'image inspection',
  'brute force and recovery',
  'media and documents',
  'binary and forensic inspection',
  'specialist steganography',
  'classic steg tools',
  'external tools',
  'other analyzers',
];

const ANALYZER_CATEGORY_HINTS = {
  'guided inspection': 'fast triage and carrier-aware suggestions for where to look next',
  'carrier inspection': 'format, metadata, entropy, and structural clues before extraction',
  'learned and research steganalysis': 'optional model-backed and research methods with explicit runtime and license boundaries',
  'pixel and bit planes': 'least-significant bits, channel planes, and visual plane decomposition',
  'pixel and frequency': 'bit planes, color channels, quantization, and carrier-aware decoders',
  'frequency domain': 'jpeg coefficients, quantization, and frequency-domain payloads',
  'metadata and structure': 'file signatures, metadata, entropy, and embedded carrier structure',
  'payload recovery': 'carving, wrapper removal, nested files, and obfuscation recovery',
  'text and transforms': 'hidden text, unicode signals, wrappers, ciphers, and transformations',
  'text and unicode': 'hidden characters, lookalikes, whitespace, and text-layer signals',
  'audio and media': 'audio samples, color channels, spectra, and other media signals',
  audio: 'sample bits, echoes, spectra, and frequency-domain signals',
  'image inspection': 'format-specific image validation, metadata, and visual inspection tools',
  'brute force and recovery': 'password search, signature carving, and file recovery tools',
  'media and documents': 'audio, video, document, and container inspection tools',
  'binary and forensic inspection': 'binary structure, packet, disk, and memory inspection tools',
  'specialist steganography': 'format-specific and standalone steganography commands',
  'classic steg tools': 'password-aware and command-line steganography probes',
  'external tools': 'command-line analyzers that run when selected and installed',
  'other analyzers': 'additional specialized inspection and recovery passes',
};

function analyzerCategory(tool) {
  const explicit = String(tool.category || tool.group || '').trim().toLowerCase();
  if (explicit && explicit !== 'general') return explicit;

  const id = String(tool.id || '').toLowerCase();
  if (id.startsWith('audio_')) return 'audio';
  if (['pre_analysis', 'exiftool', 'strings', 'entropy_analyzer', 'jpeg_qtable_analyzer', 'statistical_steg'].includes(id)) {
    return 'carrier inspection';
  }
  if (['simple_lsb', 'advanced_lsb', 'simple_zlib', 'decode_options', 'decomposer', 'plane_carver', 'zsteg'].includes(id)) {
    return 'pixel and frequency';
  }
  if (['randomizer_decode', 'payload_unwrap', 'xor_flag_sweep', 'binwalk', 'foremost', 'matryoshka'].includes(id)) {
    return 'payload recovery';
  }
  if (['zero_width', 'invisible_unicode', 'invisible_unicode_decode', 'homoglyph', 'whitespace_steg'].includes(id)) {
    return 'text and unicode';
  }
  if (['steghide', 'outguess', 'stegg', 'tool_suite', 'channel_cipher'].includes(id)) {
    return 'classic steg tools';
  }
  return 'other analyzers';
}

function analyzerCategoryRank(category) {
  const index = ANALYZER_CATEGORY_ORDER.indexOf(category);
  return index < 0 ? ANALYZER_CATEGORY_ORDER.length : index;
}

function analyzerIsSuggested(tool) {
  if (typeof tool.recommended_in_profile === 'boolean') return tool.recommended_in_profile;
  return !!tool.enabled_in_profile;
}

function readableCatalogValue(value) {
  if (Array.isArray(value)) return value.map((item) => String(item)).join(', ');
  if (value && typeof value === 'object') {
    return Object.entries(value).map(([key, item]) => `${key}: ${item}`).join(', ');
  }
  return String(value || '').trim();
}

function analyzerRequirement(tool) {
  const explicit = readableCatalogValue(tool.requirements || tool.requires || tool.requirement);
  if (explicit) return explicit;

  const id = String(tool.id || '').toLowerCase();
  const kind = String(tool.kind || 'internal').toLowerCase();
  if (kind !== 'external') return 'built into twitterpainted; no external command required';
  if (id === 'tool_suite') return 'coordinates the command-line tools detected in this runtime';

  const status = profileState.tools[id];
  if (status?.available && status.path) return `external command detected at ${status.path}`;
  if (status && !status.available) return 'external command not detected in this runtime';
  return 'uses an external command-line tool when it is available';
}

function analyzerCost(tool) {
  const explicit = readableCatalogValue(tool.cost_label || tool.cost);
  if (explicit) return explicit;
  if (tool.eta_label) return `estimated runtime ${tool.eta_label}`;
  if (Number(tool.eta_seconds) > 0) return `estimated runtime ~${tool.eta_seconds}s`;
  return 'runtime estimate unavailable';
}

function analyzerOperation(tool) {
  const explicit = readableCatalogValue(tool.operation || tool.role);
  if (explicit) return explicit;
  return String(tool.kind || '').toLowerCase() === 'external' ? 'carrier cli' : 'decode or inspect';
}

function analyzerApplicability(tool) {
  const explicit = readableCatalogValue(
    tool.applicability || tool.input_types || tool.formats || tool.supported_formats
  );
  if (explicit) return explicit;

  const id = String(tool.id || '').toLowerCase();
  const category = analyzerCategory(tool);
  if (id.startsWith('audio_')) return 'audio carriers: wav, flac, ogg, aiff, aif, au, or raw';
  if (['pixel and bit planes', 'pixel and frequency', 'frequency domain', 'image inspection'].includes(category)) {
    return 'image carriers; format-specific tools report skipped when the format does not match';
  }
  if (category === 'media and documents') return 'media or document carriers, depending on the selected command';
  if (category === 'binary and forensic inspection') return 'binary, packet, disk, or memory-oriented carriers';
  return 'carrier-dependent; incompatible analyzers report skipped instead of locking the control';
}

function analyzerAvailability(tool) {
  const id = String(tool.id || '').toLowerCase();
  const kind = String(tool.kind || 'internal').toLowerCase();
  if (kind !== 'external') return { label: 'built in', className: 'built-in' };
  const status = profileState.tools[id];
  if (!status) return { label: 'external', className: 'external' };
  return status.available
    ? { label: 'detected', className: 'detected' }
    : { label: 'not detected', className: 'not-detected' };
}

function analyzerDomId(value) {
  return String(value || 'analyzer').toLowerCase().replace(/[^a-z0-9_-]+/g, '-');
}

function safeExternalUrl(value) {
  try {
    const parsed = new URL(String(value || '').trim(), window.location.origin);
    return ['http:', 'https:'].includes(parsed.protocol) ? parsed.href : '';
  } catch {
    return '';
  }
}

function loadSelectedToolsForProfile(profileId) {
  if (profileState.selectedToolsByProfile[profileId]) {
    return new Set(profileState.selectedToolsByProfile[profileId]);
  }

  const analyzerIds = new Set(
    profileState.analyzers
      .map((row) => row.id)
  );
  const fallback = profileId === 'light' && analyzerIds.has('simple_lsb')
    ? ['simple_lsb']
    : (Array.isArray(profileState.defaultSelectedTools)
      ? profileState.defaultSelectedTools
      : Array.from(analyzerIds));

  const savedRaw = localStorage.getItem(selectedToolsStorageKey(profileId));
  if (!savedRaw) {
    const initial = fallback.filter((id) => analyzerIds.has(id));
    profileState.selectedToolsByProfile[profileId] = initial;
    return new Set(initial);
  }

  try {
    const parsed = JSON.parse(savedRaw);
    if (!Array.isArray(parsed)) throw new Error('invalid selection');
    const normalized = parsed.map((item) => String(item || '').toLowerCase()).filter((id) => analyzerIds.has(id));
    profileState.selectedToolsByProfile[profileId] = normalized;
    return new Set(normalized);
  } catch {
    const initial = fallback.filter((id) => analyzerIds.has(id));
    profileState.selectedToolsByProfile[profileId] = initial;
    return new Set(initial);
  }
}

function persistSelectedToolsForProfile(profileId, selectedSet) {
  const values = Array.from(selectedSet).sort();
  profileState.selectedToolsByProfile[profileId] = values;
  localStorage.setItem(selectedToolsStorageKey(profileId), JSON.stringify(values));
  if (selectedToolsInputEl) {
    selectedToolsInputEl.value = JSON.stringify(values);
  }
}

function selectedAnalyzerIds(profileId) {
  return Array.from(loadSelectedToolsForProfile(profileId)).sort();
}

function renderAnalyzerSelector(profileId) {
  if (!analyzerGridEl) return;
  const selectedSet = loadSelectedToolsForProfile(profileId);
  const profile = profileState.byId[profileId] || { label: profileId };
  const grouped = new Map();

  profileState.analyzers.forEach((tool) => {
    const category = analyzerCategory(tool);
    if (!grouped.has(category)) grouped.set(category, []);
    grouped.get(category).push(tool);
  });

  const groups = Array.from(grouped.entries()).sort(([left], [right]) => {
    const rankDiff = analyzerCategoryRank(left) - analyzerCategoryRank(right);
    return rankDiff || left.localeCompare(right);
  });

  const html = groups.map(([category, tools]) => {
    const categoryId = `analyzer-category-${analyzerDomId(category)}`;
    const sortedTools = [...tools].sort((left, right) => {
      const suggestionDiff = Number(analyzerIsSuggested(right)) - Number(analyzerIsSuggested(left));
      const leftLabel = String(left.label || left.id || '');
      const rightLabel = String(right.label || right.id || '');
      return suggestionDiff || leftLabel.localeCompare(rightLabel);
    });
    const cards = sortedTools.map((tool) => {
      const id = String(tool.id || '').toLowerCase();
      const label = String(tool.label || id);
      const description = String(tool.help || tool.description || 'no description supplied');
      const suggested = analyzerIsSuggested(tool);
      const checked = selectedSet.has(id);
      const availability = analyzerAvailability(tool);
      const operation = analyzerOperation(tool);
      const inputId = `analyzer-${analyzerDomId(id)}`;
      const detailId = `${inputId}-details`;
      const infoExpanded = profileState.infoMode;
      const infoLabel = `${infoExpanded ? 'hide' : 'show'} details for ${label}`.toLowerCase();
      const suggestionText = suggested
        ? `suggested by ${profile.label || profileId}`
        : `optional in ${profile.label || profileId}; still selectable`;
      const sourceUrl = safeExternalUrl(tool.source_url);
      const licenseUrl = safeExternalUrl(tool.license_url);
      const licenseName = readableCatalogValue(tool.license) || 'license terms';
      const sourceRow = sourceUrl
        ? `<div><dt>${escapeHtml(stylizeUi('source'))}</dt><dd><a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHtml(`open upstream source for ${label}`.toLowerCase())}">${escapeHtml(stylizeUi('upstream source'))}</a></dd></div>`
        : '';
      const licenseRow = licenseUrl
        ? `<div><dt>${escapeHtml(stylizeUi('license'))}</dt><dd><a href="${escapeHtml(licenseUrl)}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHtml(`open license terms for ${label}`.toLowerCase())}">${escapeHtml(stylizeUi(licenseName))}</a></dd></div>`
        : (tool.license
          ? `<div><dt>${escapeHtml(stylizeUi('license'))}</dt><dd>${escapeHtml(stylizeUi(licenseName))}</dd></div>`
          : '');
      return `
        <article class="analyzer-pill ${suggested ? 'recommended' : ''}" title="${escapeHtml(description.toLowerCase())}">
          <div class="analyzer-choice-row">
            <label class="analyzer-choice" for="${escapeHtml(inputId)}">
              <input id="${escapeHtml(inputId)}" type="checkbox" class="analyzer-checkbox" value="${escapeHtml(id)}" ${checked ? 'checked' : ''}>
              <span class="analyzer-meta">
                <span class="analyzer-name">${escapeHtml(stylizeUi(label))}</span>
                <span class="analyzer-badges">
                  ${suggested ? `<span class="analyzer-badge suggested">${escapeHtml(stylizeUi('suggested'))}</span>` : ''}
                  <span class="analyzer-badge ${escapeHtml(availability.className)}">${escapeHtml(stylizeUi(availability.label))}</span>
                  <span class="analyzer-badge operation ${escapeHtml(analyzerDomId(operation))}">${escapeHtml(stylizeUi(operation))}</span>
                  <span class="analyzer-badge eta">${escapeHtml(stylizeUi(tool.eta_label || 'eta unknown'))}</span>
                </span>
              </span>
            </label>
            <button type="button" class="analyzer-info-button" data-analyzer-label="${escapeHtml(label.toLowerCase())}" aria-expanded="${String(infoExpanded)}" aria-controls="${escapeHtml(detailId)}" aria-label="${escapeHtml(infoLabel)}">ⓘ</button>
          </div>
          <div class="analyzer-explainer" id="${escapeHtml(detailId)}" role="region" aria-label="${escapeHtml(`information about ${label}`.toLowerCase())}" aria-hidden="${String(!infoExpanded)}">
            <p>${escapeHtml(stylizeUi(description))}</p>
            <dl class="analyzer-info-grid">
              <div><dt>${escapeHtml(stylizeUi('category'))}</dt><dd>${escapeHtml(stylizeUi(category))}</dd></div>
              <div><dt>${escapeHtml(stylizeUi('requirements'))}</dt><dd>${escapeHtml(stylizeUi(analyzerRequirement(tool)))}</dd></div>
              <div><dt>${escapeHtml(stylizeUi('works with'))}</dt><dd>${escapeHtml(stylizeUi(analyzerApplicability(tool)))}</dd></div>
              <div><dt>${escapeHtml(stylizeUi('operation'))}</dt><dd>${escapeHtml(stylizeUi(operation))}</dd></div>
              <div><dt>${escapeHtml(stylizeUi('cost'))}</dt><dd>${escapeHtml(stylizeUi(analyzerCost(tool)))}</dd></div>
              ${sourceRow}
              ${licenseRow}
              <div><dt>${escapeHtml(stylizeUi('profile'))}</dt><dd>${escapeHtml(stylizeUi(suggestionText))}</dd></div>
            </dl>
          </div>
        </article>
      `;
    }).join('');
    const hint = ANALYZER_CATEGORY_HINTS[category] || 'related analysis methods and recovery tools';
    return `
      <section class="analyzer-group" aria-labelledby="${escapeHtml(categoryId)}">
        <div class="analyzer-group-head">
          <div>
            <h3 id="${escapeHtml(categoryId)}">${escapeHtml(stylizeUi(category))}</h3>
            <p>${escapeHtml(stylizeUi(hint))}</p>
          </div>
          <span>${escapeHtml(stylizeUi(`${tools.length} ${tools.length === 1 ? 'analyzer' : 'analyzers'}`))}</span>
        </div>
        <div class="analyzer-group-grid">${cards}</div>
      </section>
    `;
  }).join('');

  analyzerGridEl.innerHTML = html || `<div class="status-line">${escapeHtml(stylizeUi('no analyzers available'))}</div>`;
  analyzerGridEl.classList.toggle('info-visible', profileState.infoMode);
  syncAllAnalyzerInfoAria();
  persistSelectedToolsForProfile(profileId, selectedSet);
}

async function loadAnalyzerCatalog(profileId) {
  try {
    const res = await fetch(`/api/analyzers?profile=${encodeURIComponent(profileId)}`);
    const data = await res.json();
    profileState.analyzers = Array.isArray(data.analyzers) ? data.analyzers : [];
    profileState.analyzerById = Object.fromEntries(
      profileState.analyzers.map((row) => [row.id, row])
    );
    profileState.defaultSelectedTools = Array.isArray(data.default_selected_tools)
      ? data.default_selected_tools
      : [];
    renderAnalyzerSelector(profileId);
  } catch {
    profileState.analyzers = [];
    profileState.analyzerById = {};
    profileState.defaultSelectedTools = [];
    if (analyzerGridEl) {
      analyzerGridEl.innerHTML = `<div class="status-line">${escapeHtml(stylizeUi('unable to load analyzer catalog'))}</div>`;
    }
  }
}

function syncAnalyzerCardInfoAria(card) {
  if (!(card instanceof Element)) return;
  const button = card.querySelector('.analyzer-info-button');
  const details = card.querySelector('.analyzer-explainer');
  if (!(button instanceof HTMLButtonElement) || !(details instanceof HTMLElement)) return;
  const visible = profileState.infoMode
    || card.classList.contains('info-open')
    || card.classList.contains('info-peek');
  const label = button.dataset.analyzerLabel || 'analyzer';
  button.setAttribute('aria-expanded', String(visible));
  button.setAttribute('aria-label', `${visible ? 'hide' : 'show'} details for ${label}`);
  details.setAttribute('aria-hidden', String(!visible));
}

function syncAllAnalyzerInfoAria() {
  if (!analyzerGridEl) return;
  analyzerGridEl.querySelectorAll('.analyzer-pill').forEach(syncAnalyzerCardInfoAria);
}

function setAnalyzerCardPeek(card, visible) {
  if (!(card instanceof Element)) return;
  card.classList.toggle('info-peek', visible);
  syncAnalyzerCardInfoAria(card);
}

if (analyzerGridEl) {
  analyzerGridEl.addEventListener('change', (event) => {
    const target = event.target;
    if (!(target instanceof HTMLInputElement)) return;
    if (!target.classList.contains('analyzer-checkbox')) return;
    const profileId = selectedProfileId();
    const selected = new Set();
    analyzerGridEl.querySelectorAll('input.analyzer-checkbox').forEach((checkbox) => {
      if (!(checkbox instanceof HTMLInputElement)) return;
      if (!checkbox.checked) return;
      selected.add(String(checkbox.value || '').toLowerCase());
    });
    persistSelectedToolsForProfile(profileId, selected);
    turnOffOrphanedAdvancedOptions(selected);
    syncProfileUI();
  });

  analyzerGridEl.addEventListener('click', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const button = target.closest('.analyzer-info-button');
    if (!(button instanceof HTMLButtonElement)) return;
    const card = button.closest('.analyzer-pill');
    if (!card) return;
    const open = !card.classList.contains('info-open');
    card.classList.toggle('info-open', open);
    syncAnalyzerCardInfoAria(card);
  });

  analyzerGridEl.addEventListener('pointerover', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const card = target.closest('.analyzer-pill');
    if (!card || (event.relatedTarget instanceof Node && card.contains(event.relatedTarget))) return;
    setAnalyzerCardPeek(card, true);
  });

  analyzerGridEl.addEventListener('pointerout', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const card = target.closest('.analyzer-pill');
    if (!card || (event.relatedTarget instanceof Node && card.contains(event.relatedTarget))) return;
    setAnalyzerCardPeek(card, false);
  });

  analyzerGridEl.addEventListener('focusin', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    setAnalyzerCardPeek(target.closest('.analyzer-pill'), true);
  });

  analyzerGridEl.addEventListener('focusout', (event) => {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const card = target.closest('.analyzer-pill');
    if (!card || (event.relatedTarget instanceof Node && card.contains(event.relatedTarget))) return;
    setAnalyzerCardPeek(card, false);
  });
}

if (selectAllToolsBtn) {
  selectAllToolsBtn.addEventListener('click', () => {
    const profileId = selectedProfileId();
    const all = new Set(
      profileState.analyzers
        .map((row) => String(row.id || '').toLowerCase())
    );
    persistSelectedToolsForProfile(profileId, all);
    turnOffOrphanedAdvancedOptions(all);
    renderAnalyzerSelector(profileId);
    syncProfileUI();
  });
}

if (selectNoToolsBtn) {
  selectNoToolsBtn.addEventListener('click', () => {
    const profileId = selectedProfileId();
    const none = new Set();
    persistSelectedToolsForProfile(profileId, none);
    turnOffOrphanedAdvancedOptions(none);
    renderAnalyzerSelector(profileId);
    syncProfileUI();
  });
}

if (selectProfileToolsBtn) {
  selectProfileToolsBtn.addEventListener('click', () => {
    const profileId = selectedProfileId();
    const recommended = new Set(
      (profileState.defaultSelectedTools || []).map((item) => String(item || '').toLowerCase())
    );
    persistSelectedToolsForProfile(profileId, recommended);
    turnOffOrphanedAdvancedOptions(recommended);
    renderAnalyzerSelector(profileId);
    syncProfileUI();
  });
}

function setAnalyzerInfoMode(enabled) {
  profileState.infoMode = !!enabled;
  if (analyzerGridEl) analyzerGridEl.classList.toggle('info-visible', profileState.infoMode);
  syncAllAnalyzerInfoAria();
  if (toggleAnalyzerInfoBtn) {
    toggleAnalyzerInfoBtn.setAttribute('aria-pressed', String(profileState.infoMode));
    toggleAnalyzerInfoBtn.textContent = stylizeUi(profileState.infoMode ? 'info on' : 'info');
    toggleAnalyzerInfoBtn.setAttribute(
      'aria-label',
      profileState.infoMode ? 'hide analyzer information' : 'show analyzer information'
    );
  }
  localStorage.setItem('twitterpaintedAnalyzerInfo', String(profileState.infoMode));
}

if (toggleAnalyzerInfoBtn) {
  toggleAnalyzerInfoBtn.addEventListener('click', () => {
    setAnalyzerInfoMode(!profileState.infoMode);
  });
  setAnalyzerInfoMode(localStorage.getItem('twitterpaintedAnalyzerInfo') === 'true');
}

function renderToolPills(profile) {
  if (!toolStatusEl) return;
  const selectedIds = new Set(selectedAnalyzerIds(profile.id));
  const selectedAnalyzers = profileState.analyzers.filter((tool) => selectedIds.has(String(tool.id || '').toLowerCase()));
  const externalAnalyzers = selectedAnalyzers.filter((tool) => String(tool.kind || '').toLowerCase() === 'external');
  const internalAnalyzers = selectedAnalyzers.filter((tool) => String(tool.kind || '').toLowerCase() !== 'external');

  const externalHtml = externalAnalyzers.map((tool) => {
    const name = String(tool.id || 'external analyzer').toLowerCase();
    const info = profileState.tools[name];
    const known = !!info;
    const ok = !!info?.available;
    const icon = known ? (ok ? '✅' : '◇') : '◇';
    const cls = ok ? 'ok' : (known ? 'missing' : 'unknown');
    const path = ok && info.path
      ? info.path
      : stylizeUi(known ? 'not detected in this runtime' : 'managed external analyzer');
    return `
      <div class="tool-pill">
        <div class="tool-top"><span class="tool-icon ${cls}">${icon}</span><span class="tool-name">${escapeHtml(stylizeUi(name))}</span></div>
        <span class="tool-path">${escapeHtml(path)}</span>
      </div>
    `;
  }).join('');

  const internalHtml = internalAnalyzers.map((tool) => {
    const name = String(tool.id || 'internal analyzer').toLowerCase();
    return `
      <div class="tool-pill">
        <div class="tool-top"><span class="tool-icon ok">✦</span><span class="tool-name">${escapeHtml(stylizeUi(name))}</span></div>
        <span class="tool-path">${escapeHtml(stylizeUi('built-in analyzer'))}</span>
      </div>
    `;
  }).join('');

  toolStatusEl.innerHTML = `${externalHtml}${internalHtml}` || `<div class="status-line">${stylizeUi('no analyzers selected')}</div>`;

  if (analysisToolsEl) {
    const selectedCount = selectedAnalyzers.length;
    const total = externalAnalyzers.length;
    const tracked = externalAnalyzers.filter((tool) => profileState.tools[String(tool.id || '').toLowerCase()]);
    const available = tracked.filter((tool) => profileState.tools[String(tool.id || '').toLowerCase()]?.available).length;
    if (!total) {
      analysisToolsEl.textContent = stylizeUi(`tools: ${selectedCount} selected · ${internalAnalyzers.length} built in`);
    } else if (!tracked.length) {
      analysisToolsEl.textContent = stylizeUi(`tools: ${selectedCount} selected · ${total} external`);
    } else {
      analysisToolsEl.textContent = stylizeUi(`tools: ${selectedCount} selected · ${available}/${tracked.length} commands detected`);
    }
  }
}

function selectedAnalyzerEtaLabel(profileId) {
  const selected = new Set(selectedAnalyzerIds(profileId));
  const seconds = profileState.analyzers.reduce((total, tool) => {
    if (!selected.has(String(tool.id || '').toLowerCase())) return total;
    return total + Math.max(0, Number(tool.eta_seconds) || 0);
  }, 0);
  if (!seconds) return '~0s';
  const minutes = Math.floor(seconds / 60);
  const remainder = seconds % 60;
  if (!minutes) return `~${remainder}s`;
  if (!remainder) return `~${minutes}m`;
  return `~${minutes}m ${remainder}s`;
}

function syncProfileUI() {
  const profile = profileState.byId[selectedProfileId()] || profileState.byId[profileState.defaultProfile];
  if (!profile) return;

  if (profileDescriptionEl) profileDescriptionEl.textContent = stylizeUi(profile.description || '');
  if (analysisEtaEl) analysisEtaEl.textContent = stylizeUi(`selected cost: ${selectedAnalyzerEtaLabel(profile.id)}`);
  renderToolPills(profile);
  localStorage.setItem(ANALYSIS_PROFILE_STORAGE_KEY, profile.id);
  if (selectedToolsInputEl) {
    selectedToolsInputEl.value = JSON.stringify(selectedAnalyzerIds(profile.id));
  }
}

if (analysisProfileSelect) {
  analysisProfileSelect.addEventListener('change', async () => {
    const profileId = selectedProfileId();
    await loadAnalyzerCatalog(profileId);
    syncProfileUI();
    syncAdvancedOptions(profileId);
  });
}

function compactLines(lines, maxLines = 40) {
  const filtered = lines.filter((line) => String(line || '').trim());
  if (filtered.length <= maxLines) return filtered;
  return [...filtered.slice(0, maxLines), `... (${filtered.length - maxLines} more lines)`];
}

function payloadBlocks(payload) {
  const blocks = [];

  if (typeof payload?.output === 'string' && payload.output.trim()) {
    blocks.push({ title: 'payload', text: payload.output.trim() });
  }

  if (Array.isArray(payload?.output)) {
    const joined = compactLines(payload.output.map((line) => String(line))).join('\n');
    if (joined.trim()) blocks.push({ title: 'payload', text: joined });
  }

  if (payload?.decoded_text && typeof payload.decoded_text === 'object') {
    const rows = Object.entries(payload.decoded_text)
      .filter(([, value]) => value)
      .map(([key, value]) => `${key}:\n${value}`);
    if (rows.length) blocks.push({ title: 'decoded text', text: rows.join('\n\n') });
  }

  if (Array.isArray(payload?.matches) && payload.matches.length) {
    const rows = payload.matches.map((item) => `${item.plane || 'plane'} (${item.strategy || 'scan'}):\n${item.preview || ''}`);
    blocks.push({ title: 'matches', text: rows.join('\n\n') });
  }

  const details = payload?.details;
  if (details && typeof details === 'object') {
    if (typeof details.preview === 'string' && details.preview.trim()) {
      blocks.push({ title: 'preview', text: details.preview.trim() });
    }

    if (Array.isArray(details.text) && details.text.length) {
      const textRows = details.text
        .map((entry) => `${entry.keyword || 'text'}: ${entry.text || ''}`)
        .filter(Boolean)
        .join('\n\n');
      if (textRows.trim()) blocks.push({ title: 'text chunks', text: textRows });
    }

    if (details.text_channels && typeof details.text_channels === 'object') {
      const rows = Object.entries(details.text_channels)
        .map(([channel, value]) => `${channel}:\n${value.text_preview || ''}`)
        .join('\n\n');
      if (rows.trim()) blocks.push({ title: 'channel text', text: rows });
    }

    if (Array.isArray(details.file_payloads) && details.file_payloads.length) {
      const rows = details.file_payloads
        .map((entry) => `${entry.channel}:\n${entry.preview || ''}`)
        .join('\n\n');
      if (rows.trim()) blocks.push({ title: 'file payloads', text: rows });
    }

    if (Array.isArray(details.candidates) && details.candidates.length) {
      const rows = details.candidates
        .slice(0, 8)
        .map((candidate, idx) => {
          const signals = Array.isArray(candidate.signals) && candidate.signals.length
            ? `\nsignals: ${candidate.signals.join(', ')}`
            : '';
          return `${idx + 1}. ${candidate.label || candidate.option_id} (${candidate.confidence})\n${candidate.summary || ''}${signals}`;
        })
        .join('\n\n');
      blocks.push({ title: 'ranked candidates', text: rows });
    }
  }

  if (!blocks.length) {
    const fallback = payload?.error || payload?.reason || payload?.summary || 'no payload detected';
    blocks.push({ title: 'result', text: String(fallback) });
  }

  const unique = [];
  const seen = new Set();
  blocks.forEach((block) => {
    const key = `${block.title}::${block.text}`;
    if (seen.has(key)) return;
    seen.add(key);
    unique.push(block);
  });
  return unique;
}

function renderMetadata(payload) {
  const copy = {};
  Object.entries(payload || {}).forEach(([key, value]) => {
    if (['output', 'decoded_text', 'matches'].includes(key)) return;
    if (key === 'details' && value && typeof value === 'object') {
      const detailCopy = { ...value };
      delete detailCopy.preview;
      delete detailCopy.text;
      delete detailCopy.text_channels;
      delete detailCopy.file_payloads;
      delete detailCopy.candidates;
      copy[key] = detailCopy;
      return;
    }
    copy[key] = value;
  });

  if (!Object.keys(copy).length) return '';
  return `
    <details class="meta-toggle">
      <summary>${escapeHtml(stylizeUi('metadata'))}</summary>
      <pre>${escapeHtml(JSON.stringify(copy, null, 2))}</pre>
    </details>
  `;
}

function renderToolCard(toolKey, payload, wide = false) {
  if (!payload || typeof payload !== 'object') return '';

  const status = String(payload.status || 'unknown').toLowerCase();
  const label = stylizeUi(payload.label || toolKey);
  const tagClass =
    status === 'ok' ? 'ok' : status === 'error' ? 'error' : status === 'no_signal' || status === 'skipped' ? 'warn' : '';

  const confidence = typeof payload.confidence === 'number' ? payload.confidence : null;
  const timing = typeof payload.timing_ms === 'number' && payload.timing_ms > 0 ? formatDurationMs(payload.timing_ms) : '';

  const blocks = payloadBlocks(payload)
    .map((block) => `
      <div class="payload-block">
        <div class="payload-title">${escapeHtml(stylizeUi(block.title))}</div>
        <pre>${escapeHtml(block.text)}</pre>
      </div>
    `)
    .join('');

  const summary = payload.summary ? `<div class="result-summary">${escapeHtml(stylizeUi(payload.summary))}</div>` : '';
  const modeBadge = payload.mode ? `<span class="tag mode ${escapeHtml(payload.mode)}">${escapeHtml(stylizeUi(payload.mode))}</span>` : '';
  const confBadge = confidence !== null ? `<span class="tag mode">${escapeHtml(stylizeUi(`conf ${confidence}`))}</span>` : '';
  const timingBadge = timing ? `<span class="tag mode">${escapeHtml(stylizeUi(timing))}</span>` : '';
  const style = wide ? 'style="grid-column: 1 / -1;"' : '';

  return `
    <div class="result-card" ${style}>
      <div class="result-card-head">
        <h3>${escapeHtml(label)}</h3>
        <div class="tag-row">
          ${modeBadge}
          ${confBadge}
          ${timingBadge}
          <span class="tag ${tagClass}">${escapeHtml(stylizeUi(status))}</span>
        </div>
      </div>
      ${summary}
      ${blocks}
      ${renderMetadata(payload)}
    </div>
  `;
}

function renderDecodeResult(data) {
  const results = data.results || {};
  const artifacts = data.artifacts || { images: [], archives: [] };
  const meta = data.meta || {};

  const planeKeys = ['simple_rgb', 'red_plane', 'green_plane', 'blue_plane', 'alpha_plane'];
  const stringsKey = 'strings';

  const cardsPlanes = planeKeys
    .filter((key) => results[key])
    .map((key) => renderToolCard(key, results[key]))
    .join('');

  const primary = ['invisible_unicode_decode', 'auto_detect']
    .filter((key) => results[key])
    .map((key) => renderToolCard(key, results[key]))
    .join('');

  const rankedKeys = (results.auto_detect?.details?.candidates || [])
    .map((candidate) => candidate.option_id)
    .filter((key, idx, arr) => key && arr.indexOf(key) === idx && results[key]);

  const topCards = rankedKeys.map((key) => renderToolCard(key, results[key])).join('');

  const otherDecode = decodeOptionPriority
    .filter((key) => key !== 'auto_detect' && results[key] && !rankedKeys.includes(key))
    .map((key) => renderToolCard(key, results[key]))
    .join('');

  const restCards = restOrder
    .filter(
      (key) =>
        results[key] &&
        !planeKeys.includes(key) &&
        !decodeOptionPriority.includes(key) &&
        key !== stringsKey &&
        key !== 'invisible_unicode_decode'
    )
    .map((key) => renderToolCard(key, results[key]))
    .join('');

  const remaining = Object.keys(results)
    .filter(
      (key) =>
        !planeKeys.includes(key) &&
        !decodeOptionPriority.includes(key) &&
        !restOrder.includes(key) &&
        key !== stringsKey &&
        key !== 'invisible_unicode_decode'
    )
    .map((key) => renderToolCard(key, results[key]))
    .join('');

  const stringsCard = results[stringsKey] ? renderToolCard(stringsKey, results[stringsKey], true) : '';

  const gallery = (artifacts.images || [])
    .map((img) => `<div><img src="${img.data_url}" alt="${escapeHtml(img.name)}"><div class="status-line">${escapeHtml(img.name)}</div></div>`)
    .join('');

  const downloads = (artifacts.archives || [])
    .map((file) => `<a href="${file.data_url}" download="${escapeHtml(file.name)}">${escapeHtml(file.name)}</a>`)
    .join('');

  const metaLine = `
    <div class="analysis-meta-line">
      <span>${escapeHtml(stylizeUi(`profile: ${meta.profile_label || meta.profile || 'n/a'}`))}</span>
      <span>${escapeHtml(stylizeUi(`elapsed: ${formatDurationMs(meta.elapsed_ms || 0)}`))}</span>
      <span>${escapeHtml(stylizeUi(`input: ${meta.input_mime || 'unknown'}`))}</span>
    </div>
  `;

  decodeOutput.innerHTML = `
    ${metaLine}
    <div class="result-grid priority-grid">${cardsPlanes}</div>
    ${primary ? `<div class="result-grid">${primary}</div>` : ''}
    ${topCards ? `<div class="result-grid">${topCards}</div>` : ''}
    ${otherDecode ? `<div class="result-grid">${otherDecode}</div>` : ''}
    ${gallery ? `<h3 class="gallery-title">${escapeHtml(stylizeUi('bit-plane gallery'))}</h3><div class="gallery">${gallery}</div>` : ''}
    <div class="result-grid">${restCards}${remaining}</div>
    ${downloads ? `<div class="downloads" style="margin-top:12px;">${downloads}</div>` : ''}
    ${stringsCard ? `<div class="result-grid strings-block">${stringsCard}</div>` : ''}
  `;
}

if (decodeForm) {
  decodeForm.addEventListener('submit', async (event) => {
    event.preventDefault();

    const analyzeFile = analyzeInput && analyzeInput.files ? analyzeInput.files[0] : null;
    const analyzeError = validateAnalysisFile(analyzeFile);
    if (analyzeError) {
      decodeOutput.innerHTML = `<div class="status-line error">${escapeHtml(stylizeUi(analyzeError))}</div>`;
      return;
    }

    const profileId = selectedProfileId();
    const fd = new FormData(decodeForm);
    fd.set('analysisProfile', profileId);
    fd.set('selectedTools', JSON.stringify(selectedAnalyzerIds(profileId)));

    showPanel('decode-panel');
    const stopTimer = startLiveTimer(stylizeUi('status: running'));
    decodeOutput.innerHTML = `<div class="status-line">${escapeHtml(stylizeUi('running analyzers…'))}</div>`;

    try {
      const res = await fetch('/api/decode', { method: 'POST', body: fd });
      const { data, text } = await readResponse(res);
      if (!res.ok) throw new Error(responseMessage(res, data, text));
      if (!data) throw new Error(responseMessage(res, data, text));
      if (data.error) throw new Error(data.error);
      renderDecodeResult(data);
      stopTimer(stylizeUi('status: complete'));
    } catch (err) {
      stopTimer(stylizeUi('status: failed'));
      decodeOutput.innerHTML = `<div class="status-line error">${escapeHtml(stylizeUi(err.message || String(err)))}</div>`;
    }
  });
}

loadProfilesAndTools();
