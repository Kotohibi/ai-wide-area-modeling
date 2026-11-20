// Procedural surface materials of the school for the Three.js viewer: the world-space formulas of blender/bl_mats.py (as rewritten in
// HLSL for Unreal, ue/ue_mats.py) in GLSL ES 3 - colour per pixel, relief from a 3-point height gradient near the camera, no image textures.
// Parameters per material: materials.json (make_materials.py).  The shader works in model metres p = (x, y, z up); three.js world = (x, z, -y).
// Kinds (P0.x): 0 plain fBM (also bark), 1 boards, 2 panels (sheets, mats, ceiling squares), 3 mud + bamboo lath, 4 pantiles, 5 corrugated tin,
//               6 ground (vertex colour: red = green cover, green = dry litter), 8 grass blades (vertex colour red = height along the blade).
// Dirt (P1.w): 1 floor, 2 wall, 3 outside, 4 plaster, 5 ceiling, 6 wood - only in the ruin.  Wet zones (P5.y): 1 under roof / ceiling holes, 2 + floor holes.
// Light: there is no bounced light in the browser, so the sky / ambient light is cut inside the footprints of the buildings (deeper = darker,
// brighter under the holes of the ruin's roofs); the sun comes in through windows and holes by the shadow map.
import * as THREE from "three";

export const QUALITY = { uBumpDist: { value: 30.0 }, octaves: 5 };      // relief within this distance (m); noise octaves (fewer on phones)
export const LIGHTING = { uIndoor: { value: 0.30 } };                   // ambient factor deep inside a room
let CONSTS = ""; const SHARED = {};
/** Scene constants the shaders need: footprints of the buildings, roof holes (scene.json), wet zones (materials.json).
 *  They are uniform arrays, not const arrays: indexing a const array in a loop ("icb" in D3D bytecode) made the D3D compiler fail with
 *  "Negate modifier not allowed for operand" and the WebGL context was lost. */
export function initProc(S, PM) {
  const n = (l) => Math.max(1, l.length), pad = (l, k) => l.length ? l : [new Array(k).fill(0)];
  CONSTS = `#define NBOX ${S.boxes.length}
#define NHOLE ${S.holes.length}
#define NW1 ${PM.wet.length}
#define NW2 ${PM.wetf.length}
` +
    `uniform vec4 uBox[${n(S.boxes)}]; uniform float uBoxZ[${n(S.boxes)}]; uniform vec4 uHole[${n(S.holes)}]; uniform vec3 uW1[${n(PM.wet)}]; uniform vec3 uW2[${n(PM.wetf)}];
`;
  SHARED.uBox = { value: pad(S.boxes, 4).map(b => new THREE.Vector4(b[0], b[1], b[2], b[3])) }; SHARED.uBoxZ = { value: pad(S.boxes, 5).map(b => b[4]) };
  SHARED.uHole = { value: pad(S.holes, 4).map(b => new THREE.Vector4(...b)) };
  SHARED.uW1 = { value: pad(PM.wet, 3).map(b => new THREE.Vector3(...b)) }; SHARED.uW2 = { value: pad(PM.wetf, 3).map(b => new THREE.Vector3(...b)) };
}

