import {
  INDIVIDUAL_CHANNELS,
  LEGACY_DECODE_PLANES,
  MAX_EXTRACTED_BYTES,
  TWITTERPAINT_PLANES,
  analyzePlane,
  channelCapacityBytes,
  embedIndividualPlanes,
  embedPlane,
  equalBytes,
  extractPlaneBytes,
  planeCapacityBytes,
  textPayload,
  utf8Bytes,
} from './steg-core.js';

const MAX_IMAGE_BYTES = 8 * 1024 * 1024;
const TARGET_PNG_BYTES = 900 * 1024;
const TWITTER_MAX_EDGE = 680;
const TWITTER_MIN_UNIQUE_RGB = 257;
const MAX_CANVAS_EDGE = 8192;
const MAX_CANVAS_PIXELS = 32 * 1024 * 1024;
const MAX_RESIZE_ATTEMPTS = 20;
const LAST_RECEIPT_KEY = 'twitterpainted:last-raster-receipt:v1';

const unicodeLower = Object.freeze({
  a: '𝐚', b: '𝖻', c: '𝖼', d: '𝖽', e: '𝐞', f: '𝖿', g: '𝗀',
  h: '𝗁', i: '𝐢', j: '𝗃', k: '𝗄', l: '𝗅', m: '𝗆', n: '𝗇',
  o: '𝐨', p: '𝗉', q: '𝗊', r: '𝗋', s: '𝗌', t: '𝗍', u: '𝐮',
  v: '𝗏', w: '𝗐', x: '𝗑', y: '𝗒', z: '𝗓',
});

const state = {
  carrier: null,
  decodeCarrier: null,
  outputUrl: '',
};

const byId = (id) => document.getElementById(id);
const workCanvas = byId('work-canvas');
const workContext = workCanvas.getContext('2d', { willReadFrequently: true });
const encodeCanvas = document.createElement('canvas');
const encodeContext = encodeCanvas.getContext('2d', {
  alpha: false,
  willReadFrequently: true,
});

function stylizeUi(text) {
  return String(text ?? '')
    .toLowerCase()
    .replace(/[a-z]/g, (character) => unicodeLower[character] || character);
}

function stylizeStaticUi(root = document.body) {
  const skippedTags = new Set(['SCRIPT', 'STYLE', 'TEXTAREA', 'CODE', 'PRE']);
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
    acceptNode(node) {
      if (!node.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
      if (skippedTags.has(node.parentElement?.tagName)) return NodeFilter.FILTER_REJECT;
      if (node.parentElement?.closest('[data-no-stylize]')) return NodeFilter.FILTER_REJECT;
      return NodeFilter.FILTER_ACCEPT;
    },
  });
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);
  for (const node of nodes) node.nodeValue = stylizeUi(node.nodeValue);

  // Keep ARIA labels in plain language for assistive technology.
  for (const element of root.querySelectorAll('[placeholder], [title]')) {
    for (const attribute of ['placeholder', 'title']) {
      if (element.hasAttribute(attribute)) {
        element.setAttribute(attribute, stylizeUi(element.getAttribute(attribute)));
      }
    }
  }
}

function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} b`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(value < 10 * 1024 ? 1 : 0)} kib`;
  return `${(value / (1024 * 1024)).toFixed(2)} mib`;
}

function setStatus(element, message = '', kind = '') {
  element.textContent = message ? stylizeUi(message) : '';
  element.className = `status-box${message ? ' visible' : ''}${kind ? ` ${kind}` : ''}`;
}

function setBusy(button, busy, busyLabel, idleLabel) {
  button.disabled = busy;
  button.textContent = stylizeUi(busy ? busyLabel : idleLabel);
}

function makeElement(tagName, className = '', text = '') {
  const element = document.createElement(tagName);
  if (className) element.className = className;
  if (text) element.textContent = stylizeUi(text);
  return element;
}

function makeChip(text) {
  return makeElement('span', 'stat-chip', text);
}

