/**
 * The filter registry: 21 effects, each one a self-contained WebGL2 fragment
 * shader, plus the metadata the UI needs (bilingual labels, emoji, category).
 *
 * Every shader receives the same uniform block:
 *
 * | uniform        | meaning                                              |
 * | -------------- | ---------------------------------------------------- |
 * | `u_texture`    | the current webcam frame as a texture                |
 * | `u_prev`       | the previous composited frame (feedback filters only) |
 * | `u_mask`       | the person mask from the selfie segmenter (optional)  |
 * | `u_has_mask`   | `1.0` when `u_mask` holds a valid mask                |
 * | `u_time`       | seconds since the demo started (drives animation)     |
 * | `u_resolution` | canvas size in device pixels                          |
 * | `u_flip`       | `1.0` for the selfie (mirrored) view                  |
 *
 * Motion is intentionally driven by `u_time` rather than accumulated state so
 * that pausing or freezing the frame cannot desynchronise a filter.
 */

export type FilterCategory = "basic" | "stylize" | "glitch" | "artistic" | "color" | "utility";

export interface FilterDefinition {
  id: string;
  label: string;
  labelEs: string;
  emoji: string;
  category: FilterCategory;
  description: string;
  descriptionEs: string;
  /** Uses `u_time`, so the preview never looks static. */
  animated: boolean;
  /** Needs the previous composited frame through `u_prev` (ping-pong targets). */
  needsHistory?: boolean;
  /** Needs the selfie-segmenter mask through `u_mask`. */
  needsMask?: boolean;
  /** Complete GLSL ES 3.00 fragment shader. */
  fragment: string;
}

/** Vertex stage: one full-screen triangle-strip quad, no matrices needed. */
export const VERTEX_SHADER = `#version 300 es
in vec2 a_position;
out vec2 v_uv;
void main() {
  v_uv = a_position * 0.5 + 0.5;
  gl_Position = vec4(a_position, 0.0, 1.0);
}
`;

