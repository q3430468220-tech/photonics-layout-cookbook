// photonics-layout-cookbook: a device in 3D, as the process file builds it (website/fx/solids.py writes the data).
//
//   the solid    every layer of the process table that has shapes: its top and bottom faces from the triangles of
//                its outline, its walls from the edges (the material lies to the right of every edge, so a wall
//                faces to the left of it); the implants as a tint on the top of their silicon; the top of the
//                buried oxide as a glass plate with the deep trenches cut out.
//   the view     drag to turn, pinch (or ctrl and the wheel, or the buttons) to zoom, a double click to start again.  The heights
//                are stretched by a factor that the page shows, or kept true.  "Apart" lifts the layers from one
//                another.  Where the pointer rests on a waveguide, a pane of glass stands across it with the field
//                of the solver, and the section is drawn beside the solid; a click holds it and opens the solid there.
//
// SolidMath holds what has no page around it (the section, the stretch); website/tests/test_solids.py runs it in node.
const SolidMath = (() => {
  "use strict";
  // the intervals of y (micrometres) where a layer crosses the line x = c: the crossings of its edges, paired
  function section(data, x) {
    const u = data.unit;
    const c = (x - data.window[0]) * u;
    const out = [];
    for (const s of data.solids) {
      const ys = [];
      const e = s.edges;
      for (let i = 0; i < e.length; i += 4) {
        const [xa, ya, xb, yb] = [e[i], e[i + 1], e[i + 2], e[i + 3]];
        if ((xa <= c && c < xb) || (xb <= c && c < xa)) ys.push(ya + ((c - xa) * (yb - ya)) / (xb - xa));
      }
      ys.sort((a, b) => a - b);
      const spans = [];
      for (let i = 0; i + 1 < ys.length; i += 2) spans.push([ys[i] / u + data.window[1], ys[i + 1] / u + data.window[1]]);
      if (spans.length) out.push({ key: s.key, what: s.what, family: s.family, colour: s.colour, z0: s.z0, z1: s.z1, spans });
    }
    return out;
  }
  // the stretch of the heights that makes the stack about 7 % of the width of the window, on a round number
  function stretch(data) {
    const top = Math.max(...data.solids.map((s) => s.z1)) / 1000;
    const across = Math.max(...data.size) / data.unit;
    const want = (0.07 * across) / top;
    const steps = [1, 2, 3, 5, 8, 10, 15, 20, 30];
    return steps.reduce((best, v) => (Math.abs(Math.log(v / want)) < Math.abs(Math.log(best / want)) ? v : best), 1);
  }
  // the bytes of a field (base64, scaled to its largest value): a cross-section is y-major, a top view x-major
  const bytesOf = (field) => {
    if (!field._bytes) field._bytes = Uint8Array.from(atob(field.values), (c) => c.charCodeAt(0));
    return field._bytes;
  };
  // where a cross-section field lies in a section: the middle of every strip of its width, or of every pair of its
  // width and gap
  function centres(field, parts) {
    const core = parts.find((p) => p.key === "si_core");
    if (!core) return [];
    const [w, gap] = field.core;
    const near = (a, b, tol) => Math.abs(a - b) < tol;
    if (gap === undefined) return core.spans.filter(([a, b]) => near(b - a, w, 0.04)).map(([a, b]) => (a + b) / 2);
    const out = [];
    for (let i = 0; i + 1 < core.spans.length; i++) {
      const [a0, a1] = core.spans[i];
      const [b0, b1] = core.spans[i + 1];
      if (near(a1 - a0, w, 0.04) && near(b1 - b0, w, 0.04) && near(b0 - a1, gap, 0.04)) out.push((a0 + b1) / 2);
    }
    return out;
  }
  // the light across y of a top view at a place along x, scaled to the largest value of the whole field
  function lightAt(field, x) {
    const [x0, x1, nx] = field.x;
    if (x < x0 || x > x1) return null;
    const ix = Math.round(((x - x0) / (x1 - x0)) * (nx - 1));
    const ny = field.y[2];
    return Array.from(bytesOf(field).subarray(ix * ny, ix * ny + ny), (v) => v / 255);
  }

  // ---- the section that follows the pointer: any vertical plane, not only across x ----
  // the edges of the core in micrometres, once per device: [xa, ya, xb, yb, ...]
  function coreEdges(data) {
    if (data._core) return data._core;
    const core = data.solids.find((s) => s.key === "si_core");
    const u = data.unit;
    data._core = core ? Array.from(core.edges, (v, i) => v / u + data.window[i % 2]) : [];
    return data._core;
  }
  // the direction of the waveguide at a point: the edges of the core within reach, each pulling with its length
  // towards its own direction (as an axis: an edge and its reverse pull alike); null when no core is that near
  function tangentAt(data, p, reach = 1.2) {
    const e = coreEdges(data);
    let cx = 0;
    let cy = 0;
    let nearest = Infinity;
    for (let i = 0; i < e.length; i += 4) {
      const [xa, ya, xb, yb] = [e[i], e[i + 1], e[i + 2], e[i + 3]];
      const dx = xb - xa;
      const dy = yb - ya;
      const len2 = dx * dx + dy * dy;
      if (!len2) continue;
      const t = Math.max(0, Math.min(1, ((p[0] - xa) * dx + (p[1] - ya) * dy) / len2));
      const d = Math.hypot(xa + t * dx - p[0], ya + t * dy - p[1]);
      nearest = Math.min(nearest, d);
      if (d > reach) continue;
      const w = Math.sqrt(len2) * (1 - d / reach);
      const a = Math.atan2(dy, dx);
      cx += w * Math.cos(2 * a);
      cy += w * Math.sin(2 * a);
    }
    if (!Number.isFinite(nearest) || nearest > reach || Math.hypot(cx, cy) < 1e-9) return null;
    const a = Math.atan2(cy, cx) / 2;
    return [Math.cos(a), Math.sin(a)];
  }
  // the intervals of s (micrometres) where a layer crosses the line p + s n: as section(), for any line
  function sectionLine(data, p, n) {
    const u = data.unit;
    const out = [];
    for (const s of data.solids) {
      const ss = [];
      const e = s.edges;
      for (let i = 0; i < e.length; i += 4) {
        const xa = e[i] / u + data.window[0] - p[0];
        const ya = e[i + 1] / u + data.window[1] - p[1];
        const xb = e[i + 2] / u + data.window[0] - p[0];
        const yb = e[i + 3] / u + data.window[1] - p[1];
        // the side of the line each end lies on, and where the edge crosses it
        const sa = xa * -n[1] + ya * n[0];
        const sb = xb * -n[1] + yb * n[0];
        if ((sa <= 0 && sb > 0) || (sb <= 0 && sa > 0)) {
          const t = sa / (sa - sb);
          ss.push((xa + t * (xb - xa)) * n[0] + (ya + t * (yb - ya)) * n[1]);
        }
      }
      ss.sort((a, b) => a - b);
      const spans = [];
      for (let i = 0; i + 1 < ss.length; i += 2) spans.push([ss[i], ss[i + 1]]);
      if (spans.length) out.push({ key: s.key, what: s.what, family: s.family, colour: s.colour, z0: s.z0, z1: s.z1, spans });
    }
    return out;
  }
  // the light of a top view along the line p + s n, at the given values of s (bilinear between its samples)
  function lightAlong(field, p, n, ss) {
    const [x0, x1, nx] = field.x;
    const [y0, y1, ny] = field.y;
    const b = bytesOf(field);
    let any = false;
    const out = ss.map((s) => {
      const fx = ((p[0] + s * n[0] - x0) / (x1 - x0)) * (nx - 1);
      const fy = ((p[1] + s * n[1] - y0) / (y1 - y0)) * (ny - 1);
      if (fx < 0 || fy < 0 || fx > nx - 1 || fy > ny - 1) return 0;
      any = true;
      const i = Math.min(nx - 2, Math.floor(fx));
      const j = Math.min(ny - 2, Math.floor(fy));
      const tx = fx - i;
      const ty = fy - j;
      const at = (a, c) => b[a * ny + c] / 255;
      return (1 - tx) * ((1 - ty) * at(i, j) + ty * at(i, j + 1)) + tx * ((1 - ty) * at(i + 1, j) + ty * at(i + 1, j + 1));
    });
    return any ? out : null;
  }
  // where a point lies against the ring of a ring modulator: its distance from the middle of the ring waveguide and
  // its angle (degrees, counter-clockwise from +x); and whether that angle lies in the doped arc
  function ringPlace(ring, p) {
    const dx = p[0] - ring.centre[0];
    const dy = p[1] - ring.centre[1];
    const r = Math.hypot(dx, dy);
    let a = (Math.atan2(dy, dx) * 180) / Math.PI;
    const [a0, a1] = ring.pn;
    while (a < a0) a += 360;
    while (a >= a0 + 360) a -= 360;
    return { off: r - ring.radius, angle: a, inPN: a <= a1, inward: r ? [-dx / r, -dy / r] : [0, 1] };
  }

  return { section, stretch, centres, lightAt, bytesOf, coreEdges, tangentAt, sectionLine, lightAlong, ringPlace };
})();
if (typeof module !== "undefined") module.exports = SolidMath;

