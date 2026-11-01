// Дельта (Delta) — UI Kit page (Figma Plugin API, run via use_figma in the file «Дельта — UI»). Re-runnable: rebuilds the page.
let page = figma.root.children.find(p => p.name === "UI Kit");
if (!page) { page = figma.createPage(); page.name = "UI Kit"; }
await figma.setCurrentPageAsync(page);
for (const c of await figma.variables.getLocalVariableCollectionsAsync()) if (c.name.startsWith("Delta")) c.remove();
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
const MONO = ["JetBrains Mono", "Roboto Mono", "Source Code Pro", "IBM Plex Mono"].find(f => has(f, "Regular")) || "Inter";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: SERIF, style: SERIF_I}, {family: MONO, style: "Regular"}]) await figma.loadFontAsync(fn);

const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
// mirrors delta/theme.py
const T = {
  "bg": ["#FAF9F5", "#262624"], "panel": ["#F0EEE6", "#1F1E1D"], "card": ["#FFFFFF", "#30302E"], "border": ["#E3DFD3", "#3E3D39"],
  "text": ["#141413", "#F4F2EC"], "muted": ["#6F6E69", "#A6A39A"], "faint": ["#A8A59C", "#6E6C66"], "accent": ["#D97757", "#D97757"],
  "on-accent": ["#FFFFFF", "#FFFFFF"], "selected": ["#E6E2D6", "#3A3936"], "hover": ["#E9E6DC", "#34332F"], "input": ["#FFFFFF", "#262624"],
  "canvas": ["#E9E6DC", "#191918"], "paper": ["#FFFFFF", "#FFFFFF"], "ink": ["#141413", "#141413"], "key": ["#D97757", "#D97757"],
  "track": ["#E3DFD3", "#3E3D39"], "layer-bar": ["#E8E2D2", "#34332F"], "skin": ["#F6C8B5", "#F6C8B5"],
};
const V = {Light: {}, Dark: {}};
const colIds = {};
for (const [mi, modeName] of ["Light", "Dark"].entries()) {
  const col = figma.variables.createVariableCollection("Delta — " + modeName);  // Starter plan: 1 mode per collection
  col.renameMode(col.modes[0].modeId, modeName);
  colIds[modeName] = col.id;
  for (const [name, vals] of Object.entries(T)) {
    const v = figma.variables.createVariable("color/" + name, col, "COLOR");
    v.setValueForMode(col.modes[0].modeId, hex(vals[mi]));
    V[modeName][name] = v;
  }
}
let MODE = "Light";
const fill = name => figma.variables.setBoundVariableForPaint({type: "SOLID", color: {r: 0, g: 0, b: 0}}, "color", V[MODE][name]);
function txt(chars, o = {}) {
  const t = figma.createText();
  t.fontName = {family: o.family || SANS, style: o.style || "Regular"};
  t.fontSize = o.size || 13; t.characters = chars; t.fills = [fill(o.color || "text")];
  return t;
}
function al(dir, o = {}) {
  const f = figma.createAutoLayout(dir, {itemSpacing: o.gap ?? 8});
  f.name = o.name || "Frame";
  f.fills = o.fill ? [fill(o.fill)] : [];
  if (o.pad !== undefined) { const [t, r, b, l] = Array.isArray(o.pad) ? o.pad : [o.pad, o.pad, o.pad, o.pad]; f.paddingTop = t; f.paddingRight = r; f.paddingBottom = b; f.paddingLeft = l; }
  if (o.radius) f.cornerRadius = o.radius;
  if (o.stroke) { f.strokes = [fill(o.stroke)]; f.strokeWeight = 1; }
  if (o.align) f.counterAxisAlignItems = o.align;
  return f;
}
function comp(name, dir, o = {}) {
  const c = figma.createComponent(); c.name = name; c.layoutMode = dir;
  c.primaryAxisSizingMode = "AUTO"; c.counterAxisSizingMode = "AUTO"; c.itemSpacing = o.gap ?? 8;
  const [t, r, b, l] = Array.isArray(o.pad) ? o.pad : [o.pad ?? 0, o.pad ?? 0, o.pad ?? 0, o.pad ?? 0];
  c.paddingTop = t; c.paddingRight = r; c.paddingBottom = b; c.paddingLeft = l;
  c.fills = o.fill ? [fill(o.fill)] : []; if (o.radius) c.cornerRadius = o.radius;
  if (o.stroke) { c.strokes = [fill(o.stroke)]; c.strokeWeight = 1; }
  c.counterAxisAlignItems = o.align || "CENTER";
  return c;
}
function variants(comps, parent, props = {}) {
  const set = figma.combineAsVariants(comps, parent);
  set.layoutMode = "HORIZONTAL"; set.primaryAxisSizingMode = "AUTO"; set.counterAxisSizingMode = "AUTO";
  set.itemSpacing = 16; set.paddingTop = set.paddingBottom = set.paddingLeft = set.paddingRight = 20;
  set.counterAxisAlignItems = "CENTER"; set.fills = [fill("bg")]; set.cornerRadius = 12;
  set.strokes = [fill("border")]; set.dashPattern = [4, 4];
  for (const [prop, def] of Object.entries(props)) {
    const key = set.addComponentProperty(prop, "TEXT", def);
    for (const v of set.children) { const t = v.findOne(n => n.type === "TEXT" && n.name === prop); if (t) t.componentPropertyReferences = {characters: key}; }
  }
  return set;
}