/** Helpers shared by every fragment shader. Must start with the version pragma. */
const PRELUDE = `#version 300 es
precision highp float;
precision highp int;

in vec2 v_uv;
out vec4 outColor;

uniform sampler2D u_texture;
uniform sampler2D u_prev;
uniform sampler2D u_mask;
uniform vec2 u_resolution;
uniform float u_time;
uniform float u_flip;
uniform float u_has_mask;

const float ML_PI = 3.141592653589793;

// The selfie view mirrors horizontally. Flipping inside the sampler (instead of
// in the vertex stage) keeps every screen-space effect — kaleidoscope, glitch
// columns, vignette — aligned with what the user actually sees.
vec2 flipUV(vec2 uv) { return vec2(mix(uv.x, 1.0 - uv.x, u_flip), uv.y); }
vec4 scene(vec2 uv) { return texture(u_texture, flipUV(clamp(uv, vec2(0.0), vec2(1.0)))); }
vec4 previous(vec2 uv) { return texture(u_prev, clamp(uv, vec2(0.0), vec2(1.0))); }
float maskAt(vec2 uv) { return u_has_mask > 0.5 ? texture(u_mask, flipUV(clamp(uv, vec2(0.0), vec2(1.0)))).r : 1.0; }

float luma(vec3 c) { return dot(c, vec3(0.2126, 0.7152, 0.0722)); }
vec2 aspectUV(vec2 uv) { return (uv - 0.5) * vec2(u_resolution.x / max(u_resolution.y, 1.0), 1.0); }

float hash11(float p) {
  p = fract(p * 0.1031);
  p *= p + 33.33;
  p *= p + p;
  return fract(p);
}

float hash21(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * 0.1031);
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.x + p3.y) * p3.z);
}

vec2 hash22(vec2 p) {
  vec3 p3 = fract(vec3(p.xyx) * vec3(0.1031, 0.1030, 0.0973));
  p3 += dot(p3, p3.yzx + 33.33);
  return fract((p3.xx + p3.yz) * p3.zy);
}

/** Sobel edge magnitude on the luminance channel. */
float edgeAt(vec2 uv, vec2 texel) {
  float tl = luma(scene(uv + texel * vec2(-1.0, -1.0)).rgb);
  float t  = luma(scene(uv + texel * vec2( 0.0, -1.0)).rgb);
  float tr = luma(scene(uv + texel * vec2( 1.0, -1.0)).rgb);
  float l  = luma(scene(uv + texel * vec2(-1.0,  0.0)).rgb);
  float r  = luma(scene(uv + texel * vec2( 1.0,  0.0)).rgb);
  float bl = luma(scene(uv + texel * vec2(-1.0,  1.0)).rgb);
  float b  = luma(scene(uv + texel * vec2( 0.0,  1.0)).rgb);
  float br = luma(scene(uv + texel * vec2( 1.0,  1.0)).rgb);
  float gx = -tl - 2.0 * l - bl + tr + 2.0 * r + br;
  float gy = -tl - 2.0 * t - tr + bl + 2.0 * b + br;
  return length(vec2(gx, gy));
}

vec3 rgb2hsv(vec3 c) {
  vec4 K = vec4(0.0, -1.0 / 3.0, 2.0 / 3.0, -1.0);
  vec4 p = mix(vec4(c.bg, K.wz), vec4(c.gb, K.xy), step(c.b, c.g));
  vec4 q = mix(vec4(p.xyw, c.r), vec4(c.r, p.yzx), step(p.x, c.r));
  float d = q.x - min(q.w, q.y);
  float e = 1.0e-10;
  return vec3(abs(q.z + (q.w - q.y) / (6.0 * d + e)), d / (q.x + e), q.x);
}

vec3 hsv2rgb(vec3 c) {
  vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
  vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
  return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

/** Horizontal bar of a seven-segment glyph, in cell space. */
float hbar(vec2 p, float y, float x0, float x1, float w, float aa) {
  float inside = step(x0, p.x) * step(p.x, x1);
  return inside * (1.0 - smoothstep(w * 0.5, w * 0.5 + aa, abs(p.y - y)));
}

/** Vertical bar of a seven-segment glyph, in cell space. */
float vbar(vec2 p, float x, float y0, float y1, float w, float aa) {
  float inside = step(y0, p.y) * step(p.y, y1);
  return inside * (1.0 - smoothstep(w * 0.5, w * 0.5 + aa, abs(p.x - x)));
}

/** One seven-segment digit. 'p' is in '[0,1]²', 'w' the stroke width. */
float sevenSeg(vec2 p, int digit, float w) {
  int mask = 0;
  if (digit == 0) mask = 63;
  else if (digit == 1) mask = 6;
  else if (digit == 2) mask = 91;
  else if (digit == 3) mask = 79;
  else if (digit == 4) mask = 102;
  else if (digit == 5) mask = 109;
  else if (digit == 6) mask = 125;
  else if (digit == 7) mask = 7;
  else if (digit == 8) mask = 127;
  else mask = 111;

  float aa = w * 0.7;
  float on = 0.0;
  if ((mask & 1) != 0) on = max(on, hbar(p, 0.90, 0.16, 0.84, w, aa));
  if ((mask & 2) != 0) on = max(on, vbar(p, 0.88, 0.54, 0.86, w, aa));
  if ((mask & 4) != 0) on = max(on, vbar(p, 0.88, 0.14, 0.46, w, aa));
  if ((mask & 8) != 0) on = max(on, hbar(p, 0.10, 0.16, 0.84, w, aa));
  if ((mask & 16) != 0) on = max(on, vbar(p, 0.12, 0.14, 0.46, w, aa));
  if ((mask & 32) != 0) on = max(on, vbar(p, 0.12, 0.54, 0.86, w, aa));
  if ((mask & 64) != 0) on = max(on, hbar(p, 0.50, 0.16, 0.84, w, aa));
  return on;
}

/** 'mm:ss' camcorder stamp, drawn in pixel space. */
float digitAt(vec2 px, float x, float y, float w, float h, int digit) {
  vec2 local = (px - vec2(x, y)) / vec2(w, h);
  if (local.x < 0.0 || local.x > 1.0 || local.y < 0.0 || local.y > 1.0) return 0.0;
  return sevenSeg(local, digit, 0.16);
}

float timecode(vec2 px, float seconds) {
  float h = max(u_resolution.y * 0.052, 10.0);
  float w = h * 0.58;
  float gap = w * 0.34;
  float left = u_resolution.x - (4.0 * (w + gap) + gap * 2.0) - h * 0.8;
  float bottom = u_resolution.y - h * 1.7;
  float minutes = floor(mod(seconds / 60.0, 60.0));
  float secs = floor(mod(seconds, 60.0));

  float on = 0.0;
  on = max(on, digitAt(px, left, bottom, w, h, int(floor(minutes / 10.0))));
  on = max(on, digitAt(px, left + (w + gap), bottom, w, h, int(mod(minutes, 10.0))));
  on = max(on, digitAt(px, left + 2.0 * (w + gap) + gap, bottom, w, h, int(floor(secs / 10.0))));
  on = max(on, digitAt(px, left + 3.0 * (w + gap) + gap, bottom, w, h, int(mod(secs, 10.0))));
  // the colon, lit once per second
  vec2 colon = (px - vec2(left + 2.0 * (w + gap) - gap * 0.5, bottom)) / vec2(gap, h);
  if (colon.x >= 0.0 && colon.x <= 1.0 && colon.y >= 0.0 && colon.y <= 1.0) {
    float dots = step(abs(colon.y - 0.33), 0.11) + step(abs(colon.y - 0.7), 0.11);
    on = max(on, clamp(dots, 0.0, 1.0) * step(0.5, fract(seconds)));
  }
  return clamp(on, 0.0, 1.0);
}
`;