export function rasterReceipt(pixels, width, height) {
  let hash = 0x811c9dc5;
  const mix = (value) => {
    hash ^= value & 0xff;
    hash = Math.imul(hash, 0x01000193) >>> 0;
  };
  for (const dimension of [width, height]) {
    mix(dimension);
    mix(dimension >>> 8);
    mix(dimension >>> 16);
    mix(dimension >>> 24);
  }
  for (let offset = 0; offset < pixels.length; offset += 4) {
    mix(pixels[offset]);
    mix(pixels[offset + 1]);
    mix(pixels[offset + 2]);
  }
  return `${width}x${height}-${hash.toString(16).padStart(8, '0')}`;
}

function rememberReceipt(receipt) {
  try {
    localStorage.setItem(LAST_RECEIPT_KEY, receipt);
  } catch {
    // Private browsing may disable storage; the visible filename still carries it.
  }
}

function lastReceipt() {
  try {
    return localStorage.getItem(LAST_RECEIPT_KEY) || '';
  } catch {
    return '';
  }
}

function releaseImageSource(source) {
  if (!source) return;
  if (typeof source.drawable?.close === 'function') source.drawable.close();
  if (source.objectUrl) URL.revokeObjectURL(source.objectUrl);
}

function clearEncodedOutput() {
  if (state.outputUrl) URL.revokeObjectURL(state.outputUrl);
  state.outputUrl = '';
  byId('encode-output').replaceChildren();
}

function hasPngSignature(bytes) {
  const png = [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a];
  return png.every((byte, index) => bytes[index] === byte);
}

function hasJpegSignature(bytes) {
  return bytes[0] === 0xff && bytes[1] === 0xd8 && bytes[2] === 0xff;
}

async function validateImageFile(file) {
  if (!file) throw new Error('choose a png or jpeg image first.');
  if (file.size <= 0) throw new Error('the selected image is empty.');
  if (file.size > MAX_IMAGE_BYTES) {
    throw new Error(`image too large. choose one below ${formatBytes(MAX_IMAGE_BYTES)}.`);
  }
  const signature = new Uint8Array(await file.slice(0, 12).arrayBuffer());
  if (!hasPngSignature(signature) && !hasJpegSignature(signature)) {
    throw new Error('unsupported image data. choose a real png or jpeg, regardless of filename case.');
  }
}

async function decodeDrawable(blob) {
  if (typeof createImageBitmap === 'function') {
    try {
      return { drawable: await createImageBitmap(blob), objectUrl: '' };
    } catch {
      // The image element fallback produces a clearer error on older WebKit.
    }
  }
  const objectUrl = URL.createObjectURL(blob);
  const image = new Image();
  image.decoding = 'async';
  image.src = objectUrl;
  try {
    await image.decode();
    return { drawable: image, objectUrl };
  } catch (error) {
    URL.revokeObjectURL(objectUrl);
    throw error;
  }
}

async function loadImageFile(file) {
  await validateImageFile(file);
  let decoded;
  try {
    decoded = await decodeDrawable(file);
  } catch {
    throw new Error('the browser could not decode this png or jpeg.');
  }
  const width = decoded.drawable.width || decoded.drawable.naturalWidth;
  const height = decoded.drawable.height || decoded.drawable.naturalHeight;
  if (!width || !height) {
    releaseImageSource(decoded);
    throw new Error('the carrier has invalid dimensions.');
  }
  return { ...decoded, width, height, file };
}

function fittedDimensions(width, height) {
  let scale = Math.min(1, TWITTER_MAX_EDGE / width, TWITTER_MAX_EDGE / height);
  if (width * height * scale * scale > MAX_CANVAS_PIXELS) {
    scale = Math.min(scale, Math.sqrt(MAX_CANVAS_PIXELS / (width * height)));
  }
  return {
    width: Math.max(1, Math.floor(width * scale)),
    height: Math.max(1, Math.floor(height * scale)),
  };
}

function assertNativeCanvasSize(source) {
  if (
    source.width > MAX_CANVAS_EDGE
    || source.height > MAX_CANVAS_EDGE
    || source.width * source.height > MAX_CANVAS_PIXELS
  ) {
    throw new Error('this image is too large to decode safely in the browser demo. use the full lab.');
  }
}