const root = al("VERTICAL", {name: "Дельта — UI Kit", gap: 40, pad: 56, fill: "bg"});
root.resize(1600, 100); root.primaryAxisSizingMode = "AUTO"; root.counterAxisSizingMode = "FIXED";
const head = al("HORIZONTAL", {name: "Header", gap: 16, align: "CENTER"}); root.appendChild(head);
const icon = al("HORIZONTAL", {name: "App icon", radius: 40, fill: "accent", pad: [10, 30, 22, 30]}); head.appendChild(icon);
icon.appendChild(txt("δ", {family: SERIF, style: SERIF_I, size: 96, color: "on-accent"}));
const hc = al("VERTICAL", {name: "Title", gap: 4}); head.appendChild(hc);
hc.appendChild(txt("Дельта — UI Kit", {family: SERIF, size: 40}));
hc.appendChild(txt("Рисование манги, персонажей и анимации · стиль Claude · коллекции «Delta — Light» / «Delta — Dark»", {color: "muted", size: 15}));

for (const modeName of ["Light", "Dark"]) {
  MODE = modeName;
  const row = al("HORIZONTAL", {name: "Swatches / " + modeName, gap: 10, pad: 20, radius: 14, fill: "bg", stroke: "border"});
  row.layoutWrap = "WRAP"; row.resize(1488, 100); row.primaryAxisSizingMode = "FIXED"; row.counterAxisSpacing = 12;
  for (const name of Object.keys(T)) {
    const sw = al("VERTICAL", {name, gap: 4});
    const r = figma.createRectangle(); r.resize(72, 44); r.cornerRadius = 8; r.fills = [fill(name)]; r.strokes = [fill("border")]; r.strokeWeight = 1;
    sw.appendChild(r); sw.appendChild(txt(name, {size: 10, color: "muted"})); row.appendChild(sw);
  }
  root.appendChild(row);
}
MODE = "Light";
const grid = al("HORIZONTAL", {name: "Components", gap: 24}); grid.layoutWrap = "WRAP"; grid.counterAxisSpacing = 24;
grid.resize(1488, 100); grid.primaryAxisSizingMode = "FIXED"; root.appendChild(grid);

const toolBtns = ["Default", "Active"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [5, 8, 5, 8], radius: 7, fill: s === "Active" ? "selected" : null, stroke: s === "Active" ? "accent" : null});
  c.appendChild(txt("🖌", {size: 16})); return c;
});
variants(toolBtns, grid).name = "Tool button";

const brushRows = [["Default", "✒  G-перо (тушь)"], ["Selected", "▮  Маркер"]].map(([s, label]) => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [5, 8, 5, 8], radius: 6, fill: s === "Selected" ? "selected" : null});
  c.resize(220, c.height); c.primaryAxisSizingMode = "FIXED"; const t = txt(label); t.name = "Name"; c.appendChild(t); return c;
});
variants(brushRows, grid, {Name: "Кисть"}).name = "Brush row";

const slider = comp("Brush slider", "HORIZONTAL", {gap: 8, align: "CENTER"});
slider.appendChild(txt("Размер", {w: 90}));
const tr = figma.createFrame(); tr.name = "Track"; tr.resize(140, 4); tr.cornerRadius = 2; tr.fills = [fill("border")];
const fl = figma.createRectangle(); fl.resize(60, 4); fl.cornerRadius = 2; fl.fills = [fill("accent")]; tr.appendChild(fl);
slider.appendChild(tr); slider.appendChild(txt("24 px", {color: "muted"})); grid.appendChild(slider);