const frag = (body: string): string => `${PRELUDE}\n${body}\n`;

// --------------------------------------------------------------------------- //
// Shader bodies
// --------------------------------------------------------------------------- //

const ORIGINAL = frag(`
void main() {
  outColor = vec4(scene(v_uv).rgb, 1.0);
}
`);

const GRAYSCALE = frag(`
void main() {
  vec3 c = scene(v_uv).rgb;
  float g = clamp((luma(c) - 0.5) * 1.08 + 0.5, 0.0, 1.0);
  outColor = vec4(vec3(g), 1.0);
}
`);

const SEPIA = frag(`
void main() {
  vec3 c = scene(v_uv).rgb;
  mat3 m = mat3(
    0.393, 0.349, 0.272,
    0.769, 0.686, 0.534,
    0.189, 0.168, 0.131
  );
  vec3 toned = clamp(m * c, 0.0, 1.0);
  // a touch of contrast keeps the antique tone from looking flat
  toned = clamp((toned - 0.5) * 1.06 + 0.5, 0.0, 1.0);
  outColor = vec4(toned, 1.0);
}
`);

const INVERT = frag(`
void main() {
  vec3 c = scene(v_uv).rgb;
  outColor = vec4(1.0 - c, 1.0);
}
`);

const POSTERIZE = frag(`
void main() {
  vec3 c = scene(v_uv).rgb;
  float levels = 5.0;
  vec3 flat_ = floor(c * levels + 0.5) / levels;
  // a slight saturation lift is what makes screen-print colours pop
  float g = luma(flat_);
  outColor = vec4(clamp(mix(vec3(g), flat_, 1.2), 0.0, 1.0), 1.0);
}
`);

const VIGNETTE = frag(`
void main() {
  vec3 c = scene(v_uv).rgb;
  vec2 p = aspectUV(v_uv);
  float v = smoothstep(1.15, 0.25, length(p));
  c *= mix(0.28, 1.0, v);
  // a hint of warmth in the bright centre
  c *= mix(vec3(1.0), vec3(1.04, 1.0, 0.96), v);
  outColor = vec4(clamp(c, 0.0, 1.0), 1.0);
}
`);

const THERMAL = frag(`
vec3 inferno(float t) {
  t = clamp(t, 0.0, 1.0);
  vec3 c0 = vec3(0.001, 0.000, 0.014);
  vec3 c1 = vec3(0.283, 0.062, 0.431);
  vec3 c2 = vec3(0.712, 0.176, 0.373);
  vec3 c3 = vec3(0.961, 0.482, 0.161);
  vec3 c4 = vec3(0.988, 0.998, 0.645);
  float x = t * 4.0;
  vec3 col = mix(c0, c1, clamp(x, 0.0, 1.0));
  col = mix(col, c2, clamp(x - 1.0, 0.0, 1.0));
  col = mix(col, c3, clamp(x - 2.0, 0.0, 1.0));
  col = mix(col, c4, clamp(x - 3.0, 0.0, 1.0));
  return col;
}

void main() {
  // Thermal cameras have a low spatial resolution; matching that softness is
  // what sells the effect.
  vec2 px = 3.5 / u_resolution;
  vec3 acc = vec3(0.0);
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      acc += scene(v_uv + vec2(float(x), float(y)) * px).rgb;
    }
  }
  float g = luma(acc / 9.0);
  g = 1.0 - g;
  g = clamp((g - 0.12) * 1.5, 0.0, 1.0);
  vec3 heat = inferno(g);
  outColor = vec4(mix(scene(v_uv).rgb, heat, 0.92), 1.0);
}
`);

const NIGHT_VISION = frag(`
void main() {
  vec3 base = scene(v_uv).rgb;
  // Automatic gain control: normalise the exposure, then push it hard.
  float g = luma(base);
  g = clamp(g * 1.45 + 0.06, 0.0, 1.0);

  // Sensor noise proportional to the signal, like a real image intensifier.
  float n = hash21(v_uv * u_resolution * 0.7 + vec2(u_time * 61.0, u_time * 37.0)) - 0.5;
  g = clamp(g + n * (0.05 + g * 0.22), 0.0, 1.0);

  // Cheap bloom: the phosphor screen glows around bright areas.
  vec2 px = 6.0 / u_resolution;
  float bloom = 0.0;
  bloom += luma(scene(v_uv + vec2(px.x, 0.0)).rgb);
  bloom += luma(scene(v_uv - vec2(px.x, 0.0)).rgb);
  bloom += luma(scene(v_uv + vec2(0.0, px.y)).rgb);
  bloom += luma(scene(v_uv - vec2(0.0, px.y)).rgb);
  bloom *= 0.25;

  float intensity = clamp(g + bloom * 0.4, 0.0, 1.0);
  vec3 phosphor = vec3(
    intensity * 0.20 + bloom * 0.12,
    intensity + bloom * 0.10,
    intensity * 0.16 + bloom * 0.08
  );

  vec2 p = aspectUV(v_uv);
  float vig = clamp(1.25 - 0.75 * dot(p, p), 0.15, 1.0);
  float scan = 0.90 + 0.10 * sin(v_uv.y * u_resolution.y * 3.14159);
  outColor = vec4(phosphor * vig * scan, 1.0);
}
`);