function drawSource(source, width, height) {
  workCanvas.width = width;
  workCanvas.height = height;
  workContext.clearRect(0, 0, width, height);
  workContext.drawImage(source.drawable, 0, 0, width, height);
  return workContext.getImageData(0, 0, width, height);
}

function drawOpaqueSource(source, width, height) {
  encodeCanvas.width = width;
  encodeCanvas.height = height;
  encodeContext.fillStyle = '#000000';
  encodeContext.fillRect(0, 0, width, height);
  encodeContext.drawImage(source.drawable, 0, 0, width, height);
  return encodeContext.getImageData(0, 0, width, height);
}

function canvasPngBlob() {
  return new Promise((resolve, reject) => {
    // Canvas serialization is browser-dependent; stripAncillaryPngChunks
    // removes EXIF, color-profile, comment, and other metadata afterward.
    encodeCanvas.toBlob((blob) => {
      if (!blob) {
        reject(new Error('the browser could not export the painted png.'));
      } else if (blob.type !== 'image/png') {
        reject(new Error('this browser did not produce a real png file.'));
      } else {
        resolve(blob);
      }
    }, 'image/png');
  });
}

async function stripAncillaryPngChunks(blob) {
  const bytes = new Uint8Array(await blob.arrayBuffer());
  if (!hasPngSignature(bytes)) throw new Error('the browser returned a malformed png export.');

  const kept = [bytes.slice(0, 8)];
  let cursor = 8;
  let foundIend = false;
  while (cursor + 12 <= bytes.length) {
    const length = new DataView(bytes.buffer, bytes.byteOffset + cursor, 4).getUint32(0);
    const end = cursor + 12 + length;
    if (end > bytes.length) throw new Error('the browser returned a truncated png export.');
    const type = String.fromCharCode(...bytes.subarray(cursor + 4, cursor + 8));
    // Preserve every critical chunk byte-for-byte; discard metadata and other
    // ancillary chunks. This matches the old Pillow encoder's clean output.
    if (/^[A-Z]/.test(type)) kept.push(bytes.slice(cursor, end));
    cursor = end;
    if (type === 'IEND') {
      foundIend = true;
      break;
    }
  }
  if (!foundIend) throw new Error('the browser returned a png without an end marker.');
  return new Blob(kept, { type: 'image/png' });
}

async function pngHeader(blob) {
  const header = new Uint8Array(await blob.slice(0, 26).arrayBuffer());
  const ihdr = String.fromCharCode(...header.slice(12, 16));
  if (!hasPngSignature(header) || ihdr !== 'IHDR') {
    throw new Error('the browser returned a malformed png export.');
  }
  return { bitDepth: header[24], colorType: header[25] };
}

function countUniqueRgb(pixels, stopAt = TWITTER_MIN_UNIQUE_RGB) {
  const colors = new Set();
  for (let offset = 0; offset < pixels.length; offset += 4) {
    colors.add((pixels[offset] << 16) | (pixels[offset + 1] << 8) | pixels[offset + 2]);
    if (colors.size >= stopAt) break;
  }
  return colors.size;
}

function pixelsAreOpaque(pixels) {
  for (let offset = 3; offset < pixels.length; offset += 4) {
    if (pixels[offset] !== 255) return false;
  }
  return true;
}

async function blobPixels(blob) {
  let decoded;
  try {
    decoded = await decodeDrawable(blob);
    const width = decoded.drawable.width || decoded.drawable.naturalWidth;
    const height = decoded.drawable.height || decoded.drawable.naturalHeight;
    workCanvas.width = width;
    workCanvas.height = height;
    workContext.clearRect(0, 0, width, height);
    workContext.drawImage(decoded.drawable, 0, 0);
    return {
      width,
      height,
      pixels: workContext.getImageData(0, 0, width, height).data,
    };
  } finally {
    releaseImageSource(decoded);
  }
}

function renderSourceStats(source, targetId) {
  const target = byId(targetId);
  target.replaceChildren(
    makeChip(`${source.width} × ${source.height} px`),
    makeChip(formatBytes(source.file.size)),
    makeChip(source.file.type || 'verified image'),
  );
}