const layerRows = [["Default", false], ["Selected", true], ["Hidden", false]].map(([s, sel]) => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [4, 8, 4, 8], gap: 8, radius: 6, fill: sel ? "selected" : null});
  c.resize(250, c.height); c.primaryAxisSizingMode = "FIXED";
  c.appendChild(txt("👁", {color: s === "Hidden" ? "faint" : "text"}));
  const th = figma.createRectangle(); th.resize(40, 30); th.fills = [fill("paper")]; th.strokes = [fill("border")]; th.strokeWeight = 1; c.appendChild(th);
  const col = al("VERTICAL", {name: "Text", gap: 0}); c.appendChild(col);
  const n = txt("Линии", {color: s === "Hidden" ? "muted" : "text"}); n.name = "Name"; col.appendChild(n); col.appendChild(txt("Обычный · 100%", {size: 11, color: "muted"}));
  return c;
});
variants(layerRows, grid, {Name: "Слой"}).name = "Layer row";

const keys = [["Ease", "key"], ["Current", "text"], ["Hold", "key"]].map(([s, col]) => {
  const c = comp("Kind=" + s, "HORIZONTAL", {pad: 6});
  if (s === "Hold") { const r = figma.createRectangle(); r.resize(9, 9); r.fills = [fill(col)]; c.appendChild(r); }
  else { const r = figma.createRectangle(); r.resize(8, 8); r.rotation = 45; r.fills = [fill(col)]; c.appendChild(r); }
  return c;
});
variants(keys, grid).name = "Keyframe";

const prop = comp("Property row", "HORIZONTAL", {gap: 8, pad: [3, 8, 3, 8]});
prop.resize(420, prop.height); prop.primaryAxisSizingMode = "FIXED";
prop.appendChild(txt("◆", {color: "accent"})); prop.appendChild(txt("Позиция X", {color: "muted", w: 110})); prop.appendChild(txt("60.0", {color: "accent"}));
grid.appendChild(prop);

const bubble = comp("Speech bubble", "HORIZONTAL", {pad: 0});
const bf = figma.createFrame(); bf.fills = []; bf.resize(200, 130);
const ell = figma.createEllipse(); ell.resize(190, 100); ell.fills = [fill("paper")]; ell.strokes = [fill("ink")]; ell.strokeWeight = 3; bf.appendChild(ell);
const tail = figma.createVector(); tail.vectorPaths = [{windingRule: "NONZERO", data: "M 60 88 L 40 128 L 92 96 Z"}]; tail.fills = [fill("paper")]; tail.strokes = [fill("ink")]; tail.strokeWeight = 3; bf.appendChild(tail);
const bt = txt("Привет!", {size: 18, color: "ink"}); bt.x = 62; bt.y = 38; bf.appendChild(bt);
bubble.appendChild(bf); grid.appendChild(bubble);

const panel = comp("Manga panel", "HORIZONTAL", {pad: 0});
const pf = figma.createRectangle(); pf.resize(180, 120); pf.fills = [fill("paper")]; pf.strokes = [fill("ink")]; pf.strokeWeight = 5; panel.appendChild(pf);
grid.appendChild(panel);

const tone = comp("Screentone", "HORIZONTAL", {pad: 0});
const tf = figma.createFrame(); tf.resize(120, 80); tf.fills = [fill("paper")]; tf.clipsContent = true;
for (let i = -2; i < 16; i++) for (let j = -2; j < 12; j++) { const d = figma.createEllipse(); d.resize(3, 3); d.x = i * 8 + (j % 2) * 4; d.y = j * 4 * 1.6; d.fills = [fill("ink")]; tf.appendChild(d); }
tone.appendChild(tf); grid.appendChild(tone);

const btn = comp("Button / Accent", "HORIZONTAL", {pad: [5, 12, 5, 12], radius: 7, fill: "accent"});
btn.appendChild(txt("Создать", {style: "Semi Bold", color: "on-accent"})); grid.appendChild(btn);

await root.screenshot({scale: 0.5});
return {rootId: root.id, colIds, variables: Object.keys(T).length * 2};