const XRAY = frag(`
void main() {
  float g = luma(scene(v_uv).rgb);
  float e = edgeAt(v_uv, 1.6 / u_resolution);
  float combined = clamp(0.55 * g + 0.75 * e, 0.0, 1.0);
  float inv = 1.0 - combined;

  // Approximation of OpenCV's COLORMAP_BONE, then a lightbox blue cast.
  vec3 bone = mix(vec3(0.0, 0.0, 0.06), vec3(0.72, 0.78, 0.86), smoothstep(0.0, 0.55, inv));
  bone = mix(bone, vec3(1.0), smoothstep(0.55, 1.0, inv));
  bone *= vec3(1.12, 1.02, 1.0);
  outColor = vec4(clamp(bone, 0.0, 1.0), 1.0);
}
`);

const NEON = frag(`
void main() {
  vec2 texel = 1.0 / u_resolution;
  float e = clamp(edgeAt(v_uv, texel * 1.4) * 1.7, 0.0, 1.0);

  // Bloom: edges sampled further out, four taps is plenty at preview size.
  float glow = 0.0;
  glow += clamp(edgeAt(v_uv + vec2(texel.x * 7.0, 0.0), texel * 2.4) * 1.7, 0.0, 1.0);
  glow += clamp(edgeAt(v_uv - vec2(texel.x * 7.0, 0.0), texel * 2.4) * 1.7, 0.0, 1.0);
  glow += clamp(edgeAt(v_uv + vec2(0.0, texel.y * 7.0), texel * 2.4) * 1.7, 0.0, 1.0);
  glow += clamp(edgeAt(v_uv - vec2(0.0, texel.y * 7.0), texel * 2.4) * 1.7, 0.0, 1.0);
  glow *= 0.25;

  float hue = fract(u_time * 0.055 + v_uv.y * 0.18 + v_uv.x * 0.08);
  vec3 colour = hsv2rgb(vec3(hue, 0.85, 1.0));
  vec3 col = colour * e + colour * glow * 0.6 + colour * 0.045;
  outColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
`);

const CHROMATIC = frag(`
void main() {
  vec2 p = aspectUV(v_uv);
  float r2 = dot(p, p);
  float k = 0.014 + 0.005 * sin(u_time * 0.7);
  vec2 offset = p * k * (0.55 + r2);
  float r = scene(v_uv + offset).r;
  float g = scene(v_uv).g;
  float b = scene(v_uv - offset).b;
  // Slight darkening at the edges, where real lenses fringe the most.
  float vig = clamp(1.0 - 0.18 * r2, 0.75, 1.0);
  outColor = vec4(vec3(r, g, b) * vig, 1.0);
}
`);

const GLITCH = frag(`
void main() {
  float t = floor(u_time * 12.0);
  float row = floor(v_uv.y * 44.0);

  // Databend-style block displacement: whole rows jump sideways at random.
  float jump = hash21(vec2(row, t));
  float displaced = step(0.88, jump);
  float amount = (hash21(vec2(row * 1.7, t * 0.5)) - 0.5) * 0.26 * displaced;
  vec2 uv = vec2(clamp(v_uv.x + amount, 0.0, 1.0), v_uv.y);

  // RGB shear.
  float shift = 0.003 + 0.012 * displaced;
  vec3 c = vec3(
    scene(vec2(uv.x + shift, uv.y)).r,
    scene(uv).g,
    scene(vec2(uv.x - shift, uv.y)).b
  );

  // Dropout bands and channel rotation.
  float band = step(0.965, hash21(vec2(floor(v_uv.y * 90.0), t * 0.31)));
  c = mix(c, c.brg, band * 0.7);

  // Signal noise.
  float n = hash21(v_uv * u_resolution * 0.5 + t);
  c += (n - 0.5) * 0.09;

  // Scanline tearing.
  c *= 0.94 + 0.06 * sin(v_uv.y * u_resolution.y * 1.7 + u_time * 30.0);
  outColor = vec4(clamp(c, 0.0, 1.0), 1.0);
}
`);