function selectedPaintStyle() {
  return document.querySelector('input[name="paint-style"]:checked')?.value || 'combined';
}

function refreshCapacity() {
  const source = state.carrier;
  const combinedLine = byId('combined-capacity');
  if (!source) {
    combinedLine.textContent = stylizeUi('choose a carrier to reveal capacity');
    for (const line of document.querySelectorAll('.channel-capacity')) {
      line.textContent = stylizeUi('choose a carrier to reveal capacity');
    }
    return;
  }

  const fitted = fittedDimensions(source.width, source.height);
  const combinedBytes = Math.min(
    planeCapacityBytes(fitted.width, fitted.height, 'RGB'),
    MAX_EXTRACTED_BYTES,
  );
  const combinedUsed = utf8Bytes(byId('combined-text').value).byteLength + 1;
  combinedLine.textContent = stylizeUi(
    `capacity ${formatBytes(combinedBytes)} · selected ${formatBytes(combinedUsed)}`,
  );

  const channelBytes = Math.min(
    channelCapacityBytes(fitted.width, fitted.height),
    MAX_EXTRACTED_BYTES,
  );
  for (const card of document.querySelectorAll('.channel-card')) {
    const used = utf8Bytes(card.querySelector('.channel-text').value).byteLength + 1;
    card.querySelector('.channel-capacity').textContent = stylizeUi(
      `capacity ${formatBytes(channelBytes)} · selected ${formatBytes(used)}`,
    );
  }
}

function syncPaintStyle() {
  const individual = selectedPaintStyle() === 'individual';
  byId('combined-options').classList.toggle('hidden', individual);
  byId('individual-options').classList.toggle('hidden', !individual);
}

function syncChannelCard(card) {
  const enabled = card.querySelector('.channel-enabled').checked;
  card.classList.toggle('enabled', enabled);
  card.querySelector('.channel-text').disabled = !enabled;
}

function collectCombinedPayload() {
  const text = byId('combined-text').value;
  const payload = textPayload(text);
  if (payload.byteLength > MAX_EXTRACTED_BYTES) {
    throw new Error(`text exceeds the ${formatBytes(MAX_EXTRACTED_BYTES)} decoder window.`);
  }
  return { payload, text };
}

function collectIndividualPayloads() {
  const payloads = {};
  const texts = {};
  for (const card of document.querySelectorAll('.channel-card')) {
    if (!card.querySelector('.channel-enabled').checked) continue;
    const channel = card.dataset.channel;
    try {
      payloads[channel] = textPayload(card.querySelector('.channel-text').value);
    } catch {
      throw new Error(`${channel.toLowerCase()} is enabled but its hidden text is empty.`);
    }
    if (payloads[channel].byteLength > MAX_EXTRACTED_BYTES) {
      throw new Error(`${channel.toLowerCase()} text exceeds the ${formatBytes(MAX_EXTRACTED_BYTES)} decoder window.`);
    }
    texts[channel] = card.querySelector('.channel-text').value;
  }
  if (!Object.keys(payloads).length) {
    throw new Error('enable at least one individual rgb plane.');
  }
  return { payloads, texts };
}

function paintPixels(imageData, width, height, style, hidden) {
  if (style === 'combined') {
    return embedPlane(imageData.data, width, height, 'RGB', hidden.payload);
  }
  return embedIndividualPlanes(imageData.data, width, height, hidden.payloads);
}