const LIB = /* glsl */`
uniform vec4 uP0, uP1, uP2, uP3, uP4, uP5; uniform vec3 uCA, uCB, uCC; uniform float uIndoor;
uint hsh(ivec3 p) { uint h = uint(p.x) * 0x8da6b343u ^ uint(p.y) * 0xd8163841u ^ uint(p.z) * 0xcb1ab31fu; h ^= h >> 15; h *= 0x2c1b3c6du; h ^= h >> 12; h *= 0x297a2d39u; h ^= h >> 15; return h; }
float h01(ivec3 p) { return float(hsh(p) & 0xffffffu) / 16777215.0; }
float grad3(uint h, vec3 d) { h &= 15u; float u = h < 8u ? d.x : d.y; float v = h < 4u ? d.y : ((h == 12u || h == 14u) ? d.x : d.z); return ((h & 1u) != 0u ? -u : u) + ((h & 2u) != 0u ? -v : v); }
float perlin(vec3 p) {
  vec3 i = floor(p); vec3 f = p - i; vec3 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0); ivec3 I = ivec3(i);
  float a = grad3(hsh(I), f), b = grad3(hsh(I + ivec3(1, 0, 0)), f - vec3(1, 0, 0)), c = grad3(hsh(I + ivec3(0, 1, 0)), f - vec3(0, 1, 0)), d = grad3(hsh(I + ivec3(1, 1, 0)), f - vec3(1, 1, 0));
  float e = grad3(hsh(I + ivec3(0, 0, 1)), f - vec3(0, 0, 1)), g = grad3(hsh(I + ivec3(1, 0, 1)), f - vec3(1, 0, 1)), h = grad3(hsh(I + ivec3(0, 1, 1)), f - vec3(0, 1, 1)), k = grad3(hsh(I + ivec3(1, 1, 1)), f - vec3(1, 1, 1));
  return 0.982 * mix(mix(mix(a, b, u.x), mix(c, d, u.x), u.y), mix(mix(e, g, u.x), mix(h, k, u.x), u.y), u.z);
}
// Blender's Noise Texture (fBM, normalised): vector = co * stretch + off, then * scale
float noise(vec3 co, float sc, vec3 st, int oct, float rough, float off) {
  vec3 p = (co * st + off * vec3(7.3, 3.1, 5.7)) * sc; float sum = 0.0, amp = 1.0, mx = 0.0, fs = 1.0; int oc = min(oct, OCTCAP);
  for (int k = 0; k <= 5; k++) { if (k > oc) break; sum += perlin(p * fs) * amp; mx += amp; amp *= rough; fs *= 2.0; }
  return 0.5 * sum / mx + 0.5;
}
float ramp(float v, float lo, float hi) { return lo > hi ? 1.0 - smoothstep(hi, lo, v) : smoothstep(lo, hi, v); }
float blot(vec3 co, float sc, float lo, float hi, vec3 st, float off) { return ramp(noise(co, sc, st, 4, 0.6, off), lo, hi); }
float dots(vec3 co, float sc, float r, float share) {
  vec3 p = co * sc; vec3 ip = floor(p); vec3 fp = p - ip; float md = 9.0; ivec3 cid = ivec3(0);
  for (int i = -1; i <= 1; i++) for (int j = -1; j <= 1; j++) for (int k = -1; k <= 1; k++) {
    ivec3 c = ivec3(ip) + ivec3(i, j, k); vec3 o = vec3(float(i), float(j), float(k)) + vec3(h01(c), h01(c + ivec3(17, 31, 5)), h01(c + ivec3(3, 71, 43))) - fp; float d = dot(o, o);
    if (d < md) { md = d; cid = c; } }
  return (sqrt(md) < r && h01(cid + ivec3(91, 7, 13)) < share) ? 1.0 : 0.0;
}
vec3 mixc(float f, vec3 a, vec3 b) { return mix(a, b, clamp(f, 0.0, 1.0)); }
// sky / ambient light: 1 in the open, lower inside the footprints of the buildings (deeper in = darker), brighter under the roof holes of the ruin
float indoorAmb(vec3 p, float nUp) {
  float a = 1.0;
  for (int i = 0; i < NBOX; i++) { vec4 b = uBox[i]; float top = uBoxZ[i];
    float d = min(min(p.x - b.x, b.z - p.x), min(p.y - b.y, b.w - p.y));
    if (d > 0.0 && (p.z < top + 0.06 || nUp < 0.15)) a = min(a, mix(0.72, uIndoor, smoothstep(0.0, 2.8, d)));
  }
  #if PRUIN == 1 && NHOLE > 0
    if (a < 1.0) for (int i = 0; i < NHOLE; i++) { vec4 h = uHole[i]; float dd = length(p.xy - clamp(p.xy, h.xy, h.zw)); a = max(a, mix(0.9, a, smoothstep(0.2, 3.2, dd))); }
  #endif
  return a;
}
#if PWET > 0
float nearw(vec2 xy) {
  float m = 0.0;
  #if PWET == 1
    for (int i = 0; i < NW1; i++) { vec3 w = uW1[i]; m = max(m, 1.0 - smoothstep(w.z * 0.3, w.z, length(xy - w.xy))); }
  #else
    for (int j = 0; j < NW2; j++) { vec3 w = uW2[j]; m = max(m, 1.0 - smoothstep(w.z * 0.3, w.z, length(xy - w.xy))); }
  #endif
  return m;
}
#endif
#if PDIRT > 0
// the dirt of sixty years (bl_mats.grime)
vec3 grime(vec3 p, vec3 col, float k) {
  const vec3 one = vec3(1.0); const vec3 DUST = vec3(0.33, 0.31, 0.27); float wetm = 0.0;
  #if PWET > 0
    wetm = ramp(nearw(p.xy) + (noise(p, 1.1, one, 4, 0.6, 31.0) - 0.5) * 0.8, 0.2, 0.6);
  #endif
  #if PDIRT == 1
    col = mixc(blot(p, 0.5, 0.40, 0.62, one, 3.0) * 0.5 * k, col, DUST);
    float damp = max(blot(p, 0.33, 0.52, 0.62, one, 11.0), wetm);
    col *= 1.0 - damp * 0.55;
    col = mixc(blot(p, 0.9, 0.47, 0.58, one, 23.0) * damp * 0.75, col, vec3(0.09, 0.13, 0.035));
    float grit = dots(p, 23.0, 0.17, 0.4) * blot(p, 1.3, 0.44, 0.58, one, 5.0);
    col = mixc(grit * 0.7, col, vec3(0.05, 0.045, 0.04));
    float flake = dots(p, 14.0, 0.13, 0.16) * blot(p, 0.8, 0.47, 0.60, one, 41.0);
    col = mixc(flake * 0.6, col, vec3(0.46, 0.44, 0.40));
  #elif PDIRT == 2 || PDIRT == 3
    #if PDIRT == 2
      const vec3 FILM = vec3(0.30, 0.295, 0.28); const float BL = 0.34; float foot = ramp(p.z, 0.45, -0.25);
    #else
      const vec3 FILM = vec3(0.24, 0.24, 0.235); const float BL = 0.15; float foot = ramp(p.z, 0.5, -0.5);
    #endif
    col = mixc(blot(p, 0.9, 0.45, 0.62, one, 3.0) * 0.55, col, FILM);
    col *= 1.0 - blot(p, 3.5, 0.50, 0.66, vec3(1.0, 1.0, 0.05), 7.0) * 0.5;
    float bloom = (noise(p, 26.0, one, 4, 0.6, 9.0) > 0.55 ? 1.0 : 0.0) * blot(p, 0.8, 0.45, 0.60, one, 13.0);
    col = mixc(bloom * BL, col, vec3(0.50, 0.51, 0.48));
    col *= 1.0 - foot * 0.45; col = mixc(foot * blot(p, 1.5, 0.44, 0.60, one, 17.0) * 0.5, col, vec3(0.08, 0.11, 0.04));
    col *= 1.0 - wetm * 0.5;
  #elif PDIRT == 4
    col *= 1.0 - blot(p, 3.0, 0.50, 0.66, vec3(1.0, 1.0, 0.06), 7.0) * 0.25;
    col = mixc(blot(p, 1.0, 0.50, 0.66, one, 3.0) * 0.45, col, vec3(0.20, 0.22, 0.165));
    float n = noise(p, 0.7, one, 2, 0.6, 13.0);
    col = mixc(ramp(n, 0.585, 0.63) * 0.3, col, vec3(0.36, 0.29, 0.17));
    col = mixc(ramp(abs(n - 0.585), 0.02, 0.0) * 0.22, col, vec3(0.21, 0.155, 0.09));
    col *= 1.0 - ramp(p.z, 2.35, 3.0) * blot(p, 2.0, 0.40, 0.60, vec3(1.0, 1.0, 0.3), 19.0) * 0.5;
    col *= 1.0 - ramp(p.z, 0.9, 0.0) * 0.45;
    #if PWET > 0
      col = mixc(wetm * 0.3, col * (1.0 - wetm * 0.5), vec3(0.10, 0.13, 0.06));
    #endif
  #elif PDIRT == 5
    float st = max(blot(p, 0.45, 0.60, 0.72, one, 3.0) * 0.7, wetm);
    col *= 1.0 - st * 0.7;
    float rim = ramp(abs(st - 0.3), 0.3, 0.05) * blot(p, 9.0, 0.45, 0.62, one, 9.0);
    col = mixc(rim * 0.3, col, vec3(0.40, 0.40, 0.37));
    col = mixc(blot(p, 22.0, 0.56, 0.70, one, 21.0) * 0.10, col, vec3(0.45, 0.44, 0.40));
  #else
    col = mixc(blot(p, 1.2, 0.45, 0.62, one, 3.0) * 0.6, col, vec3(0.33, 0.32, 0.30));
    col *= 1.0 - blot(p, 2.5, 0.50, 0.64, vec3(1.0, 1.0, 0.08), 7.0) * 0.5;
    col *= 1.0 - ramp(p.z, 0.35, -0.25) * 0.4;
    col *= 1.0 - wetm * 0.45;
  #endif
  return col;
}
#endif
// (the axis is picked with a constant vector and a dot product: p.y is a NEGATED shader input, and choosing it directly with ?: made the
//  D3D compiler emit invalid bytecode - "Negate modifier not allowed for operand" - and the browser lost the WebGL context)
float bu(vec3 p, float mode) { vec3 k = mode < 0.5 ? vec3(0.0, 0.0, 1.0) : (mode < 1.5 ? vec3(1.0, 1.0, 0.0) : (mode < 2.5 ? vec3(0.0, 1.0, 0.0) : vec3(1.0, 0.0, 0.0))); return dot(p, k); }
float crossAxis(vec3 p, float mode) { return dot(p.xy, mode < 2.5 ? vec2(1.0, 0.0) : vec2(0.0, 1.0)); }
vec2 tileuv(vec3 p, vec3 n) {            // tile courses: u along the eaves, v up the slope (from the face normal, not from UVs)
  float s = max(sqrt(clamp(1.0 - n.z * n.z, 0.0, 1.0)), 0.2); vec2 h = n.xy / max(length(n.xy), 1e-4);
  return vec2(dot(p.xy, vec2(-h.y, h.x)), p.z / s);
}
// p: model metres, n: face normal (model axes), cov: vertex colour
vec3 procColor(vec3 p, vec3 n, vec3 cov) {
  const vec3 one = vec3(1.0); vec3 col = uCA;
#if PKIND == 0
  float nz = noise(p, uP2.x, uP2.yzw, 5, 0.6, 0.0);
  #if PDIRT > 0
    col = grime(p, mix(uCA, uCB, ramp(nz, 0.3, 0.7)), 1.0);
  #else
    col = mix(uCA, uCB, clamp(nz, 0.0, 1.0));
  #endif
#elif PKIND == 1
  float mode = uP0.z, period = uP0.y, edge = uP0.w, vary = uP1.x, gap = uP1.y, grain = uP2.y;
  float tt = bu(p, mode) / period; float bi = floor(tt); float fr = tt - bi;
  float v = h01(ivec3(int(bi), 0, 0));
  vec3 st = mode < 0.5 ? vec3(0.6, 0.6, grain) : (mode < 1.5 ? vec3(grain, grain, 0.5) : (mode < 2.5 ? vec3(0.5, grain, grain) : vec3(grain, 0.5, grain)));
  float n1 = noise(p, 1.2, st, 5, 0.65, 0.0); float n2 = noise(p, 0.35, one, 3, 0.5, 0.0);
  #if PDIRT > 0
    n1 = ramp(n1, 0.33, 0.67);
  #endif
  col = mixc(v * vary + n1 * 0.6 - (0.05 + (vary - 0.5) * 0.5), uCA, uCB);
  col *= 0.55 + n2 * 0.8;
  if (uP3.x > 0.0) { float w = crossAxis(p, mode); float cm = fract(w / uP3.x) < uP3.y / uP3.x ? 1.0 : 0.0; col = mix(col, uCC, cm * 0.7); }
  #if PDIRT > 0
    col = grime(p, col, uP1.z);
  #endif
  { float aa = fwidth(tt) * 0.75;                                              // the dark joint, smoothed over a pixel; far away it becomes its average
    float gm = clamp(1.0 - smoothstep(edge - aa, edge + aa, fr) + smoothstep(1.0 - aa, 1.0, fr), 0.0, 1.0); gm = mix(gm, edge, clamp(aa * 2.5 - 0.4, 0.0, 1.0));
    col *= mix(1.0, gap, gm); }
#elif PKIND == 2
  float px = uP3.x, py = uP3.y, joint = uP3.z, jy = uP3.w > 0.0 ? uP3.w : uP3.z;
  float ty = (p.y - uP4.y) / py; float row = floor(ty); float fy = ty - row;
  float tx = (p.x - uP4.x) / px + mod(abs(row), 2.0) * uP4.z; float fx = fract(tx);
  float dx = min(fx, 1.0 - fx) * px, dy = min(fy, 1.0 - fy) * py; float ax = fwidth(p.x) * 0.75 + 1e-5, ay = fwidth(p.y) * 0.75 + 1e-5;
  float jm = 1.0 - min(smoothstep(joint * 0.5 - ax, joint * 0.5 + ax, dx), smoothstep(jy * 0.5 - ay, jy * 0.5 + ay, dy));
  float v = h01(ivec3(int(floor(tx)), int(row), 0)); float n1 = noise(p, uP4.w, uP2.yzw, 5, 0.65, 0.0);
  col = mixc(v * uP5.x + ramp(n1, 0.3, 0.7) * (1.0 - uP5.x), uCA, uCB);
  col = mix(col, uCC, jm);
  #if PDIRT > 0
    col = grime(p, col, uP1.z);
  #endif
#elif PKIND == 3
  float nz = noise(p, 6.0, one, 5, 0.6, 0.0); vec3 mud = mix(vec3(0.07, 0.06, 0.045), vec3(0.20, 0.17, 0.13), ramp(nz, 0.3, 0.7));
  float g = (fract((p.x + p.y) / 0.065) > 0.32 ? 1.0 : 0.0) * (fract(p.z / 0.065) > 0.32 ? 1.0 : 0.0);
  vec3 lath = mix(vec3(0.33, 0.27, 0.17), vec3(0.01, 0.008, 0.006), g);
  col = mix(mud, lath, blot(p, 1.6, 0.50, 0.55, one, 4.0));
#elif PKIND == 4
  vec2 t = tileuv(p, n); float tu = t.x / 0.27, tv = t.y / 0.235; float fu = fract(tu), fv = fract(tv);
  float w = h01(ivec3(int(floor(tu)), int(floor(tv)), int(round(n.x * 3.0)) * 7 + int(round(n.y * 3.0))));
  float nz = noise(p, 1.6, one, 5, 0.7, 0.0), n2 = noise(p, 14.0, one, 3, 0.6, 0.0);
  if (uP5.x > 0.5) col = mix(vec3(0.17, 0.175, 0.19), vec3(0.23, 0.235, 0.25), w);        // new tiles (restored school)
  else {
    col = mix(vec3(0.14, 0.14, 0.155), vec3(0.30, 0.30, 0.32), w);
    col = mixc((nz > 0.55 ? 1.0 : 0.0) * n2 * 1.2, col, vec3(0.46, 0.45, 0.46));
    col = mixc((nz < 0.33 ? 1.0 : 0.0) * 0.5, col, vec3(0.20, 0.21, 0.15));
  }
  float wave = pow(abs(sin(fu * 3.14159265)), 0.6);
  float farK = clamp(max(fwidth(tu), fwidth(tv)) * 2.0 - 0.5, 0.0, 1.0);                   // far roofs: the average instead of a moire
  col *= mix((0.25 + wave * 0.85) * (0.3 + min(fv / 0.12, 1.0) * 0.7), 0.80, farK);
#elif PKIND == 5
  float nz = noise(p, 2.5, one, 5, 0.7, 0.0); col = mix(uCA, uCB, clamp(nz, 0.0, 1.0));
  col = mix(col, uCC, (nz > 0.6 ? 1.0 : 0.0) * 0.7);
#elif PKIND == 6
  float n1 = noise(p, 0.9, one, 5, 0.65, 0.0), n2 = clamp(noise(p, 7.0, one, 4, 0.7, 0.0), 0.0, 1.0);
  vec3 g = mix(vec3(0.06, 0.085, 0.015), vec3(0.17, 0.19, 0.04), n2); vec3 d = mix(uCA, uCB, n2);
  col = mix(d, g, clamp(cov.r - cov.g + (n1 - 0.5) * 0.9 + 0.5, 0.0, 1.0));
  col *= (0.55 + 0.5 * clamp(noise(p, 40.0, one, 2, 0.6, 3.0), 0.0, 1.0)) * (0.75 + 0.5 * clamp(noise(p, 2.5, one, 3, 0.6, 7.0), 0.0, 1.0));
#elif PKIND == 8
  float nb = noise(p, 3.0, one, 2, 0.6, 0.0);                                             // blades: dark at the root, the tuft's own tone
  col = mix(uCA * 0.45, mix(uCA, uCB, nb), smoothstep(0.0, 0.7, cov.r)) * (0.8 + 0.4 * noise(p, 0.6, one, 1, 0.5, 5.0));
#endif
  return max(col, 0.0);
}
// relief in metres: laps of the clapboards, grooves between boards, joints, tile waves, corrugation
float procHeight(vec3 p, vec3 n) {
  float b = uP5.w;
#if PKIND == 1
  float mode = uP0.z, period = uP0.y; float tt = bu(p, mode) / period; float fr = fract(tt); float h;
  if (mode < 0.5) h = (1.0 - fr) * smoothstep(0.0, 0.06, fr) * 0.011;
  else { float d = min(fr, 1.0 - fr) * period; h = smoothstep(0.0, max(uP0.w * period * 0.6, 0.004), d) * 0.004; }
  if (uP3.x > 0.0) { float w = crossAxis(p, mode); float c = fract(w / uP3.x) * uP3.x; h += smoothstep(0.0, 0.004, c) * (1.0 - smoothstep(uP3.y - 0.004, uP3.y, c)) * 0.012; }
  return h * b;
#elif PKIND == 2
  float px = uP3.x, py = uP3.y, joint = uP3.z, jy = uP3.w > 0.0 ? uP3.w : uP3.z;
  float ty = (p.y - uP4.y) / py; float row = floor(ty); float fy = ty - row; float fx = fract((p.x - uP4.x) / px + mod(abs(row), 2.0) * uP4.z);
  float dx = min(fx, 1.0 - fx) * px, dy = min(fy, 1.0 - fy) * py;
  float jm = 1.0 - min(smoothstep(joint * 0.5 - 0.003, joint * 0.5 + 0.003, dx), smoothstep(jy * 0.5 - 0.003, jy * 0.5 + 0.003, dy));
  return (uP5.z > 0.5 ? jm : -jm) * 0.008 * b;
#elif PKIND == 4
  vec2 t = tileuv(p, n); float fu = fract(t.x / 0.27), fv = fract(t.y / 0.235);
  return (pow(abs(sin(fu * 3.14159265)), 0.6) * 0.55 + (1.0 - fv) * smoothstep(0.0, 0.08, fv) * 0.45) * 0.04;
#elif PKIND == 5
  return sin((p.x + p.y) * 6.2831853 / 0.076) * 0.006;
#else
  return 0.0;
#endif
}`;