const VHS = frag(`
void main() {
  // Tape wobble: a slow sine plus a fast jitter, then occasional tracking error.
  float wobble = sin(v_uv.y * 82.0 + u_time * 5.5) * 0.0016 + sin(u_time * 1.7) * 0.0022;
  float tracking = step(0.982, hash11(floor(u_time * 2.5))) * (hash11(floor(u_time * 2.5) * 3.7) - 0.5) * 0.05;
  vec2 uv = vec2(clamp(v_uv.x + wobble + tracking, 0.0, 1.0), v_uv.y);

  // Colour-under: chroma is smeared horizontally and never quite lines up.
  float bleed = 0.0042;
  vec3 c = vec3(
    scene(vec2(uv.x + bleed, uv.y)).r,
    scene(uv).g,
    scene(vec2(uv.x - bleed, uv.y)).b
  );
  c = mix(c, vec3(luma(c)), 0.2);

  // Tape grain + head-switching noise at the bottom of the frame.
  float n = hash21(vec2(floor(uv.y * u_resolution.y * 0.5), floor(u_time * 24.0)));
  c += (n - 0.5) * 0.1;
  c = mix(c, vec3(hash21(vec2(floor(uv.y * 400.0), floor(u_time * 20.0)))), smoothstep(0.05, 0.0, uv.y) * 0.8);

  // Scanlines, vignette, and a warm tape cast.
  c *= 0.92 + 0.08 * sin(v_uv.y * u_resolution.y * 2.2);
  vec2 p = aspectUV(v_uv);
  c *= clamp(1.18 - 0.55 * dot(p, p), 0.2, 1.0);
  c *= vec3(1.04, 1.0, 0.96);

  // Camcorder OSD: a blinking REC dot and an mm:ss stamp.
  vec2 px = v_uv * u_resolution;
  float dot1 = 1.0 - smoothstep(0.4, 0.55, length((px - vec2(u_resolution.x - 34.0, u_resolution.y - 34.0)) / 9.0));
  float rec = dot1 * step(0.5, fract(u_time * 1.4));
  c += vec3(0.95, 0.15, 0.15) * rec;
  c += vec3(0.95, 0.95, 0.9) * timecode(px, u_time) * 0.9;

  outColor = vec4(clamp(c, 0.0, 1.0), 1.0);
}
`);

const CRT = frag(`
void main() {
  vec2 cc = v_uv - 0.5;
  float r2 = dot(cc, cc);
  // Barrel distortion: the glass is curved.
  vec2 uv = v_uv + cc * r2 * 0.22 * vec2(1.0, 0.7);
  if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) {
    outColor = vec4(0.0, 0.0, 0.0, 1.0);
    return;
  }

  vec3 c = scene(uv).rgb;

  // Aperture grille: three phosphor stripes per pixel triad.
  float grille = 0.82 + 0.18 * sin(uv.x * u_resolution.x * 2.0944);
  c *= grille;

  // Scanlines.
  c *= 0.80 + 0.20 * sin(uv.y * u_resolution.y * 3.14159);

  // Rolling brightness bar, the classic "someone is recording this" tell.
  float bar = smoothstep(0.0, 0.14, abs(fract(uv.y + u_time * 0.07) - 0.5));
  c *= 0.92 + 0.22 * bar;

  // Bloom from the neighbouring lines.
  vec2 px = 4.0 / u_resolution;
  vec3 bloom = scene(uv + vec2(0.0, px.y)).rgb + scene(uv - vec2(0.0, px.y)).rgb;
  c += bloom * 0.06;

  c *= clamp(1.3 - 1.05 * r2, 0.08, 1.0);
  outColor = vec4(clamp(c, 0.0, 1.0), 1.0);
}
`);

const PIXELATE = frag(`
void main() {
  float block = max(floor(min(u_resolution.x, u_resolution.y) / 84.0), 2.0);
  vec2 grid = floor(v_uv * u_resolution / block);
  vec2 uv = (grid * block + block * 0.5) / u_resolution;
  vec3 c = scene(uv).rgb;
  // Posterising inside the block is what makes it read as 8-bit rather than
  // simply blurry.
  c = floor(c * 8.0 + 0.5) / 8.0;
  outColor = vec4(c, 1.0);
}
`);

const CARTOON = frag(`
void main() {
  vec2 texel = 1.0 / u_resolution;
  vec3 acc = vec3(0.0);
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      acc += scene(v_uv + vec2(float(x), float(y)) * texel * 2.0).rgb;
    }
  }
  vec3 base = acc / 9.0;
  vec3 flat_ = floor(base * 5.0 + 0.5) / 5.0;
  vec3 col = mix(base, flat_, 0.85);
  col = clamp(mix(vec3(luma(col)), col, 1.3), 0.0, 1.0);

  float e = clamp(edgeAt(v_uv, texel * 1.3) * 1.5, 0.0, 1.0);
  float ink = smoothstep(0.16, 0.46, e);
  col = mix(col, vec3(0.02, 0.02, 0.05), ink);
  outColor = vec4(col, 1.0);
}
`);