async function encodeCarrier(source, style, hidden) {
  let { width, height } = fittedDimensions(source.width, source.height);

  for (let attempt = 0; attempt < MAX_RESIZE_ATTEMPTS; attempt += 1) {
    const imageData = drawOpaqueSource(source, width, height);
    let painted;
    try {
      painted = paintPixels(imageData, width, height, style, hidden);
    } catch (error) {
      if (error instanceof RangeError) {
        throw new Error('the hidden text cannot fit after the twitter-safe resize. use shorter text or a larger carrier.');
      }
      throw error;
    }
    imageData.data.set(painted);
    encodeContext.putImageData(imageData, 0, 0);

    const blob = await stripAncillaryPngChunks(await canvasPngBlob());
    if (blob.size <= TARGET_PNG_BYTES) {
      return { blob, width, height };
    }

    const ratio = Math.min(0.94, Math.sqrt(TARGET_PNG_BYTES / blob.size) * 0.96);
    const nextWidth = Math.max(1, Math.floor(width * ratio));
    const nextHeight = Math.max(1, Math.floor(height * ratio));
    if (nextWidth === width && nextHeight === height) break;
    width = nextWidth;
    height = nextHeight;
  }

  throw new Error('the carrier could not reach the twitter-safe 900 kib ceiling without losing payload capacity. choose shorter text or a simpler image.');
}

async function verifyEncodedBlob(blob, style, hidden) {
  const decoded = await blobPixels(blob);
  const header = await pngHeader(blob);
  const failedPlanes = [];
  const profileErrors = [];

  if (blob.size > TARGET_PNG_BYTES) profileErrors.push('the png is above 900 kib');
  if (Math.max(decoded.width, decoded.height) > TWITTER_MAX_EDGE) {
    profileErrors.push('the png is above 680 px on its longest edge');
  }
  const truecolorHeader = header.bitDepth === 8 && [2, 6].includes(header.colorType);
  if (!truecolorHeader || !pixelsAreOpaque(decoded.pixels)) {
    profileErrors.push('the browser did not export an opaque 8-bit truecolor png');
  }

  const uniqueRgbColors = countUniqueRgb(decoded.pixels);
  if (uniqueRgbColors < TWITTER_MIN_UNIQUE_RGB) {
    profileErrors.push(
      `this carrier resolves to only ${uniqueRgbColors} unique rgb colors; choose a photographic carrier with more than 256 colors so twitter cannot palette-optimize it`,
    );
  }

  if (style === 'combined') {
    const recovered = extractPlaneBytes(
      decoded.pixels,
      decoded.width,
      decoded.height,
      'RGB',
      hidden.payload.byteLength,
    );
    if (!equalBytes(recovered, hidden.payload)) failedPlanes.push('combined rgb');
  } else {
    for (const channel of INDIVIDUAL_CHANNELS) {
      const expected = hidden.payloads[channel];
      if (!expected) continue;
      const recovered = extractPlaneBytes(
        decoded.pixels,
        decoded.width,
        decoded.height,
        channel,
        expected.byteLength,
      );
      if (!equalBytes(recovered, expected)) failedPlanes.push(channel.toLowerCase());
    }
  }

  return {
    passed: failedPlanes.length === 0 && profileErrors.length === 0,
    failedPlanes,
    profileErrors,
    uniqueRgbColors,
    receipt: rasterReceipt(decoded.pixels, decoded.width, decoded.height),
  };
}

function renderEncodedOutput(encoded, style, verification) {
  clearEncodedOutput();
  state.outputUrl = URL.createObjectURL(encoded.blob);

  const card = makeElement('article', 'result-card encoded-result');
  const heading = makeElement('h3', '', 'the carrier kept every bit');
  const preview = document.createElement('img');
  preview.className = 'output-preview';
  preview.src = state.outputUrl;
  preview.alt = 'painted carrier preview';

  const chips = makeElement('div', 'stat-row');
  chips.append(
    makeChip('opaque rgb png'),
    makeChip(style === 'combined' ? 'combined rgb' : 'individual rgb'),
    makeChip(`${encoded.width} × ${encoded.height} px`),
    makeChip(formatBytes(encoded.blob.size)),
    makeChip(`${verification.uniqueRgbColors}+ unique rgb`),
    makeChip(`paint mark ${verification.receipt}`),
    makeChip('exact self-check · pass'),
  );

  const verificationNote = makeElement(
    'p',
    'verification-note pass',
    'pass: opaque rgb, 680 px maximum, 257+ colors, below 900 kib, and exact hidden bytes recovered after reopening.',
  );

  const routeNote = makeElement(
    'p',
    'input-hint output-route-note',
    "twitterpaint survives x / twitter's lossless png path. post this carrier, download twitter's copy, and decode it again. the spell holds.",
  );
  const download = makeElement('a', 'primary-link', 'download png');
  download.href = state.outputUrl;
  download.download = `twitterpainted-twitterpaint-${style}-${verification.receipt}.png`;
  download.setAttribute('aria-label', 'download painted png carrier');

  card.append(heading, preview, chips, verificationNote, routeNote, download);
  byId('encode-output').append(card);
  rememberReceipt(verification.receipt);
}