(() => {
  "use strict";
  if (typeof document === "undefined") return;

  // ---- loading: one script per device ----
  const waiting = new Map();
  function load(key, src) {
    const have = window.COOKBOOK_SOLIDS && window.COOKBOOK_SOLIDS[key];
    if (have) return Promise.resolve(have);
    if (!waiting.has(key)) {
      waiting.set(key, new Promise((resolve, reject) => {
        const tag = document.createElement("script");
        tag.src = src;
        tag.onload = () => (window.COOKBOOK_SOLIDS && window.COOKBOOK_SOLIDS[key] ? resolve(window.COOKBOOK_SOLIDS[key]) : reject(new Error(key)));
        tag.onerror = () => reject(new Error(src));
        document.head.appendChild(tag);
      }));
    }
    return waiting.get(key);
  }

  // ---- matrices, column by column as WebGL reads them ----
  const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
  const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
  const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
  const unit = (a) => {
    const l = Math.hypot(a[0], a[1], a[2]) || 1;
    return [a[0] / l, a[1] / l, a[2] / l];
  };
  const perspective = (fovy, aspect, near, far) => {
    const f = 1 / Math.tan(fovy / 2);
    const nf = 1 / (near - far);
    return [f / aspect, 0, 0, 0, 0, f, 0, 0, 0, 0, (far + near) * nf, -1, 0, 0, 2 * far * near * nf, 0];
  };
  const lookAt = (eye, at, up) => {
    const z = unit(sub(eye, at));
    const x = unit(cross(up, z));
    const y = cross(z, x);
    return [x[0], y[0], z[0], 0, x[1], y[1], z[1], 0, x[2], y[2], z[2], 0, -dot(x, eye), -dot(y, eye), -dot(z, eye), 1];
  };
  const multiply = (a, b) => {
    const out = new Array(16).fill(0);
    for (let i = 0; i < 4; i++) for (let j = 0; j < 4; j++) for (let k = 0; k < 4; k++) out[i + 4 * j] += a[i + 4 * k] * b[k + 4 * j];
    return out;
  };
  const rgb = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);

  const VERTEX = `
attribute vec3 aPos;
attribute vec3 aNor;
uniform mat4 uMVP;
uniform float uZ;
uniform float uLift;
varying vec3 vNor;
varying vec3 vPos;
void main() {
  vec3 p = vec3(aPos.xy, aPos.z * uZ + uLift);
  vPos = vec3(aPos.xy, p.z);
  vNor = aNor;
  gl_Position = uMVP * vec4(p, 1.0);
}`;
  const FRAGMENT = `
precision mediump float;
uniform vec3 uColor;
uniform float uAlpha;
uniform vec3 uEye;
uniform float uFlat;
uniform vec3 uPlane;
varying vec3 vNor;
varying vec3 vPos;
void main() {
  if (dot(vPos.xy, uPlane.xy) > uPlane.z) discard;  // the side of the cut that faces the eye
  if (uFlat > 0.5) { gl_FragColor = vec4(uColor * uAlpha, uAlpha); return; }
  if (!gl_FrontFacing) {  // the inside of a solid that a cut has opened: drawn flat, as the face of the cut
    vec3 cap = mix(uColor, vec3(1.0), 0.18) * 0.92;
    gl_FragColor = vec4(cap * uAlpha, uAlpha);
    return;
  }
  vec3 n = normalize(vNor);
  vec3 v = normalize(uEye - vPos);
  vec3 key = normalize(vec3(-0.45, -0.35, 0.82));
  vec3 fill = normalize(vec3(0.6, 0.55, 0.3));
  float light = 0.3 + 0.16 * n.z + 0.6 * max(dot(n, key), 0.0) + 0.2 * max(dot(n, fill), 0.0);
  float rim = pow(1.0 - max(dot(n, v), 0.0), 3.0) * 0.28;
  float spec = pow(max(dot(n, normalize(key + v)), 0.0), 48.0) * 0.22;
  vec3 c = uColor * light + vec3(rim + spec);
  gl_FragColor = vec4(c * uAlpha, uAlpha);
}`;

  // the light of a top view, laid on the top of the silicon: a texture added to what lies below it
  const LIGHT_VERTEX = `
attribute vec2 aXY;
attribute vec2 aUV;
uniform mat4 uMVP;
uniform float uH;
varying vec2 vUV;
varying vec2 vXY;
void main() {
  vUV = aUV;
  vXY = aXY;
  gl_Position = uMVP * vec4(aXY, uH, 1.0);
}`;
  const LIGHT_FRAGMENT = `
precision mediump float;
uniform sampler2D uTex;
uniform vec3 uPlane;
uniform float uAlpha;
varying vec2 vUV;
varying vec2 vXY;
void main() {
  if (dot(vXY, uPlane.xy) > uPlane.z) discard;
  float v = texture2D(uTex, vUV).r;
  vec3 c = mix(vec3(0.37, 0.91, 0.96), vec3(1.0), v * v);
  gl_FragColor = vec4(c * v * uAlpha, 0.0);
}`;

  const DECAL_FRAGMENT = `
precision mediump float;
uniform sampler2D uTex;
uniform float uAlpha;
varying vec2 vUV;
void main() {
  vec4 c = texture2D(uTex, vUV);
  gl_FragColor = vec4(c.rgb * c.a * uAlpha, c.a * uAlpha);
}`;

  // the section that follows the pointer: a pane of glass standing across the waveguide, with the field of the
  // solver drawn on it (a texture, premultiplied), its heights stretched as the solid's
  const PLANE_VERTEX = `
attribute vec3 aPos;
attribute vec2 aUV;
uniform mat4 uMVP;
uniform float uZ;
varying vec2 vUV;
void main() {
  vUV = aUV;
  gl_Position = uMVP * vec4(aPos.xy, aPos.z * uZ, 1.0);
}`;
  const PLANE_FRAGMENT = `
precision mediump float;
uniform sampler2D uTex;
uniform float uAlpha;
uniform float uGlass;
varying vec2 vUV;
void main() {
  vec4 c = texture2D(uTex, vUV);
  float edge = max(step(vUV.x, 0.006) + step(0.994, vUV.x), step(vUV.y, 0.012) + step(0.988, vUV.y));
  vec3 glass = vec3(0.55, 0.85, 1.0);
  vec3 rgb = c.rgb + glass * (uGlass * (1.0 - c.a) + 0.55 * edge);
  float a = c.a + (1.0 - c.a) * (uGlass + 0.5 * edge);
  gl_FragColor = vec4(rgb * uAlpha, a * uAlpha);
}`;

  // ---- the viewer ----
  class Viewer {
    constructor(canvas) {
      const gl = canvas.getContext("webgl", { antialias: true, premultipliedAlpha: true, alpha: true });
      if (!gl) throw new Error("no WebGL");
      this.gl = gl;
      this.canvas = canvas;
      const shader = (type, text) => {
        const s = gl.createShader(type);
        gl.shaderSource(s, text);
        gl.compileShader(s);
        if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
        return s;
      };
      const p = gl.createProgram();
      gl.attachShader(p, shader(gl.VERTEX_SHADER, VERTEX));
      gl.attachShader(p, shader(gl.FRAGMENT_SHADER, FRAGMENT));
      gl.linkProgram(p);
      if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p));
      this.program = p;
      const q = gl.createProgram();
      gl.attachShader(q, shader(gl.VERTEX_SHADER, LIGHT_VERTEX));
      gl.attachShader(q, shader(gl.FRAGMENT_SHADER, LIGHT_FRAGMENT));
      gl.linkProgram(q);
      this.lightProgram = gl.getProgramParameter(q, gl.LINK_STATUS) ? q : null;
      const dq = gl.createProgram();
      gl.attachShader(dq, shader(gl.VERTEX_SHADER, LIGHT_VERTEX));
      gl.attachShader(dq, shader(gl.FRAGMENT_SHADER, DECAL_FRAGMENT));
      gl.linkProgram(dq);
      this.decalProgram = gl.getProgramParameter(dq, gl.LINK_STATUS) ? dq : null;
      const pq = gl.createProgram();
      gl.attachShader(pq, shader(gl.VERTEX_SHADER, PLANE_VERTEX));
      gl.attachShader(pq, shader(gl.FRAGMENT_SHADER, PLANE_FRAGMENT));
      gl.linkProgram(pq);
      this.planeProgram = gl.getProgramParameter(pq, gl.LINK_STATUS) ? pq : null;
      if (this.planeProgram) {
        this.planeLoc = {
          pos: gl.getAttribLocation(pq, "aPos"),
          uv: gl.getAttribLocation(pq, "aUV"),
          ...Object.fromEntries(["uMVP", "uZ", "uTex", "uAlpha", "uGlass"].map((n) => [n, gl.getUniformLocation(pq, n)])),
        };
      }
      this.probe = null;
      this.decals = null;
      this.beam = "";
      if (this.lightProgram) {
        this.lightLoc = {
          xy: gl.getAttribLocation(q, "aXY"),
          uv: gl.getAttribLocation(q, "aUV"),
          ...Object.fromEntries(["uMVP", "uH", "uTex", "uPlane", "uAlpha"].map((n) => [n, gl.getUniformLocation(q, n)])),
        };
      }
      this.loc = {
        pos: gl.getAttribLocation(p, "aPos"),
        nor: gl.getAttribLocation(p, "aNor"),
        ...Object.fromEntries(["uMVP", "uZ", "uLift", "uColor", "uAlpha", "uEye", "uFlat", "uPlane"].map((n) => [n, gl.getUniformLocation(p, n)])),
      };
      // cut: a place along x, or plane: {c: [x, y], n: [nx, ny]}, a vertical plane through c across n (window
      // coordinates, micrometres); the solid is opened on the side that faces the eye
      this.view = { az: -2.25, el: 0.6, zoom: 1, explode: 0, z: 1, cut: Infinity, plane: null, hidden: new Set(), light: true };
      this.parts = [];
      // hooks for an animation that builds the solid layer by layer: an extra lift and an opacity for part i
      this.lift = () => 0;
      this.fade = () => 1;
    }

    setSolid(data) {
      const gl = this.gl;
      for (const part of this.parts) {
        gl.deleteBuffer(part.buffer);
        if (part.lines) gl.deleteBuffer(part.lines);
      }
      this.data = data;
      const u = data.unit;
      const cx = data.size[0] / 2;
      const cy = data.size[1] / 2;
      const X = (v) => (v - cx) / u;
      const Y = (v) => (v - cy) / u;
      this.width = data.size[0] / u;
      this.height = data.size[1] / u;
      this.x0 = data.window[0] + this.width / 2; // the window's centre, in the coordinates of the layout
      this.y0 = data.window[1] + this.height / 2;
      const upload = (array) => {
        const b = gl.createBuffer();
        gl.bindBuffer(gl.ARRAY_BUFFER, b);
        gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(array), gl.STATIC_DRAW);
        return b;
      };
      // faces: the triangles turned counter-clockwise seen from above (the top) or from below (the bottom)
      const faces = (f, z, up, out) => {
        for (let i = 0; i < f.length; i += 6) {
          let [ax, ay, bx, by, qx, qy] = [X(f[i]), Y(f[i + 1]), X(f[i + 2]), Y(f[i + 3]), X(f[i + 4]), Y(f[i + 5])];
          const area = (bx - ax) * (qy - ay) - (qx - ax) * (by - ay);
          if ((area < 0) === up) [bx, by, qx, qy] = [qx, qy, bx, by];
          const n = up ? 1 : -1;
          out.push(ax, ay, z, 0, 0, n, bx, by, z, 0, 0, n, qx, qy, z, 0, 0, n);
        }
      };
      // walls: the quad of every edge, facing to its left (the outside)
      const walls = (e, z0, z1, out) => {
        for (let i = 0; i < e.length; i += 4) {
          const [ax, ay, bx, by] = [X(e[i]), Y(e[i + 1]), X(e[i + 2]), Y(e[i + 3])];
          const [nx, ny] = unit([-(by - ay), bx - ax, 0]);
          const A0 = [ax, ay, z0, nx, ny, 0];
          const A1 = [ax, ay, z1, nx, ny, 0];
          const B0 = [bx, by, z0, nx, ny, 0];
          const B1 = [bx, by, z1, nx, ny, 0];
          out.push(...A0, ...A1, ...B1, ...A0, ...B1, ...B0);
        }
      };
      const outline = (e, z, out) => {
        for (let i = 0; i < e.length; i += 4) out.push(X(e[i]), Y(e[i + 1]), z, 0, 0, 1, X(e[i + 2]), Y(e[i + 3]), z, 0, 0, 1);
      };
      this.parts = [];
      data.solids.forEach((s, index) => {
        const rank = s.rank ?? index; // the level it floats on when the layers are apart
        const tri = [];
        faces(s.faces, s.z1 / 1000, true, tri);
        faces(s.faces, s.z0 / 1000, false, tri);
        walls(s.edges, s.z0 / 1000, s.z1 / 1000, tri);
        const lines = [];
        outline(s.edges, s.z1 / 1000, lines);
        this.parts.push({ kind: "solid", key: s.key, family: s.family, colour: rgb(s.colour), rank, z0: s.z0, z1: s.z1, device: s.device,
          buffer: upload(tri), count: tri.length / 6, lines: upload(lines), lineCount: lines.length / 6 }); // fmt: skip
      });
      for (const imp of data.implants) {
        const tri = [];
        faces(imp.faces, imp.z / 1000, true, tri);
        const host = this.parts.find((p) => p.kind === "solid" && Math.abs(p.z1 - imp.z) < 1 && p.device === imp.device);
        this.parts.push({ kind: "implant", key: imp.key, family: "implant", colour: rgb(imp.colour), rank: host ? host.rank : 0, device: imp.device,
          alpha: { 1: 0.38, 2: 0.55, 3: 0.72 }[imp.strength], buffer: upload(tri), count: tri.length / 6 }); // fmt: skip
      }
      const g = data.ground;
      const tri = [];
      faces(g.faces, g.z1 / 1000, true, tri);
      faces(g.faces, g.z0 / 1000, false, tri);
      walls(g.edges, g.z0 / 1000, g.z1 / 1000, tri);
      const lines = [];
      outline(g.edges, g.z1 / 1000, lines);
      this.parts.push({ kind: "ground", key: "ground", family: "ground", colour: rgb(g.colour), rank: -1, buffer: upload(tri),
        count: tri.length / 6, lines: upload(lines), lineCount: lines.length / 6 }); // fmt: skip
      // the glass of every level, as large as the window, and the column of light over every device
      for (const sheet of data.sheets || []) {
        const W = data.size[0];
        const H = data.size[1];
        const z = sheet.z / 1000;
        const tri = [X(0), Y(0), z, 0, 0, 1, X(W), Y(0), z, 0, 0, 1, X(W), Y(H), z, 0, 0, 1, X(0), Y(0), z, 0, 0, 1, X(W), Y(H), z, 0, 0, 1, X(0), Y(H), z, 0, 0, 1];
        const lines = [];
        outline([0, 0, 0, H, 0, H, W, H, W, H, W, 0, W, 0, 0, 0], z, lines);
        this.parts.push({ kind: "sheet", key: sheet.key, family: "sheet", colour: rgb("#8fa3d9"), rank: sheet.rank, z0: sheet.z, z1: sheet.z,
          buffer: upload(tri), count: 6, lines: upload(lines), lineCount: lines.length / 6 }); // fmt: skip
      }
      for (const b of data.beams || []) {
        const tri = [];
        walls([b.x0, b.y0, b.x0, b.y1, b.x0, b.y1, b.x1, b.y1, b.x1, b.y1, b.x1, b.y0, b.x1, b.y0, b.x0, b.y0], 0, 1, tri);
        this.parts.push({ kind: "beam", key: b.device, device: b.device, family: "beam", colour: rgb("#bff6ff"), rank: -1, buffer: upload(tri), count: tri.length / 6 });
      }
      this.top = Math.max(...data.solids.map((s) => s.z1)) / 1000;
      this.levels = data.levels ?? data.solids.length;
      this.X = X;
      this.Y = Y;
      this.setLight(data, X, Y);
    }

    // the top view of the solver as a texture, on a quad over the part of the window it covers
    setLight(data, X, Y) {
      const gl = this.gl;
      if (this.light) {
        gl.deleteTexture(this.light.texture);
        gl.deleteBuffer(this.light.buffer);
      }
      this.light = null;
      const field = (data.fields || []).find((f) => f.kind === "top");
      if (!field || !this.lightProgram) return;
      this.setLightBytes(field.x, field.y, Uint8Array.from(atob(field.values), (c) => c.charCodeAt(0)));
    }

    // a top view of light as bytes, x-major (x0, x1, nx) by (y0, y1, ny), laid on the top of the silicon
    setLightBytes([x0, x1, nx], [y0, y1, ny], bytes) {
      const gl = this.gl;
      const data = this.data;
      const X = this.X;
      const Y = this.Y;
      if (!this.lightProgram) return;
      if (this.light) {
        gl.deleteTexture(this.light.texture);
        gl.deleteBuffer(this.light.buffer);
        this.light = null;
      }
      const rows = new Uint8Array(nx * ny); // the texture runs along x, row by row of y
      for (let ix = 0; ix < nx; ix++) for (let iy = 0; iy < ny; iy++) rows[iy * nx + ix] = bytes[ix * ny + iy];
      const texture = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 1);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.LUMINANCE, nx, ny, 0, gl.LUMINANCE, gl.UNSIGNED_BYTE, rows);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      const u = data.unit;
      const wx = (x) => X((x - data.window[0]) * u);
      const wy = (y) => Y((y - data.window[1]) * u);
      const quad = [wx(x0), wy(y0), 0, 0, wx(x1), wy(y0), 1, 0, wx(x0), wy(y1), 0, 1, wx(x1), wy(y1), 1, 1];
      const buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(quad), gl.STATIC_DRAW);
      const core = data.solids.find((s) => s.key === "si_core");
      this.light = { texture, buffer, z: (core ? core.z1 : 220) / 1000, core: this.parts.findIndex((p) => p.key === "si_core") };
    }

    draw() {
      const gl = this.gl;
      const canvas = this.canvas;
      const ratio = Math.min(2, window.devicePixelRatio || 1);
      const w = Math.max(1, Math.round(canvas.clientWidth * ratio));
      const h = Math.max(1, Math.round(canvas.clientHeight * ratio));
      if (canvas.width !== w || canvas.height !== h) {
        canvas.width = w;
        canvas.height = h;
      }
      gl.viewport(0, 0, w, h);
      gl.clearColor(0, 0, 0, 0);
      gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
      if (!this.data) return;
      const v = this.view;
      const gap = 0.05 * Math.max(this.width, this.height); // the lift between two layers when they are apart
      const stackTop = this.top * v.z + gap * v.explode * this.levels;
      const target = [0, 0, stackTop * 0.4];
      const radius = 0.5 * Math.hypot(this.width, this.height, stackTop);
      const fov = 0.55;
      const dist = (radius / Math.sin(fov / 2)) * 0.92 / v.zoom;
      const eye = [target[0] + dist * Math.cos(v.el) * Math.cos(v.az), target[1] + dist * Math.cos(v.el) * Math.sin(v.az), target[2] + dist * Math.sin(v.el)];
      const mvp = multiply(perspective(fov, w / h, dist * 0.02, dist * 6), lookAt(eye, target, [0, 0, 1]));
      this.mvp = mvp;
      this.gap = gap;
      this.stackTop = stackTop;
      gl.useProgram(this.program);
      const L = this.loc;
      gl.uniformMatrix4fv(L.uMVP, false, new Float32Array(mvp));
      gl.uniform1f(L.uZ, v.z);
      gl.uniform3fv(L.uEye, eye);
      // the plane of the cut, in the frame of the drawing (the window's centre at 0): what lies beyond it, seen from
      // the eye, is kept
      let plane = [0, 0, 1e9];
      if (v.plane) {
        const c = [v.plane.c[0] - this.x0, v.plane.c[1] - this.y0];
        let [nx, ny] = v.plane.n;
        if (nx * (eye[0] - c[0]) + ny * (eye[1] - c[1]) < 0) [nx, ny] = [-nx, -ny];
        plane = [nx, ny, nx * c[0] + ny * c[1]];
      } else if (Number.isFinite(v.cut)) plane = [1, 0, v.cut - this.x0];
      this.eye = eye;
      this.target = target;
      this.fov = fov;
      gl.uniform3fv(L.uPlane, plane);
      gl.enable(gl.DEPTH_TEST);
      gl.enable(gl.BLEND);
      gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
      gl.disable(gl.CULL_FACE);
      const bind = (buffer) => {
        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.enableVertexAttribArray(L.pos);
        gl.vertexAttribPointer(L.pos, 3, gl.FLOAT, false, 24, 0);
        gl.enableVertexAttribArray(L.nor);
        gl.vertexAttribPointer(L.nor, 3, gl.FLOAT, false, 24, 12);
      };
      const shown = (part) => !v.hidden.has(part.family === "slab" ? "silicon" : part.family);
      const liftOf = (part, i) => (part.rank >= 0 ? gap * v.explode * part.rank : 0) + this.lift(i, part);
      // the solids, opaque
      gl.depthMask(true);
      this.parts.forEach((part, i) => {
        if (part.kind !== "solid" || !shown(part)) return;
        const a = this.fade(i, part);
        if (a <= 0.01) return;
        gl.uniform1f(L.uLift, liftOf(part, i));
        gl.uniform3fv(L.uColor, part.colour);
        gl.uniform1f(L.uAlpha, a);
        gl.uniform1f(L.uFlat, 0);
        bind(part.buffer);
        gl.drawArrays(gl.TRIANGLES, 0, part.count);
        gl.uniform3fv(L.uColor, part.colour.map((c) => Math.min(1, c * 0.55 + 0.45)));
        gl.uniform1f(L.uAlpha, 0.55 * a);
        gl.uniform1f(L.uFlat, 1);
        bind(part.lines);
        gl.drawArrays(gl.LINES, 0, part.lineCount);
      });
      // the implants: a tint on the top of their silicon
      gl.enable(gl.POLYGON_OFFSET_FILL);
      gl.polygonOffset(-2, -2);
      gl.depthMask(false);
      this.parts.forEach((part, i) => {
        if (part.kind !== "implant" || v.hidden.has("implant")) return;
        const a = this.fade(i, part) * part.alpha;
        if (a <= 0.01) return;
        gl.uniform1f(L.uLift, liftOf(part, i));
        gl.uniform3fv(L.uColor, part.colour);
        gl.uniform1f(L.uAlpha, a);
        gl.uniform1f(L.uFlat, 1);
        bind(part.buffer);
        gl.drawArrays(gl.TRIANGLES, 0, part.count);
      });
      gl.disable(gl.POLYGON_OFFSET_FILL);
      // the light of the solver on the top of the silicon, added to what lies below it
      if (this.light && v.light && !v.hidden.has("silicon")) {
        const LL = this.lightLoc;
        const core = this.parts[this.light.core];
        gl.useProgram(this.lightProgram);
        gl.uniformMatrix4fv(LL.uMVP, false, new Float32Array(mvp));
        gl.uniform1f(LL.uH, this.light.z * v.z + (core ? liftOf(core, this.light.core) : 0) + 0.002);
        gl.uniform3fv(LL.uPlane, plane);
        gl.uniform1f(LL.uAlpha, core ? this.fade(this.light.core, core) : 1);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, this.light.texture);
        gl.uniform1i(LL.uTex, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.light.buffer);
        gl.disableVertexAttribArray(L.nor);
        gl.enableVertexAttribArray(LL.xy);
        gl.vertexAttribPointer(LL.xy, 2, gl.FLOAT, false, 16, 0);
        gl.enableVertexAttribArray(LL.uv);
        gl.vertexAttribPointer(LL.uv, 2, gl.FLOAT, false, 16, 8);
        gl.blendFunc(gl.ONE, gl.ONE);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
        gl.disableVertexAttribArray(LL.uv);
        gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
        gl.useProgram(this.program);
      }
      // the glass of the levels, which shows as they part
      this.parts.forEach((part, i) => {
        if (part.kind !== "sheet" || v.explode < 0.02) return;
        const a = this.fade(i, part) * Math.min(1, v.explode * 1.6);
        gl.uniform1f(L.uLift, liftOf(part, i));
        gl.uniform3fv(L.uColor, part.colour);
        gl.uniform1f(L.uAlpha, 0.055 * a);
        gl.uniform1f(L.uFlat, 1);
        bind(part.buffer);
        gl.drawArrays(gl.TRIANGLES, 0, part.count);
        gl.uniform1f(L.uAlpha, 0.3 * a);
        bind(part.lines);
        gl.drawArrays(gl.LINES, 0, part.lineCount);
      });
      // the column of light over the device that the pointer is on, through every level
      this.parts.forEach((part) => {
        if (part.kind !== "beam" || part.device !== this.beam) return;
        gl.uniform1f(L.uZ, stackTop + gap * 0.6);
        gl.uniform1f(L.uLift, 0);
        gl.uniform3fv(L.uColor, part.colour);
        gl.uniform1f(L.uAlpha, 0.13);
        gl.uniform1f(L.uFlat, 1);
        gl.blendFunc(gl.ONE, gl.ONE);
        bind(part.buffer);
        gl.drawArrays(gl.TRIANGLES, 0, part.count);
        gl.blendFunc(gl.ONE, gl.ONE_MINUS_SRC_ALPHA);
        gl.uniform1f(L.uZ, v.z);
      });
      // the ground: glass, last
      this.parts.forEach((part, i) => {
        if (part.kind !== "ground" || v.hidden.has("ground")) return;
        const a = this.fade(i, part);
        gl.uniform1f(L.uLift, this.lift(i, part));
        gl.uniform3fv(L.uColor, part.colour);
        gl.uniform1f(L.uAlpha, 0.2 * a);
        gl.uniform1f(L.uFlat, 0);
        bind(part.buffer);
        gl.drawArrays(gl.TRIANGLES, 0, part.count);
        gl.uniform1f(L.uAlpha, 0.35 * a);
        gl.uniform1f(L.uFlat, 1);
        bind(part.lines);
        gl.drawArrays(gl.LINES, 0, part.lineCount);
      });
      // the drawings of what is still to come, flat on the top of the ground
      if (this.decals && this.decalProgram) {
        const DL = this.decalLoc;
        gl.useProgram(this.decalProgram);
        gl.uniformMatrix4fv(DL.uMVP, false, new Float32Array(mvp));
        gl.uniform1f(DL.uH, 0.003);
        gl.uniform1f(DL.uAlpha, this.decals.alpha);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, this.decals.texture);
        gl.uniform1i(DL.uTex, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.decals.buffer);
        gl.disableVertexAttribArray(L.nor);
        gl.enableVertexAttribArray(DL.xy);
        gl.vertexAttribPointer(DL.xy, 2, gl.FLOAT, false, 16, 0);
        gl.enableVertexAttribArray(DL.uv);
        gl.vertexAttribPointer(DL.uv, 2, gl.FLOAT, false, 16, 8);
        gl.drawArrays(gl.TRIANGLES, 0, this.decals.count);
        gl.disableVertexAttribArray(DL.uv);
        gl.useProgram(this.program);
      }
      // the pane of the section, last: glass with the field of the solver on it
      if (this.probe && this.planeProgram) {
        const PL = this.planeLoc;
        gl.useProgram(this.planeProgram);
        gl.uniformMatrix4fv(PL.uMVP, false, new Float32Array(mvp));
        gl.uniform1f(PL.uZ, v.z);
        gl.uniform1f(PL.uAlpha, 1);
        gl.uniform1f(PL.uGlass, this.probe.held ? 0.12 : 0.16);
        gl.activeTexture(gl.TEXTURE0);
        gl.bindTexture(gl.TEXTURE_2D, this.probe.texture);
        gl.uniform1i(PL.uTex, 0);
        gl.bindBuffer(gl.ARRAY_BUFFER, this.probe.buffer);
        gl.disableVertexAttribArray(L.nor);
        gl.enableVertexAttribArray(PL.pos);
        gl.vertexAttribPointer(PL.pos, 3, gl.FLOAT, false, 20, 0);
        gl.enableVertexAttribArray(PL.uv);
        gl.vertexAttribPointer(PL.uv, 2, gl.FLOAT, false, 20, 12);
        gl.depthMask(false);
        gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
        gl.disableVertexAttribArray(PL.uv);
        gl.useProgram(this.program);
      }
      gl.depthMask(true);
    }

    // a point of the world (micrometres, heights already stretched and lifted) on the canvas, in CSS pixels
    project(p) {
      const m = this.mvp;
      if (!m) return null;
      const x = m[0] * p[0] + m[4] * p[1] + m[8] * p[2] + m[12];
      const y = m[1] * p[0] + m[5] * p[1] + m[9] * p[2] + m[13];
      const w = m[3] * p[0] + m[7] * p[1] + m[11] * p[2] + m[15];
      if (w <= 0) return null;
      return [((x / w + 1) / 2) * this.canvas.clientWidth, ((1 - y / w) / 2) * this.canvas.clientHeight];
    }

    // the point of the window (micrometres, the coordinates of the layout) under a pixel of the canvas, on the plane
    // of the top of the silicon; null when the ray of that pixel misses it
    pick(px, py) {
      if (!this.eye || !this.data) return null;
      const w = this.canvas.clientWidth;
      const h = this.canvas.clientHeight;
      const f = unit(sub(this.target, this.eye));
      const r = unit(cross(f, [0, 0, 1]));
      const u = cross(r, f);
      const t = Math.tan(this.fov / 2);
      const nx = ((2 * px) / w - 1) * t * (w / h);
      const ny = (1 - (2 * py) / h) * t;
      const d = [f[0] + r[0] * nx + u[0] * ny, f[1] + r[1] * nx + u[1] * ny, f[2] + r[2] * nx + u[2] * ny];
      const core = this.data.solids.find((s) => s.key === "si_core");
      const z = ((core ? core.z1 : 220) / 1000) * this.view.z;
      if (Math.abs(d[2]) < 1e-9) return null;
      const k = (z - this.eye[2]) / d[2];
      if (k <= 0) return null;
      return [this.eye[0] + k * d[0] + this.x0, this.eye[1] + k * d[1] + this.y0];
    }

    // the pane of the section: from a to b (window, micrometres) and from z0 to z1 (true heights), with an image of
    // the field on it (a canvas, premultiplied below), or plain glass when there is none; null takes it away
    setProbe(probe) {
      const gl = this.gl;
      if (this.probe) {
        gl.deleteBuffer(this.probe.buffer);
        if (this.probe.texture) gl.deleteTexture(this.probe.texture);
        this.probe = null;
      }
      if (!probe || !this.planeProgram) return;
      const ax = probe.a[0] - this.x0;
      const ay = probe.a[1] - this.y0;
      const bx = probe.b[0] - this.x0;
      const by = probe.b[1] - this.y0;
      const q = [ax, ay, probe.z0, 0, 1, bx, by, probe.z0, 1, 1, ax, ay, probe.z1, 0, 0, bx, by, probe.z1, 1, 0];
      const buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(q), gl.STATIC_DRAW);
      const texture = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, true);
      if (probe.image) gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, probe.image);
      else gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, 1, 1, 0, gl.RGBA, gl.UNSIGNED_BYTE, new Uint8Array([0, 0, 0, 0]));
      gl.pixelStorei(gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, false);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      this.probe = { buffer, texture, held: Boolean(probe.held) };
    }

    // drawings on the top of the ground: an image (an atlas) and, for each, a rectangle in the window and in the image
    setDecals(image, quads, alpha) {
      const gl = this.gl;
      if (!this.decalProgram) return;
      const q = this.decalProgram;
      this.decalLoc = {
        xy: gl.getAttribLocation(q, "aXY"),
        uv: gl.getAttribLocation(q, "aUV"),
        ...Object.fromEntries(["uMVP", "uH", "uTex", "uAlpha"].map((n) => [n, gl.getUniformLocation(q, n)])),
      };
      const texture = gl.createTexture();
      gl.bindTexture(gl.TEXTURE_2D, texture);
      gl.pixelStorei(gl.UNPACK_ALIGNMENT, 4);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGBA, gl.RGBA, gl.UNSIGNED_BYTE, image);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      const out = [];
      for (const { x0, y0, x1, y1, u0, v0, u1, v1 } of quads) {
        const a = [this.X(x0), this.Y(y0), u0, v1];
        const b = [this.X(x1), this.Y(y0), u1, v1];
        const c = [this.X(x1), this.Y(y1), u1, v0];
        const d = [this.X(x0), this.Y(y1), u0, v0];
        out.push(...a, ...b, ...c, ...a, ...c, ...d);
      }
      const buffer = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(out), gl.STATIC_DRAW);
      this.decals = { texture, buffer, count: out.length / 4, alpha };
    }
  }

  // ---- the turning, by hand ----
  function steer(viewer, canvas, redraw, onTouch) {
    let drag = null;
    canvas.addEventListener("pointerdown", (event) => {
      drag = { x: event.clientX, y: event.clientY, az: viewer.view.az, el: viewer.view.el };
      canvas.setPointerCapture(event.pointerId);
      onTouch();
    });
    canvas.addEventListener("pointermove", (event) => {
      if (!drag) return;
      viewer.view.az = drag.az - (event.clientX - drag.x) * 0.008;
      viewer.view.el = Math.max(0.05, Math.min(1.5, drag.el + (event.clientY - drag.y) * 0.006));
      redraw();
    });
    const end = () => (drag = null);
    canvas.addEventListener("pointerup", end);
    canvas.addEventListener("pointercancel", end);
    canvas.addEventListener("wheel", (event) => {
      if (!event.ctrlKey) return; // a plain wheel scrolls the page; a pinch on a trackpad comes with ctrl
      event.preventDefault();
      viewer.view.zoom = Math.max(0.6, Math.min(8, viewer.view.zoom * Math.exp(-event.deltaY * 0.01)));
      onTouch();
      redraw();
    }, { passive: false });
    canvas.addEventListener("dblclick", () => {
      Object.assign(viewer.view, { az: -2.25, el: 0.6, zoom: 1 });
      redraw();
    });
  }

  // ---- the section beside the solid ----
  const NS = "http://www.w3.org/2000/svg";
  // ---- the fields the solvers found ----
  // values: bytes in base64, scaled to their largest value; a cross-section is y-major ([y][z]), a top view x-major
  const { centres, bytesOf } = SolidMath;
  // the colour of a field: the light of a mode in cyan going white, heat in orange going pale; faint is clear
  const paint = (kind, v) => {
    if (kind === "heat") {
      const stops = [[0, 110, 20, 50], [0.35, 220, 70, 45], [0.7, 255, 170, 70], [1, 255, 244, 205]];
      const u = Math.pow(v, 1.8); // the hot part of the range spread out, so that the heater stands out of its chimney
      let k = 1;
      while (k < stops.length - 1 && u > stops[k][0]) k += 1;
      const [a0, r0, g0, b0] = stops[k - 1];
      const [a1, r1, g1, b1] = stops[k];
      const f = Math.max(0, Math.min(1, (u - a0) / (a1 - a0)));
      return [r0 + (r1 - r0) * f, g0 + (g1 - g0) * f, b0 + (b1 - b0) * f, v < 0.02 ? 0 : Math.min(1, v * 1.5) * 215];
    }
    const w = v * v;
    return [94 + 161 * w, 231 + 24 * w, 245 + 10 * w, Math.min(1, v * 1.15) * 235];
  };
  // a field as a canvas, its top row the top of the field (and its data URL, for the section)
  function fieldCanvas(field, k = 0) {
    field._canvas = field._canvas || {};
    if (field._canvas[k]) return field._canvas[k];
    const ny = field.y[2];
    const nz = field.z[2];
    const bytes = bytesOf(field);
    const canvas = document.createElement("canvas");
    canvas.width = ny;
    canvas.height = nz;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(ny, nz);
    const plane = ny * nz;
    for (let i = 0; i < ny; i++) {
      for (let jj = 0; jj < nz; jj++) {
        let rgba;
        if (field.kind === "carriers") {
          // electrons blue, holes pink, by the log of their density; where both are few (the depletion) it stays dark
          // the colour runs from 10^16 to 10^18 per cm^3 (the bytes span 10^14 to 10^20): the junction shows dark
          const e = Math.min(1, Math.max(0, (bytes[2 * k * plane + i * nz + jj] / 255 - 1 / 3) * 3));
          const h = Math.min(1, Math.max(0, (bytes[(2 * k + 1) * plane + i * nz + jj] / 255 - 1 / 3) * 3));
          const s = e + h || 1;
          rgba = [(106 * e + 255 * h) / s, (165 * e + 127 * h) / s, (255 * e + 176 * h) / s, Math.max(e, h) * 240];
        } else rgba = paint(field.kind, bytes[i * nz + jj] / 255);
        img.data.set(rgba, ((nz - 1 - jj) * ny + i) * 4);
      }
    }
    ctx.putImageData(img, 0, 0);
    canvas._url = canvas.toDataURL("image/png");
    field._canvas[k] = canvas;
    return canvas;
  }
  // the light of a top view along the section, as a pane over the height of the silicon
  function lightCanvas(light) {
    const canvas = document.createElement("canvas");
    canvas.width = light.length;
    canvas.height = 4;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(light.length, 4);
    light.forEach((v, i) => {
      for (let j = 0; j < 4; j++) img.data.set(paint("mode", Math.pow(v, 0.8)), (j * light.length + i) * 4);
    });
    ctx.putImageData(img, 0, 0);
    return canvas;
  }
  // The section at the width of its panel, in pixels: across the line of the cut (s, micrometres from the pointer),
  // the layers it crosses and the field of the solver on its waveguide.  Without a field it shows 4 um across, as
  // tall as the stack; with one, it closes in on the field, at about true proportions.  over: a second field drawn
  // faintly over the first (the mode over the carriers).  It returns what the pane in the solid needs.
  function drawSection(svg, data, cut, field, k = 0, over = null) {
    const parts = cut.parts;
    const top = Math.max(...data.solids.map((s) => s.z1)) / 1000;
    const W = Math.max(300, Math.round(svg.clientWidth || 600));
    let yy = [-2, 2];
    let zz = [-0.3, top + 0.15];
    let shown = false;
    let note = "";
    let at = null; // where the field stands, in s
    let light = null;
    let image = null;
    let pane = { s: [-2, 2], z: [-0.3, top + 0.15] };
    if (field && field.kind === "top") {
      const n = 121;
      const ss = Array.from({ length: n }, (_, i) => -3 + (6 * i) / (n - 1));
      light = SolidMath.lightAlong(field, cut.p, cut.n, ss);
      if (light && Math.max(...light) > 0.02) {
        yy = [-3, 3];
        zz = [-0.3, 1.25];
        shown = true;
        const core = (data.solids.find((s) => s.key === "si_core") || { z1: 220 }).z1 / 1000;
        image = lightCanvas(light);
        pane = { s: [-3, 3], z: [0, core] };
      } else {
        light = null;
        note = `the ${field.label} was simulated from x = ${field.x[0].toFixed(1)} to ${field.x[1].toFixed(1)} µm`;
      }
    } else if (field) {
      const spots = centres(field, parts);
      if (spots.length) {
        at = spots.reduce((a, b) => (Math.abs(b) < Math.abs(a) ? b : a), spots[0]); // the waveguide under the pointer
        yy = [at + Math.max(field.y[0], -3), at + Math.min(field.y[1], 3)];
        zz = [Math.min(-0.3, field.z[0]), Math.max(field.kind === "heat" ? top + 0.15 : 0.37, field.z[1])];
        if (field.kind === "carriers") {
          // the junction is a tenth of a micrometre wide: close in on the core
          yy = [at - 1.2, at + 1.2];
          zz = [-0.12, 0.4];
        }
        shown = true;
        image = fieldCanvas(field, k);
        pane = { s: [at + Math.max(field.y[0], -2.5), at + Math.min(field.y[1], 2.5)], z: [field.z[0], field.z[1]] };
      } else {
        note = field.core.length === 1
          ? `the ${field.label} belongs to a strip ${field.core[0]} µm wide, and there is none under the pointer`
          : `the ${field.label} belongs to two strips ${field.core[0]} µm wide, ${field.core[1]} µm apart, and there are none under the pointer`;
      }
    }
    // the pane in the solid: a sheet of glass from below the top of the oxide to above the stack, 5 um across at most,
    // with the field drawn where it lies (so that it shows at true heights too, where the field is thin)
    const Z0 = -0.8;
    const Z1 = top + 0.3;
    const S0 = shown ? pane.s[0] : -2;
    const S1 = shown ? pane.s[1] : 2;
    const sheet = document.createElement("canvas");
    const res = 80; // pixels per micrometre
    sheet.width = Math.max(2, Math.round((S1 - S0) * res));
    sheet.height = Math.max(2, Math.round((Z1 - Z0) * res));
    if (shown && image) {
      const g = sheet.getContext("2d");
      g.imageSmoothingEnabled = true;
      if (light) {
        g.drawImage(image, 0, (Z1 - pane.z[1]) * res, sheet.width, (pane.z[1] - pane.z[0]) * res);
      } else {
        // the field over its own extent, placed in the sheet: its y from at + y0, its z from z0
        g.drawImage(image, (at + field.y[0] - S0) * res, (Z1 - field.z[1]) * res, (field.y[1] - field.y[0]) * res, (field.z[1] - field.z[0]) * res);
      }
    }
    image = sheet;
    pane = { s: [S0, S1], z: [Z0, Z1] };
    const span = yy[1] - yy[0];
    const kx = W / span; // pixels per micrometre across
    const H = 170;
    const zk = H / (zz[1] - zz[0]); // pixels per micrometre of height
    const px = (y) => (y - yy[0]) * kx;
    const pz = (z) => H - (z - zz[0]) * zk;
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
    svg.replaceChildren();
    const add = (name, attrs) => {
      const el = document.createElementNS(NS, name);
      for (const [a, v] of Object.entries(attrs)) el.setAttribute(a, typeof v === "number" ? v.toFixed(2) : v);
      svg.appendChild(el);
      return el;
    };
    const rect = (y0, y1, z0, z1, fill, cls) =>
      add("rect", { x: px(y0), width: Math.max(0.8, (y1 - y0) * kx), y: pz(z1), height: Math.max(0.8, (z1 - z0) * zk), fill, class: cls || "" });
    rect(yy[0], yy[1], zz[0], 0, "#8fa3d9", "sec-oxide");
    const carriers = shown && field.kind === "carriers"; // the silicon faint under them, so that they keep their colours
    for (const p of parts) for (const [a, b] of p.spans) rect(a, b, p.z0 / 1000, p.z1 / 1000, p.colour, carriers ? "sec-part sec-faint" : "sec-part");
    if (shown && at !== null) {
      const place = (f, img, cls, extra = {}) =>
        add("image", { href: img._url, x: px(at + f.y[0]), y: pz(f.z[1]), width: (f.y[1] - f.y[0]) * kx,
          height: (f.z[1] - f.z[0]) * zk, preserveAspectRatio: "none", class: cls, ...extra }); // fmt: skip
      place(field, fieldCanvas(field, k), carriers ? "sec-carriers" : "sec-field");
      if (over) place(over, fieldCanvas(over), "sec-field sec-over");
    }
    if (light) {
      // the light at the height of the silicon, and its profile above it
      const n = light.length;
      const dy = 6 / (n - 1);
      const core = (data.solids.find((s) => s.key === "si_core") || { z1: 220 }).z1 / 1000;
      light.forEach((v, i) => {
        if (v > 0.03) rect(-3 + i * dy - dy / 2, -3 + i * dy + dy / 2, 0, core, `rgba(190, 248, 255, ${Math.pow(v, 1.1).toFixed(3)})`, "sec-light");
      });
      const base = core + 0.25;
      const lift = zz[1] - base - 0.08;
      const d = light.map((v, i) => `${i ? "L" : "M"}${px(-3 + i * dy).toFixed(1)} ${pz(base + v * lift).toFixed(1)}`).join("");
      add("path", { d: `${d}L${px(3).toFixed(1)} ${pz(base).toFixed(1)}L${px(-3).toFixed(1)} ${pz(base).toFixed(1)}Z`, class: "sec-profile-fill" });
      add("path", { d, class: "sec-profile" });
    }
    // the pointer: where the line of the section passes under it
    add("path", { d: `M${px(0).toFixed(1)} 0V${H}`, class: "sec-pointer" });
    return { parts, stretch: zk / kx, shown, note, yy, image, pane };
  }

  // the light of the ring modulator, made from its numbers: the bus before the ring, the bus after it (what passes,
  // T), and the ring (what it holds, against what it holds at 0 V); bytes x-major over the window
  function ringLight(data, k) {
    const ring = data.ring;
    const [x0, y0, x1, y1] = data.window;
    const step = 0.08;
    const nx = Math.round((x1 - x0) / step) + 1;
    const ny = Math.round((y1 - y0) / step) + 1;
    const bytes = new Uint8Array(nx * ny);
    const sigma = ring.width * 0.36;
    const bus = 0.62;
    const held = Math.min(1, ring.stored[k] / ring.stored[0]);
    for (let ix = 0; ix < nx; ix++) {
      const x = x0 + ix * step;
      const pass = x < -2 ? 1 : x > 2 ? ring.T[k] : 1 + ((ring.T[k] - 1) * (x + 2)) / 4; // the coupling point at x = 0
      for (let iy = 0; iy < ny; iy++) {
        const y = y0 + iy * step;
        const db = y - ring.busY;
        const dr = Math.hypot(x - ring.centre[0], y - ring.centre[1]) - ring.radius;
        const v = bus * pass * Math.exp((-db * db) / (2 * sigma * sigma)) + held * Math.exp((-dr * dr) / (2 * sigma * sigma));
        bytes[ix * ny + iy] = Math.min(255, Math.round(255 * v));
      }
    }
    return { x: [x0, x0 + (nx - 1) * step, nx], y: [y0, y0 + (ny - 1) * step, ny], bytes };
  }

  // ---- a viewer in a chapter ----
  const calm = Boolean(window.COOKBOOK_CALM);
  for (const figure of document.querySelectorAll("[data-solid]")) {
    const key = figure.dataset.solid;
    const canvas = figure.querySelector("canvas");
    const stage = figure.querySelector(".solid-stage");
    let viewer = null;
    let frame = 0;
    let spin = !calm; // a slow turn until the reader takes over
    let last = 0;
    const redraw = () => {
      if (!frame) frame = requestAnimationFrame(tick);
    };
    const tick = (now) => {
      frame = 0;
      if (!viewer) return;
      if (spin && last) viewer.view.az += Math.min(0.05, (now - last) / 1000) * 0.12;
      last = now;
      viewer.draw();
      if (spin && visible) frame = requestAnimationFrame(tick);
    };
    let visible = false;
    const start = (data) => {
      try {
        viewer = new Viewer(canvas);
      } catch (error) {
        figure.classList.add("is-flat");
        return;
      }
      viewer.setSolid(data);
      const s = SolidMath.stretch(data);
      viewer.view.z = s;
      figure.querySelectorAll("[data-stretch-value]").forEach((el) => (el.textContent = `×${s}`));
      steer(viewer, canvas, redraw, () => {
        spin = false;
        figure.classList.add("is-touched");
      });
      // the layers that this device has: the chips of the bar
      const families = new Set(viewer.parts.map((p) => (p.family === "slab" ? "silicon" : p.family)));
      figure.querySelectorAll("[data-family]").forEach((chip) => {
        chip.hidden = !families.has(chip.dataset.family);
        chip.addEventListener("click", () => {
          const f = chip.dataset.family;
          const off = !viewer.view.hidden.has(f);
          if (off) viewer.view.hidden.add(f);
          else viewer.view.hidden.delete(f);
          chip.setAttribute("aria-pressed", String(!off));
          redraw();
        });
      });
      figure.querySelectorAll("[data-zoom]").forEach((button) =>
        button.addEventListener("click", () => {
          viewer.view.zoom = Math.max(0.6, Math.min(8, viewer.view.zoom * Number(button.dataset.zoom)));
          spin = false;
          redraw();
        }),
      );
      // the ring modulator: its light made from its numbers, at the voltage of the slider
      const ring = data.ring;
      const voltInput = figure.querySelector("[data-volt]");
      const ringReadout = figure.querySelector("[data-ring-readout]");
      let vk = 0;
      const lightRing = () => {
        if (!ring) return;
        const l = ringLight(data, vk);
        viewer.setLightBytes(l.x, l.y, l.bytes);
      };
      lightRing();
      if (viewer.light) {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "solid-light";
        chip.setAttribute("aria-pressed", "true");
        chip.innerHTML = '<i style="--c:#bff6ff"></i>light';
        chip.title = ring
          ? "the light in the bus and the ring at the laser wavelength, from the numbers of the chapter"
          : (data.fields.find((f) => f.kind === "top") || {}).source || "";
        chip.addEventListener("click", () => {
          viewer.view.light = !viewer.view.light;
          chip.setAttribute("aria-pressed", String(viewer.view.light));
          redraw();
        });
        figure.querySelector(".solid-chips").prepend(chip);
      }
      const apart = figure.querySelector("[data-apart]");
      apart.addEventListener("input", () => {
        viewer.view.explode = Number(apart.value);
        redraw();
      });
      const height = figure.querySelector("[data-true-height]");
      if (height) height.addEventListener("click", () => {
        const flat = height.getAttribute("aria-pressed") !== "true";
        height.setAttribute("aria-pressed", String(flat));
        viewer.view.z = flat ? 1 : s;
        redraw();
      });

      // ---- the section under the pointer ----
      const panel = figure.querySelector(".solid-section");
      const readout = figure.querySelector("[data-probe-at]");
      const fields = data.fields || [];
      const chooser = figure.querySelector("[data-sec-fields]");
      const source = figure.querySelector("[data-sec-source]");
      let chosen = null; // null: the shape alone; a field, once the reader or the first section has chosen one
      let picked = false;
      let held = null; // the point the reader clicked, while the section is held there
      let last = null; // the last point that had a section
      const applies = (f, place) => {
        if (!f.where) return true;
        const onRing = place && Math.abs(place.off) < 1.2;
        if (f.where === "ring") return Boolean(onRing);
        if (f.where === "pn") return Boolean(onRing && place.inPN);
        return !onRing; // the bus
      };
      const choices = [{ label: "shape", field: null }, ...fields.map((f) => ({ label: f.label, field: f }))];
      const chips = choices.map((c) => {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = c.label;
        b.setAttribute("aria-pressed", "false");
        b.addEventListener("click", () => {
          chosen = c.field;
          picked = true;
          if (last) probeAt(last, Boolean(held));
        });
        chooser.appendChild(b);
        return b;
      });
      chooser.hidden = fields.length === 0;
      const SUP = { "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹" };
      const fmt = (v, d = 2) => {
        if (v === 0 || Math.abs(v) >= 1e-3) return v.toFixed(d);
        const [m, e] = v.toExponential(1).split("e");
        return `${m} × 10${String(Number(e)).replace(/./g, (c) => SUP[c] || c)}`;
      };
      const ringText = (place) => {
        if (!ring) return "";
        const V = ring.V[vk];
        const where = place && Math.abs(place.off) < 1.2
          ? `on the ring, ${Math.round(((place.angle % 360) + 360) % 360)}° from +x${place.inPN ? ", in the PN section" : ", outside the PN section"}`
          : "on the bus";
        return `${where} · at ${V.toFixed(2)} V: Δn_eff ${fmt(ring.dneff[vk])}, carrier loss ${ring.loss[vk].toFixed(1)} dB/cm, resonance +${ring.shift[vk].toFixed(0)} pm`;
      };
      const showRing = () => {
        if (!ring || !ringReadout) return;
        ringReadout.innerHTML =
          `<b>${ring.V[vk].toFixed(2)} V</b> reverse: the resonance moves ${ring.shift[vk].toFixed(0)} pm (its width is ${ring.fwhm_pm.toFixed(0)} pm). ` +
          `A laser at ${ring.laser_nm.toFixed(3)} nm, the resonance at 0 V: <b>${Math.round(100 * ring.T[vk])} %</b> passes the bus, ` +
          `and the ring holds <b>${ring.stored[vk].toFixed(0)}×</b> the power of the bus. The mode itself hardly changes: n_eff moves by ${fmt(ring.dneff[vk])}.`;
      };
      function clearProbe() {
        viewer.setProbe(null);
        viewer.view.plane = null;
        panel.hidden = true;
        last = null;
        redraw();
      }
      function probeAt(p, hold) {
        const t = SolidMath.tangentAt(data, p);
        if (!t) {
          if (!hold) clearProbe();
          return false;
        }
        let n = [-t[1], t[0]];
        const place = ring ? SolidMath.ringPlace(ring, p) : null;
        if (place && Math.abs(place.off) < 1.2) n = ring.inward > 0 ? place.inward : [-place.inward[0], -place.inward[1]];
        else if (n[1] < -1e-9 || (Math.abs(n[1]) <= 1e-9 && n[0] < 0)) n = [-n[0], -n[1]];
        const parts = SolidMath.sectionLine(data, p, n);
        const usable = fields.filter((f) => applies(f, place));
        if (!picked || (chosen && !usable.includes(chosen))) {
          // the first field that has something to show here, until the reader chooses
          chosen = usable.find((f) => (f.kind === "top" ? SolidMath.lightAlong(f, p, n, [0]) !== null : centres(f, parts).length)) || null;
        }
        const cut = drawSection(panel.querySelector("svg"), data, { p, n, parts }, chosen, vk);
        chips.forEach((b, i) => {
          b.hidden = Boolean(choices[i].field) && !usable.includes(choices[i].field);
          b.setAttribute("aria-pressed", String(choices[i].field === chosen));
        });
        panel.hidden = false;
        const across = `${cut.yy[1] - cut.yy[0] < 5 ? (cut.yy[1] - cut.yy[0]).toFixed(1) : Math.round(cut.yy[1] - cut.yy[0])} µm across, heights ×${cut.stretch < 10 ? cut.stretch.toFixed(1) : Math.round(cut.stretch)}`;
        readout.textContent = `${hold ? "held at" : "at"} x = ${p[0].toFixed(2)}, y = ${p[1].toFixed(2)} µm · ${across}` +
          `${ring ? " · " + ringText(place) : ""} · under it: ${cut.parts.filter((q) => q.spans.some(([lo, hi]) => lo <= 0 && 0 <= hi)).map((q) => q.what).join(", ") || "nothing"}`; // fmt: skip
        source.textContent = chosen ? (cut.shown ? chosen.source : `Not here: ${cut.note}.`) : "";
        const a = [p[0] + cut.pane.s[0] * n[0], p[1] + cut.pane.s[0] * n[1]];
        const b = [p[0] + cut.pane.s[1] * n[0], p[1] + cut.pane.s[1] * n[1]];
        viewer.setProbe({ a, b, z0: cut.pane.z[0], z1: cut.pane.z[1], image: cut.shown ? cut.image : null, held: hold });
        viewer.view.plane = hold ? { c: p, n: t } : null;
        last = p;
        redraw();
        return true;
      }
      // the pointer: a section where it rests on a waveguide; a click holds it there and opens the solid along it,
      // a click beside the waveguides lets it go.  Turning the solid with the pointer down moves no section.
      let down = null;
      let queued = null;
      canvas.addEventListener("pointerdown", (event) => (down = { x: event.clientX, y: event.clientY }));
      canvas.addEventListener("pointermove", (event) => {
        if (held || event.buttons || event.pointerType !== "mouse") return;
        const box = canvas.getBoundingClientRect();
        if (!queued) {
          requestAnimationFrame(() => {
            const q = queued;
            queued = null;
            if (!held && q) {
              const p = viewer.pick(q[0], q[1]);
              if (p) probeAt(p, false);
              else clearProbe();
            }
          });
        }
        queued = [event.clientX - box.left, event.clientY - box.top];
        spin = false;
      });
      canvas.addEventListener("pointerleave", () => {
        if (!held) clearProbe();
      });
      canvas.addEventListener("pointerup", (event) => {
        if (!down || Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) return;
        const box = canvas.getBoundingClientRect();
        const p = viewer.pick(event.clientX - box.left, event.clientY - box.top);
        if (p && probeAt(p, true)) {
          held = p;
          figure.classList.add("is-holding");
        } else {
          held = null;
          figure.classList.remove("is-holding");
          clearProbe();
        }
      });
      figure.querySelector("[data-probe-off]").addEventListener("click", () => {
        held = null;
        figure.classList.remove("is-holding");
        clearProbe();
      });
      // for a check by script (website/tests and screenshots): hold the section at a point of the layout
      figure._probe = (p) => {
        held = p;
        figure.classList.add("is-holding");
        return probeAt(p, true);
      };
      if (voltInput && ring) {
        voltInput.closest("[data-volt-box]").hidden = false;
        voltInput.max = String(ring.V.length - 1);
        voltInput.addEventListener("input", () => {
          vk = Number(voltInput.value);
          figure.querySelector("[data-volt-value]").textContent = `${ring.V[vk].toFixed(2)} V`;
          lightRing();
          showRing();
          if (last) probeAt(last, Boolean(held));
          redraw();
        });
        showRing();
      }
      figure.classList.add("is-ready");
      redraw();
    };
    if (!("IntersectionObserver" in window)) {
      load(key, figure.dataset.src).then(start, () => figure.classList.add("is-flat"));
      continue;
    }
    let asked = false;
    new IntersectionObserver(
      (entries) => {
        visible = entries.some((e) => e.isIntersecting);
        if (visible && !asked) {
          asked = true;
          load(key, figure.dataset.src).then(start, () => figure.classList.add("is-flat"));
        }
        if (visible) redraw();
      },
      { rootMargin: "200px" },
    ).observe(stage);
  }

  // ---- the chip at the head of the device library ----
  //   the simulated devices at their true sizes on one die, the planned ones as dim drawings along its edges.  The
  //   levels of the process float apart, each on a sheet of glass; scrolling down brings them together into one
  //   chip.  A level named at the side, or a device named over its place, can be pointed at: a device lights a column
  //   through every level, and a click opens its chapter.
  const chipBox = document.querySelector("[data-chip3d]");
  const chipRaw = document.getElementById("chip3d-data");
  if (chipBox && chipRaw) {
    const spec = JSON.parse(chipRaw.textContent);
    const canvas = chipBox.querySelector("canvas");
    const labels = chipBox.querySelector(".chip3d-labels");
    let viewer = null;
    try {
      viewer = new Viewer(canvas);
    } catch (error) {
      chipBox.classList.add("is-flat");
    }
    const UNIT = 100;
    const [dx0, dy0, dx1, dy1] = spec.die;
    const levelOf = new Map();
    spec.levels.forEach((level, i) => level.rows.forEach((row) => levelOf.set(row, i)));
    function merge(list) {
      const solids = [];
      const implants = [];
      const beams = [];
      for (const { item, data } of list) {
        const cx = (data.window[0] + data.window[2]) / 2;
        const cy = (data.window[1] + data.window[3]) / 2;
        const sx = Math.round((data.window[0] - cx + item.at[0] - dx0) * UNIT);
        const sy = Math.round((data.window[1] - cy + item.at[1] - dy0) * UNIT);
        const shift = (a) => a.map((value, i) => value + (i % 2 ? sy : sx));
        for (const s of data.solids) solids.push({ ...s, faces: shift(s.faces), edges: shift(s.edges), level: levelOf.get(s.key) ?? 0, device: item.key });
        for (const imp of data.implants) implants.push({ ...imp, faces: shift(imp.faces), device: item.key });
        beams.push({ device: item.key, x0: sx, y0: sy, x1: sx + data.size[0], y1: sy + data.size[1] });
      }
      // the levels the chip uses, one above the other
      const used = [...new Set(solids.map((s) => s.level))].sort((a, b) => a - b);
      const rank = new Map(used.map((level, i) => [level, i]));
      for (const s of solids) s.rank = rank.get(s.level);
      solids.sort((a, b) => a.z0 - b.z0);
      const W = Math.round((dx1 - dx0) * UNIT);
      const H = Math.round((dy1 - dy0) * UNIT);
      const sheets = used.map((level, i) => {
        const mine = solids.filter((s) => s.level === level);
        return { key: spec.levels[level].key, rank: i, z: Math.min(...mine.map((s) => s.z0)), top: Math.max(...mine.map((s) => s.z1)), name: spec.levels[level].name };
      });
      return {
        unit: UNIT, window: spec.die, size: [W, H], solids, implants, fields: [], levels: used.length, sheets, beams,
        ground: { z0: -200, z1: 0, colour: "#8fa3d9", faces: [0, 0, W, 0, W, H, 0, 0, W, H, 0, H], edges: [0, 0, 0, H, 0, H, W, H, W, H, W, 0, W, 0, 0, 0], trenches: false },
      }; // fmt: skip
    }

    // the drawings of the planned devices, in one image, coloured as on their cards but lighter
    const GHOST_STYLE = ".m-si{fill:#93a2c8}.m-slab{fill:#3e4a72}.m-p{fill:#a081b4;opacity:.75}.m-n{fill:#6f8cc8;opacity:.75}.m-sin{fill:#86ad98}" +
      ".m-ge{fill:#a598c8}.m-heater{fill:#c09a86}.m-metal{fill:#c2ae86}.m-fibre{fill:#a4aed0}.m-ln{fill:#a19bd4}.m-pit{fill:#1a1f38}";
    function ghosts() {
      const cellW = 240;
      const cellH = 120;
      const cols = 4;
      const rows = Math.ceil(spec.ghosts.length / cols);
      const atlas = document.createElement("canvas");
      atlas.width = cellW * cols;
      atlas.height = cellH * rows;
      const ctx = atlas.getContext("2d");
      const quads = [];
      const jobs = spec.ghosts.map((g, i) => {
        const symbol = document.getElementById(g.symbol);
        if (!symbol) return Promise.resolve();
        const box = symbol.getAttribute("viewBox");
        const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="${box}"><style>${GHOST_STYLE}</style>${symbol.innerHTML}</svg>`;
        const col = i % cols;
        const row = Math.floor(i / cols);
        return new Promise((resolve) => {
          const img = new Image();
          img.onload = () => {
            const [, , bw, bh] = box.split(/\s+/).map(Number);
            const s = Math.min((cellW - 8) / bw, (cellH - 8) / bh);
            const w = bw * s;
            const h = bh * s;
            const ox = col * cellW + (cellW - w) / 2;
            const oy = row * cellH + (cellH - h) / 2;
            ctx.drawImage(img, ox, oy, w, h);
            const gw = g.w;
            const gh = (g.w * h) / w;
            quads.push({ x0: (g.x - gw / 2 - dx0) * UNIT, y0: (g.y - gh / 2 - dy0) * UNIT, x1: (g.x + gw / 2 - dx0) * UNIT, y1: (g.y + gh / 2 - dy0) * UNIT,
              u0: ox / atlas.width, v0: oy / atlas.height, u1: (ox + w) / atlas.width, v1: (oy + h) / atlas.height }); // fmt: skip
            resolve();
          };
          img.onerror = () => resolve();
          img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
        });
      });
      return Promise.all(jobs).then(() => ({ atlas, quads }));
    }

    if (viewer) {
      let data = null;
      let frame = 0;
      let last = 0;
      let clock = 0;
      let visible = false;
      let held = 0;
      let focusLevel = null;
      let focusDevice = "";
      const base = { az: -2.05, el: 0.5 };
      Object.assign(viewer.view, { ...base, zoom: 1.08 });
      viewer.fade = (i, part) => {
        if (focusLevel !== null) return part.kind === "ground" ? 0.5 : part.rank === focusLevel ? 1 : 0.14;
        if (focusDevice && part.device) return part.device === focusDevice ? 1 : 0.2;
        return 1;
      };
      // the labels: a level at the right of its glass, a device over its place
      const levelLabels = [];
      const deviceLabels = [];
      function makeLabels() {
        for (const sheet of data.sheets) {
          const span = document.createElement("span");
          span.className = "chip3d-level";
          const um = (nm) => (nm >= 1000 ? `${(nm / 1000).toFixed(2)} µm` : `${Math.round(nm)} nm`);
          span.innerHTML = `<b>${sheet.name}</b><i>${um(sheet.z)} to ${um(sheet.top)}</i>`;
          span.addEventListener("pointerenter", () => {
            focusLevel = sheet.rank;
            draw();
          });
          span.addEventListener("pointerleave", () => {
            focusLevel = null;
            draw();
          });
          labels.appendChild(span);
          levelLabels.push({ span, sheet });
        }
        for (const item of spec.devices) {
          const a = document.createElement("a");
          a.className = "chip3d-device";
          a.href = item.href;
          a.textContent = item.name;
          a.addEventListener("pointerenter", () => {
            focusDevice = item.key;
            viewer.beam = item.key;
            draw();
          });
          a.addEventListener("pointerleave", () => {
            focusDevice = "";
            viewer.beam = "";
            draw();
          });
          labels.appendChild(a);
          deviceLabels.push({ a, item });
        }
      }
      function placeLabels() {
        const v = viewer.view;
        const right = viewer.X(data.size[0]);
        const front = viewer.Y(0);
        for (const { span, sheet } of levelLabels) {
          const p = viewer.project([right, front, (sheet.z / 1000) * v.z + viewer.gap * v.explode * sheet.rank]);
          span.style.opacity = String(Math.max(0, Math.min(1, (v.explode - 0.55) * 3.5))); // gone before the levels crowd
          if (p) span.style.transform = `translate(${p[0].toFixed(1)}px, ${p[1].toFixed(1)}px)`;
        }
        const core = data.sheets.find((s) => s.key === "core") || data.sheets[0];
        for (const { a, item } of deviceLabels) {
          const p = viewer.project([item.at[0] - (dx0 + dx1) / 2, item.at[1] - (dy0 + dy1) / 2, (core.top / 1000) * v.z + viewer.gap * v.explode * core.rank]);
          if (p) a.style.transform = `translate(${p[0].toFixed(1)}px, ${p[1].toFixed(1)}px)`;
        }
      }
      // the levels part as the chip comes into view, and come together as it is scrolled past
      const apart = () => {
        if (calm) return 0.55;
        const r = chipBox.getBoundingClientRect();
        const middle = r.top + r.height / 2;
        return Math.max(0, Math.min(1, (middle - 0.05 * innerHeight) / (0.5 * innerHeight)));
      };
      function draw() {
        if (!data) return;
        viewer.view.explode = apart();
        viewer.draw();
        placeLabels();
      }
      const tick = (now) => {
        frame = 0;
        if (!visible) return;
        const dt = last ? Math.min(0.05, (now - last) / 1000) : 0;
        last = now;
        clock += dt;
        if (held > 0) held -= dt;
        else viewer.view.az = base.az + 0.14 * Math.sin(clock * 0.09); // a slow sway, nothing more
        draw();
        frame = requestAnimationFrame(tick);
      };
      const go = () => {
        if (calm) return draw();
        if (visible && !frame) {
          last = 0;
          frame = requestAnimationFrame(tick);
        }
      };
      steer(viewer, canvas, () => draw(), () => (held = 6));
      addEventListener("scroll", () => calm && draw(), { passive: true });
      addEventListener("resize", () => draw());
      Promise.all(spec.devices.map((item) => load(item.key, item.src).then((d) => ({ item, data: d }))))
        .then((list) => {
          data = merge(list);
          viewer.setSolid(data);
          viewer.view.z = SolidMath.stretch(data);
          makeLabels();
          chipBox.classList.add("is-ready");
          draw();
          return ghosts();
        })
        .then(({ atlas, quads }) => {
          viewer.setDecals(atlas, quads, 0.55);
          draw();
        })
        .catch(() => chipBox.classList.add("is-flat"));
      if (!("IntersectionObserver" in window)) {
        visible = true;
        go();
      } else {
        new IntersectionObserver((entries) => {
          visible = entries.some((e) => e.isIntersecting);
          go();
        }).observe(canvas);
      }
    }
  }

  window.CookbookSolid = { load, Viewer, SolidMath };
})();