const HALFTONE = frag(`
void main() {
  vec2 px = v_uv * u_resolution;
  float cell = max(min(u_resolution.x, u_resolution.y) / 88.0, 3.0);
  float angle = 0.4636476;
  float ca = cos(angle);
  float sa = sin(angle);
  mat2 rot = mat2(ca, -sa, sa, ca);
  mat2 inv = mat2(ca, sa, -sa, ca);

  vec2 rp = (rot * px) / cell;
  vec2 local = fract(rp) - 0.5;
  float d = length(local);

  // Ink colour sampled once per dot, so each dot stays flat.
  vec2 centre = (floor(rp) + 0.5) * cell;
  vec2 source = (inv * centre) / u_resolution;
  vec3 ink = mix(vec3(0.03), scene(source).rgb, 0.9);

  float cov = 1.0 - clamp(luma(scene(source).rgb), 0.0, 1.0);
  float radius = sqrt(cov) * 0.62;
  float dot_ = 1.0 - smoothstep(radius - 0.07, radius + 0.07, d);

  vec3 paper = vec3(0.95, 0.94, 0.91);
  vec3 col = mix(paper, ink, dot_);
  col = mix(col, scene(v_uv).rgb, 0.12);
  outColor = vec4(col, 1.0);
}
`);

const KALEIDOSCOPE = frag(`
void main() {
  vec2 p = aspectUV(v_uv);
  float segments = 8.0;
  float sector = ML_PI * 2.0 / segments;
  float a = atan(p.y, p.x) + u_time * 0.22;
  float r = length(p);

  a = mod(a, sector);
  a = abs(a - sector * 0.5);
  vec2 q = vec2(cos(a), sin(a)) * r;
  vec2 uv = q / vec2(u_resolution.x / max(u_resolution.y, 1.0), 1.0) + 0.5;
  outColor = vec4(scene(uv).rgb, 1.0);
}
`);

const MATRIX = frag(`
void main() {
  vec3 base = scene(v_uv).rgb;
  float g = luma(base);
  vec3 tinted = vec3(g * 0.16, g * 0.72 + 0.05, g * 0.26);

  float cols = 64.0;
  float rows = 38.0;
  float col = floor(v_uv.x * cols);
  float row = floor(v_uv.y * rows);

  float rnd = hash21(vec2(col, 9.0));
  float speed = 0.30 + rnd * 1.10;
  float head = fract(u_time * speed * 0.42 + rnd);

  // Distance below the leading glyph, in rows.
  float below = head * (rows + 14.0) - (v_uv.y * rows);
  float tail = clamp(1.0 - below / 13.0, 0.0, 1.0);

  // Pseudo-glyph: two random strokes per cell, reshuffled a few times a second.
  vec2 local = fract(vec2(v_uv.x * cols, v_uv.y * rows));
  float frame = floor(u_time * 5.0);
  float s1 = hash21(vec2(col * 3.1 + frame, row * 1.7));
  float s2 = hash21(vec2(col * 1.3, row * 2.9 + frame));
  float stroke = step(abs(local.x - (0.25 + 0.5 * s1)), 0.14) * step(0.45, s1);
  stroke = max(stroke, step(abs(local.y - (0.25 + 0.5 * s2)), 0.12) * step(s1, 0.55));
  stroke = max(stroke, step(abs(local.x - local.y), 0.10) * step(0.75, s2));

  vec3 col3 = tinted + vec3(0.12, 0.95, 0.32) * tail * stroke;
  col3 += vec3(0.75, 1.0, 0.85) * smoothstep(0.93, 1.0, tail) * stroke;
  outColor = vec4(clamp(col3, 0.0, 1.0), 1.0);
}
`);

const TRAILS = frag(`
void main() {
  vec4 current = scene(v_uv);

  // Feedback with a slow zoom, so old echoes drift towards the centre.
  vec2 cc = v_uv - 0.5;
  vec2 prevUV = cc * 0.9965 + 0.5;
  vec3 prev = previous(prevUV).rgb;

  // "Max" feedback keeps highlights trailing without smearing the whole frame.
  vec3 col = max(current.rgb, prev * 0.90);
  col += prev * vec3(0.0, 0.01, 0.03);
  outColor = vec4(clamp(col, 0.0, 1.0), 1.0);
}
`);