function renderDecodedResults(results, source, receipt) {
  const output = byId('decode-output');
  output.replaceChildren();

  const preview = document.createElement('img');
  preview.className = 'decode-preview';
  preview.src = source.objectUrl || URL.createObjectURL(source.file);
  preview.alt = 'painted carrier being decoded';
  if (!source.objectUrl) preview.addEventListener('load', () => URL.revokeObjectURL(preview.src), { once: true });
  output.append(preview);

  const receiptRow = makeElement('div', 'stat-row receipt-row');
  receiptRow.append(makeChip(`paint mark ${receipt}`));
  const expected = lastReceipt();
  if (expected) {
    receiptRow.append(makeChip(expected === receipt ? 'matches last export' : 'different from last export'));
  }
  output.append(receiptRow);

  if (!results.length) {
    const empty = makeElement('article', 'result-card empty-result');
    empty.append(
      makeElement('h3', '', 'no readable twitterpaint text confessed'),
      makeElement('p', 'input-hint', 'no null-terminated utf-8 text passed combined rgb, individual r / g / b, or the legacy alpha fallback.'),
    );
    output.append(empty);
    return;
  }

  for (const result of results) {
    const card = makeElement('article', 'result-card decode-result');
    if (result.plane === 'A') card.classList.add('legacy-result');
    const heading = result.plane === 'RGB'
      ? 'combined rgb'
      : result.plane === 'A'
        ? 'legacy alpha · decoder only'
        : `individual ${result.plane.toLowerCase()}`;
    card.append(
      makeElement('h3', '', heading),
      makeChip(result.plane === 'A' ? 'old carrier' : 'text'),
    );
    if (result.plane === 'A') {
      card.append(makeElement(
        'p',
        'input-hint',
        'legacy alpha payload found. the current twitterpaint encoder writes only combined rgb or individual r / g / b.',
      ));
    }
    const recovered = makeElement('pre', 'recovered-text');
    recovered.textContent = result.text;
    card.append(recovered);
    output.append(card);
  }
}

async function chooseCarrier(file) {
  const next = await loadImageFile(file);
  releaseImageSource(state.carrier);
  state.carrier = next;
  byId('carrier-name').textContent = stylizeUi(file.name);
  renderSourceStats(next, 'carrier-stats');
  clearEncodedOutput();
  refreshCapacity();
}

async function chooseDecodeCarrier(file) {
  const next = await loadImageFile(file);
  assertNativeCanvasSize(next);
  releaseImageSource(state.decodeCarrier);
  state.decodeCarrier = next;
  byId('decode-name').textContent = stylizeUi(file.name);
  renderSourceStats(next, 'decode-stats');
  byId('decode-output').replaceChildren();
}

async function handleEncode(event) {
  event.preventDefault();
  const button = byId('encode-button');
  const status = byId('encode-status');
  setStatus(status);

  try {
    if (!state.carrier) throw new Error('choose a carrier image first.');
    setBusy(button, true, 'painting + checking', 'paint the text');
    const style = selectedPaintStyle();
    const hidden = style === 'combined' ? collectCombinedPayload() : collectIndividualPayloads();
    const encoded = await encodeCarrier(state.carrier, style, hidden);
    const verification = await verifyEncodedBlob(encoded.blob, style, hidden);
    if (!verification.passed) {
      if (verification.profileErrors.length) throw new Error(verification.profileErrors[0]);
      throw new Error(`exact payload self-check failed for ${verification.failedPlanes.join(', ')}; no download was created.`);
    }
    renderEncodedOutput(encoded, style, verification);
    setStatus(status, 'twitter-safe painted png; profile and exact payload checks passed.', 'success');
  } catch (error) {
    clearEncodedOutput();
    setStatus(status, error?.message || 'the browser could not paint this carrier.', 'error');
  } finally {
    setBusy(button, false, 'painting + checking', 'paint the text');
  }
}