const VERT_HEAD = "#include <common>\nvarying vec3 vWPos;";
const VERT_POS = `#include <project_vertex>
  vec4 wp_ = vec4(transformed, 1.0);
  #ifdef USE_INSTANCING
    wp_ = instanceMatrix * wp_;
  #endif
  vWPos = (modelMatrix * wp_).xyz;`;
const vec = (v) => v.length === 4 ? new THREE.Vector4(...v) : new THREE.Vector3(...v);

/** MeshStandardMaterial whose colour and relief come from the formulas above.  r = one entry of materials.json; opts.ruin = dirt and wet zones on. */
export function procMaterial(r, opts = {}) {
  const kind = Math.round(r.P0[0]), dirt = opts.ruin ? Math.round(r.P1[3]) : 0, wet = opts.ruin && dirt ? Math.round(r.P5[1]) : 0;
  const m = new THREE.MeshStandardMaterial({ roughness: Math.min(1, Math.max(0.05, r.rough)), metalness: Math.min(1, r.metal), vertexColors: kind === 6 || kind === 8,
                                             side: THREE.DoubleSide, shadowSide: THREE.DoubleSide });
  const bump = (kind === 1 || kind === 2 || kind === 4 || kind === 5) ? 1 : 0;
  m.defines = { ...(m.defines || {}), PKIND: kind, PDIRT: dirt, PWET: wet, PRUIN: opts.ruin ? 1 : 0, PBUMP: bump, OCTCAP: QUALITY.octaves };
  const U = { uP0: r.P0, uP1: r.P1, uP2: r.P2, uP3: r.P3, uP4: r.P4, uP5: r.P5, uCA: r.CA, uCB: r.CB, uCC: r.CC };
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, SHARED); sh.uniforms.uBumpDist = QUALITY.uBumpDist; sh.uniforms.uIndoor = LIGHTING.uIndoor; sh.uniforms.uEmit = { value: r.emit || 0 };
    for (const [k, v] of Object.entries(U)) sh.uniforms[k] = { value: vec(v) };
    sh.vertexShader = sh.vertexShader.replace("#include <common>", VERT_HEAD).replace("#include <project_vertex>", VERT_POS);
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", "#include <common>\nvarying vec3 vWPos; uniform float uEmit, uBumpDist;\n" + CONSTS + LIB)
      .replace("#include <color_fragment>", `
        vec3 cov_ = vec3(0.0);
        #if defined( USE_COLOR ) || defined( USE_COLOR_ALPHA )
          cov_ = vColor.rgb;
        #endif
        vec3 pM_ = vec3(vWPos.x, -vWPos.z, vWPos.y);
        vec3 gW_ = normalize(cross(dFdx(vWPos), dFdy(vWPos))); vec3 gM_ = vec3(gW_.x, -gW_.z, gW_.y);      // face normal (for the tile courses)
        diffuseColor.rgb = procColor(pM_, gM_, cov_);`)
      .replace("#include <normal_fragment_maps>", `#include <normal_fragment_maps>
        #if PBUMP == 1
        { float dist_ = length(vViewPosition);
          if (dist_ < uBumpDist) {
            vec3 nW_ = inverseTransformDirection(normal, viewMatrix); vec3 nM_ = normalize(vec3(nW_.x, -nW_.z, nW_.y));
            vec3 t_ = normalize(cross(nM_, abs(nM_.z) < 0.9 ? vec3(0.0, 0.0, 1.0) : vec3(1.0, 0.0, 0.0))); vec3 bt_ = cross(nM_, t_);
            float e_ = max(0.002, dist_ * 0.0012);
            float h0_ = procHeight(pM_, nM_), hx_ = procHeight(pM_ + t_ * e_, nM_), hy_ = procHeight(pM_ + bt_ * e_, nM_);
            float fade_ = 1.0 - smoothstep(uBumpDist * 0.6, uBumpDist, dist_);
            vec3 mM_ = normalize(nM_ - fade_ * (((hx_ - h0_) / e_) * t_ + ((hy_ - h0_) / e_) * bt_));
            normal = normalize((viewMatrix * vec4(mM_.x, mM_.z, -mM_.y, 0.0)).xyz);
          } }
        #endif`)
      .replace("#include <lights_fragment_end>", `#include <lights_fragment_end>
        { float amb_ = indoorAmb(pM_, inverseTransformDirection(normal, viewMatrix).y);
          // indoors the ambient light has bounced off wood and earth: warmer than the sky (blue sky light made the floors and plaster blue-grey)
          vec3 at_ = amb_ * mix(vec3(1.0), vec3(1.10, 0.97, 0.78), clamp((1.0 - amb_) / (1.0 - uIndoor), 0.0, 1.0));
          reflectedLight.indirectDiffuse *= at_; reflectedLight.indirectSpecular *= at_; }`)
      .replace("#include <emissivemap_fragment>", "#include <emissivemap_fragment>\n totalEmissiveRadiance += diffuseColor.rgb * uEmit;");
  };
  m.customProgramCacheKey = () => ["school-proc6", kind, dirt, wet, opts.ruin ? 1 : 0, QUALITY.octaves].join("-"); return m;
}

