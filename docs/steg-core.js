const CHANNEL_INDEX = Object.freeze({ R: 0, G: 1, B: 2, A: 3 });

export const TWITTERPAINT_PLANES = Object.freeze(['RGB', 'R', 'G', 'B']);
export const INDIVIDUAL_CHANNELS = Object.freeze(['R', 'G', 'B']);
export const LEGACY_DECODE_PLANES = Object.freeze(['A']);
export const MAX_EXTRACTED_BYTES = 2 * 1024 * 1024;

const utf8Encoder = new TextEncoder();
const strictUtf8Decoder = new TextDecoder('utf-8', { fatal: true });

function assertDimensions(rgba, width, height) {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
    throw new TypeError('image dimensions must be positive integers');
  }
  if (!(rgba instanceof Uint8Array || rgba instanceof Uint8ClampedArray)) {
    throw new TypeError('image pixels must be a typed byte array');
  }
  if (rgba.length !== width * height * 4) {
    throw new RangeError('pixel byte length does not match the image dimensions');
  }
}

export function normalizePlane(plane) {
  const value = String(plane || '').toUpperCase();
  if (value === 'RGB') return ['R', 'G', 'B'];
  if (Object.hasOwn(CHANNEL_INDEX, value)) return [value];
  throw new TypeError('plane must be combined rgb or one individual r, g, b, or legacy a plane');
}

export function utf8Bytes(text) {
  return utf8Encoder.encode(String(text ?? ''));
}

export function textPayload(text) {
  const body = utf8Bytes(text);
  if (!body.length) throw new RangeError('the hidden text cannot be empty');
  const payload = new Uint8Array(body.length + 1);
  payload.set(body);
  return payload;
}

export function planeCapacityBits(width, height, plane) {
  const channels = normalizePlane(plane);
  return width * height * channels.length;
}

export function planeCapacityBytes(width, height, plane) {
  return Math.floor(planeCapacityBits(width, height, plane) / 8);
}

export function channelCapacityBytes(width, height) {
  if (!Number.isInteger(width) || !Number.isInteger(height) || width <= 0 || height <= 0) {
    return 0;
  }
  return Math.floor((width * height) / 8);
}

function payloadBit(payload, bitIndex) {
  return (payload[bitIndex >> 3] >> (7 - (bitIndex & 7))) & 1;
}

export function embedPlane(rgba, width, height, plane, payload) {
  assertDimensions(rgba, width, height);
  const channels = normalizePlane(plane);
  const bytes = payload instanceof Uint8Array ? payload : new Uint8Array(payload);
  const requiredBits = bytes.length * 8;
  const capacityBits = width * height * channels.length;
  if (!bytes.length) throw new RangeError('payload cannot be empty');
  if (requiredBits > capacityBits) {
    throw new RangeError(`payload needs ${requiredBits} bits; this plane holds ${capacityBits}`);
  }

  const output = new Uint8ClampedArray(rgba);
  let bitIndex = 0;
  for (let pixel = 0; pixel < width * height && bitIndex < requiredBits; pixel += 1) {
    for (const channel of channels) {
      if (bitIndex >= requiredBits) break;
      const offset = pixel * 4 + CHANNEL_INDEX[channel];
      output[offset] = (output[offset] & 0xfe) | payloadBit(bytes, bitIndex);
      bitIndex += 1;
    }
  }
  return output;
}

export function embedIndividualPlanes(rgba, width, height, payloads) {
  assertDimensions(rgba, width, height);
  let output = new Uint8ClampedArray(rgba);
  let count = 0;
  for (const channel of INDIVIDUAL_CHANNELS) {
    const payload = payloads?.[channel];
    if (!payload) continue;
    output = embedPlane(output, width, height, channel, payload);
    count += 1;
  }
  if (!count) throw new RangeError('enable at least one individual rgb plane with hidden text');
  return output;
}

export function extractPlaneBytes(
  rgba,
  width,
  height,
  plane,
  maxBytes = MAX_EXTRACTED_BYTES,
) {
  assertDimensions(rgba, width, height);
  const channels = normalizePlane(plane);
  const availableBytes = Math.floor((width * height * channels.length) / 8);
  const byteCount = Math.max(0, Math.min(availableBytes, maxBytes));
  const output = new Uint8Array(byteCount);
  let bitIndex = 0;

  for (let pixel = 0; pixel < width * height && bitIndex < byteCount * 8; pixel += 1) {
    for (const channel of channels) {
      if (bitIndex >= byteCount * 8) break;
      const bit = rgba[pixel * 4 + CHANNEL_INDEX[channel]] & 1;
      output[bitIndex >> 3] |= bit << (7 - (bitIndex & 7));
      bitIndex += 1;
    }
  }
  return output;
}

export function printableRatio(text) {
  if (!text) return 0;
  let printable = 0;
  for (const character of text) {
    const codepoint = character.codePointAt(0);
    if (character === '\n' || character === '\r' || character === '\t') printable += 1;
    else if (codepoint >= 0x20 && codepoint !== 0x7f) printable += 1;
  }
  return printable / [...text].length;
}

export function decodeTextCandidate(bytes, { minPrintable = 0.85, trim = false } = {}) {
  const zeroIndex = bytes.indexOf(0);
  if (zeroIndex <= 0) return null;
  try {
    let text = strictUtf8Decoder.decode(bytes.subarray(0, zeroIndex));
    if (trim) text = text.trim();
    if (!text || printableRatio(text) < minPrintable) return null;
    return text;
  } catch {
    return null;
  }
}

export function analyzePlane(rgba, width, height, plane, options = {}) {
  const bytes = extractPlaneBytes(rgba, width, height, plane, options.maxBytes);
  const text = decodeTextCandidate(bytes, {
    minPrintable: options.minPrintable ?? 0.85,
    trim: options.trim ?? false,
  });
  return { plane, text };
}

export function equalBytes(left, right) {
  if (!left || !right || left.byteLength !== right.byteLength) return false;
  for (let index = 0; index < left.byteLength; index += 1) {
    if (left[index] !== right[index]) return false;
  }
  return true;
}