async function handleDecode(event) {
  event.preventDefault();
  const button = byId('decode-button');
  const status = byId('decode-status');
  setStatus(status);

  try {
    if (!state.decodeCarrier) throw new Error('choose a painted carrier first.');
    setBusy(button, true, 'reading the pixels', 'read the pixels');
    assertNativeCanvasSize(state.decodeCarrier);
    const imageData = drawSource(
      state.decodeCarrier,
      state.decodeCarrier.width,
      state.decodeCarrier.height,
    );
    const results = [...TWITTERPAINT_PLANES, ...LEGACY_DECODE_PLANES]
      .map((plane) => analyzePlane(
        imageData.data,
        state.decodeCarrier.width,
        state.decodeCarrier.height,
        plane,
        { maxBytes: MAX_EXTRACTED_BYTES, minPrintable: 0.85 },
      ))
      .filter((result) => result.text !== null);
    const receipt = rasterReceipt(
      imageData.data,
      state.decodeCarrier.width,
      state.decodeCarrier.height,
    );
    renderDecodedResults(results, state.decodeCarrier, receipt);
    const legacyOnly = results.length > 0 && results.every((result) => result.plane === 'A');
    setStatus(
      status,
      legacyOnly
        ? 'decoder found a legacy alpha payload. this is an old carrier, not a current rgb export.'
        : results.length
          ? `decoder found ${results.length} readable text ${results.length === 1 ? 'candidate' : 'candidates'}.`
        : 'decoder found no readable twitterpaint text.',
      results.length ? 'success' : 'warning',
    );
  } catch (error) {
    byId('decode-output').replaceChildren();
    setStatus(status, error?.message || 'the browser could not decode this carrier.', 'error');
  } finally {
    setBusy(button, false, 'reading the pixels', 'read the pixels');
  }
}

for (const button of document.querySelectorAll('.mode-btn')) {
  button.addEventListener('click', () => {
    for (const peer of document.querySelectorAll('.mode-btn')) {
      const selected = peer === button;
      peer.classList.toggle('active', selected);
      peer.setAttribute('aria-selected', String(selected));
    }
    for (const panel of document.querySelectorAll('.panel')) {
      panel.classList.toggle('active', panel.id === button.dataset.target);
    }
  });
}

byId('carrier-input').addEventListener('change', async (event) => {
  setStatus(byId('encode-status'));
  try {
    await chooseCarrier(event.target.files[0]);
  } catch (error) {
    event.target.value = '';
    setStatus(byId('encode-status'), error?.message || 'the browser could not open this carrier.', 'error');
  }
});

byId('decode-input').addEventListener('change', async (event) => {
  setStatus(byId('decode-status'));
  try {
    await chooseDecodeCarrier(event.target.files[0]);
  } catch (error) {
    event.target.value = '';
    setStatus(byId('decode-status'), error?.message || 'the browser could not open this carrier.', 'error');
  }
});

for (const radio of document.querySelectorAll('input[name="paint-style"]')) {
  radio.addEventListener('change', syncPaintStyle);
}
byId('combined-text').addEventListener('input', refreshCapacity);
for (const card of document.querySelectorAll('.channel-card')) {
  card.querySelector('.channel-enabled').addEventListener('change', () => syncChannelCard(card));
  card.querySelector('.channel-text').addEventListener('input', refreshCapacity);
  syncChannelCard(card);
}

byId('encode-form').addEventListener('submit', handleEncode);
byId('decode-form').addEventListener('submit', handleDecode);
window.addEventListener('pagehide', () => {
  releaseImageSource(state.carrier);
  releaseImageSource(state.decodeCarrier);
  if (state.outputUrl) URL.revokeObjectURL(state.outputUrl);
});

stylizeStaticUi();
syncPaintStyle();
refreshCapacity();