/** Window glass: a film of dirt in the ruin (more opaque where it is thick), clean panes in the restored school; frost = 1 for frosted panes. */
export function glassMaterial(frost, clean) {
  const m = new THREE.MeshStandardMaterial({ transparent: true, depthWrite: false, side: THREE.DoubleSide, metalness: 0, roughness: frost > 0.5 ? 0.45 : (clean ? 0.04 : 0.18) });
  m.defines = { ...(m.defines || {}), PKIND: 99, PDIRT: 0, PWET: 0, PRUIN: 0, PBUMP: 0, OCTCAP: Math.min(4, QUALITY.octaves) };
  m.onBeforeCompile = (sh) => {
    Object.assign(sh.uniforms, SHARED); sh.uniforms.uIndoor = LIGHTING.uIndoor; sh.uniforms.uGlass = { value: new THREE.Vector2(frost, clean ? 1 : 0) };
    for (const k of ["uP0", "uP1", "uP2", "uP3", "uP4", "uP5"]) sh.uniforms[k] = { value: new THREE.Vector4() };
    for (const k of ["uCA", "uCB", "uCC"]) sh.uniforms[k] = { value: new THREE.Vector3() };
    sh.vertexShader = sh.vertexShader.replace("#include <common>", VERT_HEAD).replace("#include <project_vertex>", VERT_POS);
    sh.fragmentShader = sh.fragmentShader.replace("#include <common>", "#include <common>\nvarying vec3 vWPos; uniform vec2 uGlass;\n" + CONSTS + LIB)
      .replace("#include <color_fragment>", `
        vec3 pM_ = vec3(vWPos.x, -vWPos.z, vWPos.y);
        float d_ = uGlass.y > 0.5 ? 0.0 : blot(pM_, 2.2, 0.36, 0.64, vec3(1.0), 0.0) * 0.7 + blot(pM_, 5.0, 0.48, 0.62, vec3(1.0, 1.0, 0.12), 5.0) * 0.3;
        if (uGlass.x > 0.5) diffuseColor = vec4(mix(vec3(0.50, 0.58, 0.60), vec3(0.33, 0.37, 0.33), d_ * 0.6), 0.86);
        else diffuseColor = vec4(mix(vec3(0.80, 0.88, 0.87), vec3(0.20, 0.20, 0.17), d_), 0.16 + d_ * 0.32);`);
  };
  m.customProgramCacheKey = () => "school-glass3-" + QUALITY.octaves; return m;
}

/** Every material of the page as [name, () => material] - for shader_check.html (the skill's scripts/threejs), which draws them one at a time. */
export async function shaderCheckList() {
  const S = await (await fetch("scene.json")).json(), PM = await (await fetch("materials.json")).json(); initProc(S, PM); const list = [];
  for (const v of ["ruin", "restored"]) for (const [n, r] of Object.entries(PM[v])) list.push([v + ":" + n, () => procMaterial(r, { ruin: v === "ruin" })]);
  list.push(["glass:ruin", () => glassMaterial(0, false)], ["glass:frost", () => glassMaterial(1, false)], ["glass:clean", () => glassMaterial(0, true)]);
  return list;
}