const PORTRAIT = frag(`
void main() {
  vec3 base = scene(v_uv).rgb;
  if (u_has_mask < 0.5) {
    outColor = vec4(base, 1.0);
    return;
  }

  // Soften the mask so the cut-out edge is not a staircase.
  vec2 mpx = 2.0 / u_resolution;
  float soft = 0.0;
  for (int y = -1; y <= 1; y++) {
    for (int x = -1; x <= 1; x++) {
      soft += maskAt(v_uv + vec2(float(x), float(y)) * mpx);
    }
  }
  soft /= 9.0;

  // 12-tap Poisson blur for the background.
  vec2 r = 7.0 / u_resolution;
  vec3 blur = vec3(0.0);
  blur += scene(v_uv + vec2( 0.0,  1.0) * r).rgb;
  blur += scene(v_uv + vec2( 0.9,  0.4) * r).rgb;
  blur += scene(v_uv + vec2( 0.6, -0.8) * r).rgb;
  blur += scene(v_uv + vec2(-0.3, -1.0) * r).rgb;
  blur += scene(v_uv + vec2(-0.9, -0.4) * r).rgb;
  blur += scene(v_uv + vec2(-0.6,  0.8) * r).rgb;
  blur += scene(v_uv + vec2( 0.0, -1.0) * r).rgb;
  blur += scene(v_uv + vec2(-0.9,  0.4) * r).rgb;
  blur += scene(v_uv + vec2(-0.6, -0.8) * r).rgb;
  blur += scene(v_uv + vec2( 0.3,  1.0) * r).rgb;
  blur += scene(v_uv + vec2( 0.9, -0.4) * r).rgb;
  blur += scene(v_uv + vec2( 0.6,  0.8) * r).rgb;
  blur /= 12.0;

  float person = smoothstep(0.35, 0.65, soft);
  // A touch of darkening behind the subject separates the two planes.
  vec3 background = blur * 0.88;
  outColor = vec4(mix(background, base, person), 1.0);
}
`);

// --------------------------------------------------------------------------- //
// Registry
// --------------------------------------------------------------------------- //
export const FILTERS: readonly FilterDefinition[] = [
  {
    id: "original",
    label: "Original",
    labelEs: "Original",
    emoji: "🎥",
    category: "basic",
    description: "The untouched camera feed.",
    descriptionEs: "La imagen original de la cámara, sin efectos.",
    animated: false,
    fragment: ORIGINAL,
  },
  {
    id: "grayscale",
    label: "Grayscale",
    labelEs: "Escala de grises",
    emoji: "⚫",
    category: "basic",
    description: "Luminance-only rendering with a slight contrast lift.",
    descriptionEs: "Solo luminancia, con un ligero aumento de contraste.",
    animated: false,
    fragment: GRAYSCALE,
  },
  {
    id: "sepia",
    label: "Sepia",
    labelEs: "Sepia",
    emoji: "🟤",
    category: "basic",
    description: "Warm antique tone via a fixed colour matrix.",
    descriptionEs: "Tono cálido de foto antigua con una matriz de color fija.",
    animated: false,
    fragment: SEPIA,
  },
  {
    id: "invert",
    label: "Negative",
    labelEs: "Negativo",
    emoji: "🔳",
    category: "basic",
    description: "Photographic negative.",
    descriptionEs: "Negativo fotográfico.",
    animated: false,
    fragment: INVERT,
  },
  {
    id: "posterize",
    label: "Posterize",
    labelEs: "Posterizar",
    emoji: "🧱",
    category: "basic",
    description: "Quantises each channel to a few flat levels — a screen-print look.",
    descriptionEs: "Reduce cada canal a pocos niveles planos, como una serigrafía.",
    animated: false,
    fragment: POSTERIZE,
  },
  {
    id: "vignette",
    label: "Vignette",
    labelEs: "Viñeta",
    emoji: "⭕",
    category: "basic",
    description: "Darkened corners that pull the eye to the centre of frame.",
    descriptionEs: "Oscurece las esquinas para centrar la mirada.",
    animated: false,
    fragment: VIGNETTE,
  },
  {
    id: "thermal",
    label: "Thermal",
    labelEs: "Térmica",
    emoji: "🌡️",
    category: "stylize",
    description: "False-colour heat map driven by inverted luminance.",
    descriptionEs: "Mapa de calor en falso color a partir de la luminancia invertida.",
    animated: false,
    fragment: THERMAL,
  },
  {
    id: "night_vision",
    label: "Night vision",
    labelEs: "Visión nocturna",
    emoji: "🌙",
    category: "stylize",
    description: "Gen-II image intensifier: green phosphor, gain noise and bloom.",
    descriptionEs: "Intensificador de imagen: fósforo verde, ruido y resplandor.",
    animated: true,
    fragment: NIGHT_VISION,
  },
  {
    id: "xray",
    label: "X-ray",
    labelEs: "Rayos X",
    emoji: "🦴",
    category: "stylize",
    description: "Inverted radiograph with bone-bright edges.",
    descriptionEs: "Radiografía invertida, con bordes brillantes.",
    animated: false,
    fragment: XRAY,
  },
  {
    id: "neon",
    label: "Neon glow",
    labelEs: "Neón",
    emoji: "💡",
    category: "stylize",
    description: "Edges only, blooming in electric colour over black.",
    descriptionEs: "Solo los bordes, brillando en color eléctrico sobre negro.",
    animated: true,
    fragment: NEON,
  },
  {
    id: "chromatic",
    label: "Chromatic aberration",
    labelEs: "Aberración cromática",
    emoji: "🔴",
    category: "glitch",
    description: "Lens-style radial colour fringing, strongest at the edges.",
    descriptionEs: "Franjas de color radiales, más fuertes en los bordes.",
    animated: true,
    fragment: CHROMATIC,
  },
  {
    id: "glitch",
    label: "Glitch",
    labelEs: "Glitch",
    emoji: "⚡",
    category: "glitch",
    description: "Databend block displacement, RGB shear and dropout noise.",
    descriptionEs: "Bloques desplazados, separación RGB y ruido de caída de señal.",
    animated: true,
    fragment: GLITCH,
  },
  {
    id: "vhs",
    label: "VHS",
    labelEs: "VHS",
    emoji: "📼",
    category: "glitch",
    description: "Tracking noise, colour bleed, tape wobble and a timecode stamp.",
    descriptionEs: "Ruido de seguimiento, sangrado de color, ondulación y timecode.",
    animated: true,
    fragment: VHS,
  },
  {
    id: "crt",
    label: "CRT monitor",
    labelEs: "Monitor CRT",
    emoji: "🖥️",
    category: "glitch",
    description: "Aperture-grille subpixels, scanlines, barrel glass and a rolling bar.",
    descriptionEs: "Subpíxeles, líneas de barrido, cristal curvo y barra rodante.",
    animated: true,
    fragment: CRT,
  },
  {
    id: "pixelate",
    label: "Pixelate",
    labelEs: "Pixelar",
    emoji: "🟦",
    category: "artistic",
    description: "Chunky 8-bit mosaic with quantised colour.",
    descriptionEs: "Mosaico de bloques grandes con color cuantizado.",
    animated: false,
    fragment: PIXELATE,
  },
  {
    id: "cartoon",
    label: "Cartoon",
    labelEs: "Caricatura",
    emoji: "🖍️",
    category: "artistic",
    description: "Flat colour regions plus bold ink outlines — the classic cel look.",
    descriptionEs: "Regiones de color plano con contornos gruesos, estilo cómic.",
    animated: false,
    fragment: CARTOON,
  },
  {
    id: "halftone",
    label: "Halftone",
    labelEs: "Semitonos",
    emoji: "🔵",
    category: "artistic",
    description: "Newspaper dot screen, generated with a rotated dot lattice.",
    descriptionEs: "Trama de puntos de periódico, con retícula rotada.",
    animated: false,
    fragment: HALFTONE,
  },
  {
    id: "kaleidoscope",
    label: "Kaleidoscope",
    labelEs: "Caleidoscopio",
    emoji: "🔮",
    category: "artistic",
    description: "Mirrors the frame into eight rotating wedges.",
    descriptionEs: "Refleja el cuadro en ocho sectores giratorios.",
    animated: true,
    fragment: KALEIDOSCOPE,
  },
  {
    id: "matrix",
    label: "Matrix rain",
    labelEs: "Lluvia Matrix",
    emoji: "🟩",
    category: "glitch",
    description: "Falling glyph columns composited over a green-tinted feed.",
    descriptionEs: "Columnas de glifos cayendo sobre la imagen en verde.",
    animated: true,
    fragment: MATRIX,
  },
  {
    id: "trails",
    label: "Echo trails",
    labelEs: "Estelas",
    emoji: "👻",
    category: "glitch",
    description: "Feedback delay that leaves ghosts of everything that moves.",
    descriptionEs: "Retardo de realimentación que deja fantasmas de lo que se mueve.",
    animated: true,
    needsHistory: true,
    fragment: TRAILS,
  },
  {
    id: "portrait",
    label: "Background blur",
    labelEs: "Fondo desenfocado",
    emoji: "🌀",
    category: "utility",
    description: "Blurs everything behind you using the selfie segmentation mask.",
    descriptionEs: "Desenfoca todo lo que hay detrás usando la máscara de segmentación.",
    animated: false,
    needsMask: true,
    fragment: PORTRAIT,
  },
];

export const DEFAULT_FILTER_ID = "original";

export const FILTER_BY_ID: ReadonlyMap<string, FilterDefinition> = new Map(
  FILTERS.map((filter) => [filter.id, filter]),
);

/** Never returns `undefined`: falls back to the original filter. */
export function getFilter(id: string | null | undefined): FilterDefinition {
  if (id && FILTER_BY_ID.has(id)) return FILTER_BY_ID.get(id) as FilterDefinition;
  return FILTER_BY_ID.get(DEFAULT_FILTER_ID) as FilterDefinition;
}

export function filterIndex(id: string): number {
  const index = FILTERS.findIndex((filter) => filter.id === id);
  return index < 0 ? 0 : index;
}

/** Step through the registry, wrapping at both ends. */
export function stepFilterId(id: string, delta: number): string {
  const count = FILTERS.length;
  const next = (((filterIndex(id) + delta) % count) + count) % count;
  return (FILTERS[next]).id;
}

export function filterLabel(filter: FilterDefinition, lang: "es" | "en"): string {
  return lang === "es" ? filter.labelEs : filter.label;
}
