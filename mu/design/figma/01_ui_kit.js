// Мю (Mu) — UI Kit page (Figma Plugin API, run via use_figma in the file «Мю — UI»). Re-runnable: rebuilds the page.
let page = figma.root.children.find(p => p.name === "UI Kit");
if (!page) { page = figma.createPage(); page.name = "UI Kit"; }
await figma.setCurrentPageAsync(page);
for (const c of await figma.variables.getLocalVariableCollectionsAsync()) if (c.name.startsWith("Mu")) c.remove();
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: SERIF, style: SERIF_I}]) await figma.loadFontAsync(fn);

const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
// mirrors mu/mu/theme.py
const T = {
  "bg": ["#FAF9F5", "#262624"], "panel": ["#F0EEE6", "#1F1E1D"], "card": ["#FFFFFF", "#30302E"], "border": ["#E3DFD3", "#3E3D39"],
  "text": ["#141413", "#F4F2EC"], "muted": ["#6F6E69", "#A6A39A"], "faint": ["#A8A59C", "#6E6C66"], "accent": ["#D97757", "#D97757"],
  "on-accent": ["#FFFFFF", "#FFFFFF"], "selected": ["#E6E2D6", "#3A3936"], "hover": ["#E9E6DC", "#34332F"], "input": ["#FFFFFF", "#262624"],
  "canvas": ["#E9E6DC", "#191918"], "checker-a": ["#FFFFFF", "#3A3936"], "checker-b": ["#E8E5DD", "#2E2D2B"],
  "chroma": ["#00FF00", "#00FF00"], "skin": ["#FDE9DD", "#FDE9DD"], "hair": ["#F0A6C4", "#F0A6C4"], "ink": ["#141413", "#141413"],
};
const V = {Light: {}, Dark: {}};
const colIds = {};
for (const [mi, modeName] of ["Light", "Dark"].entries()) {
  const col = figma.variables.createVariableCollection("Mu — " + modeName);  // Starter plan: 1 mode per collection
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
  if (o.w) { t.textAutoResize = "HEIGHT"; t.resize(o.w, t.height); }
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

const root = al("VERTICAL", {name: "Мю — UI Kit", gap: 40, pad: 56, fill: "bg"});
root.resize(1600, 100); root.primaryAxisSizingMode = "AUTO"; root.counterAxisSizingMode = "FIXED";
const head = al("HORIZONTAL", {name: "Header", gap: 16, align: "CENTER"}); root.appendChild(head);
const icon = al("HORIZONTAL", {name: "App icon", radius: 40, fill: "accent", pad: [6, 30, 26, 30]}); head.appendChild(icon);
icon.appendChild(txt("μ", {family: SERIF, style: SERIF_I, size: 96, color: "on-accent"}));
const hc = al("VERTICAL", {name: "Title", gap: 4}); head.appendChild(hc);
hc.appendChild(txt("Мю — UI Kit", {family: SERIF, size: 40}));
hc.appendChild(txt("Оживление 2D-иллюстраций для витуберов · нарезка · риг · физика · студия · эфир · коллекции «Mu — Light» / «Mu — Dark»", {color: "muted", size: 15}));

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

// Tool button (cut / rig tools)
const toolBtns = ["Default", "Checked"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: 6, radius: 6, fill: s === "Checked" ? "selected" : null});
  c.appendChild(txt("⌇", {size: 16, color: s === "Checked" ? "accent" : "text"})); return c;
});
variants(toolBtns, grid).name = "Tool button";

// Workspace tab (Нарезка · Риг · Физика · Студия · Эфир · Гайдбук)
const wsTabs = ["Default", "Active"].map(s => {
  const c = comp("State=" + s, "VERTICAL", {pad: [6, 12, 4, 12], gap: 4});
  const t = txt("Риг", {color: s === "Active" ? "text" : "muted"}); t.name = "Title"; c.appendChild(t);
  const u = figma.createRectangle(); u.resize(40, 2); u.fills = s === "Active" ? [fill("accent")] : []; c.appendChild(u); return c;
});
variants(wsTabs, grid, {Title: "Риг"}).name = "Workspace tab";

// Home action card
const card = comp("Action card", "VERTICAL", {pad: [14, 16, 14, 16], radius: 14, fill: "card", stroke: "border", gap: 6});
card.counterAxisAlignItems = "MIN"; card.resize(300, card.height); card.counterAxisSizingMode = "FIXED";
card.appendChild(txt("▣", {size: 26, color: "accent"}));
const ct = txt("Модель из PSD", {family: SERIF, size: 17}); ct.name = "Title"; card.appendChild(ct);
card.appendChild(txt("Слои PSD становятся частями модели: сетки, роли и авто-риг готовы за минуту", {color: "muted", w: 268}));
grid.appendChild(card);

// Parts tree row (visibility + kind + name)
const partRows = [["Mesh", "▣", false], ["Warp", "▦", false], ["Rotation", "↻", false], ["Selected", "▣", true]].map(([s, g, sel]) => {
  const c = comp("Kind=" + s, "HORIZONTAL", {pad: [4, 8, 4, 8], gap: 8, radius: 5, fill: sel ? "selected" : null});
  c.resize(230, c.height); c.primaryAxisSizingMode = "FIXED";
  const cb = figma.createRectangle(); cb.resize(13, 13); cb.cornerRadius = 4; cb.fills = [fill("accent")]; c.appendChild(cb);
  c.appendChild(txt(g, {color: "muted"}));
  const n = txt(s === "Warp" ? "Голова: лицо" : s === "Rotation" ? "Голова: наклон" : "Левый глаз: белок"); n.name = "Name"; c.appendChild(n);
  return c;
});
variants(partRows, grid, {Name: "Часть"}).name = "Part row";

// Parameter row: name, value, key ◆, slider with key marks
const paramRows = ["Default", "Active", "Key here"].map(s => {
  const c = comp("State=" + s, "VERTICAL", {pad: [4, 8, 4, 8], gap: 4});
  c.resize(270, c.height); c.counterAxisSizingMode = "FIXED"; c.counterAxisAlignItems = "MIN";
  const top = al("HORIZONTAL", {name: "Top", gap: 6, align: "CENTER"});
  const n = txt("Поворот головы X", {style: s === "Active" ? "Semi Bold" : "Regular", color: s === "Active" ? "accent" : "text"}); n.name = "Name"; top.appendChild(n);
  top.appendChild(txt("30", {color: "muted"})); top.appendChild(txt(s === "Key here" ? "◆" : "◇", {color: s === "Key here" ? "accent" : "muted"}));
  c.appendChild(top);
  const track = figma.createFrame(); track.resize(254, 14); track.fills = []; track.clipsContent = false;
  const g = figma.createRectangle(); g.resize(254, 4); g.y = 5; g.cornerRadius = 2; g.fills = [fill("border")]; track.appendChild(g);
  const sub = figma.createRectangle(); sub.resize(190, 4); sub.y = 5; sub.cornerRadius = 2; sub.fills = [fill("accent")]; track.appendChild(sub);
  for (const x of [6, 127, 248]) { const k = figma.createRectangle(); k.resize(5, 5); k.rotation = 45; k.x = x; k.y = 12; k.fills = [fill("accent")]; track.appendChild(k); }
  const h = figma.createEllipse(); h.resize(12, 12); h.x = 184; h.y = 1; h.fills = [fill("card")]; h.strokes = [fill("accent")]; h.strokeWeight = 2; track.appendChild(h);
  c.appendChild(track);
  return c;
});
variants(paramRows, grid, {Name: "Параметр"}).name = "Parameter row";

// Deformer handles: warp grid + rotation handle
const warp = comp("Warp grid", "HORIZONTAL", {pad: 12});
const wv = figma.createVector();
let d = ""; for (let i = 0; i <= 4; i++) { d += `M 0 ${i * 30} C 40 ${i * 30 - 8} 80 ${i * 30 - 8} 120 ${i * 30} `; d += `M ${i * 30} 0 L ${i * 30} 120 `; }
wv.vectorPaths = [{windingRule: "NONE", data: d}]; wv.strokes = [fill("accent")]; wv.strokeWeight = 1.2; warp.appendChild(wv); grid.appendChild(warp);
const rot = comp("Rotation handle", "HORIZONTAL", {pad: 16});
const rv = figma.createVector(); rv.vectorPaths = [{windingRule: "NONE", data: "M 10 90 L 10 10"}]; rv.strokes = [fill("accent")]; rv.strokeWeight = 2; rot.appendChild(rv);
grid.appendChild(rot);

// Selection overlay (cut): marching dashed outline + tint
const selc = comp("Cut selection", "HORIZONTAL", {pad: 16});
const sel = figma.createEllipse(); sel.resize(120, 80); sel.fills = [{type: "SOLID", color: hex("#D97757"), opacity: 0.43}];
sel.strokes = [fill("accent")]; sel.dashPattern = [6, 4]; sel.strokeWeight = 1.5; selc.appendChild(sel); grid.appendChild(selc);

// Pose tile (thumbnail + name)
const tile = comp("Pose tile", "VERTICAL", {pad: 8, gap: 6, radius: 10, align: "CENTER"});
const th = figma.createFrame(); th.resize(72, 72); th.cornerRadius = 8; th.fills = [fill("canvas")]; tile.appendChild(th);
const pn = txt("Привет!"); pn.name = "Name"; tile.appendChild(pn); grid.appendChild(tile);

// Emotion row (live)
const emo = comp("Emotion row", "HORIZONTAL", {pad: [4, 8, 4, 8], gap: 6, radius: 5});
emo.appendChild(txt("1 ·", {color: "muted"})); emo.appendChild(txt("Улыбка")); grid.appendChild(emo);

// Buttons
const btn = comp("Button / Accent", "HORIZONTAL", {pad: [5, 12, 5, 12], radius: 7, fill: "accent"});
btn.appendChild(txt("★  Авто-риг", {style: "Semi Bold", color: "on-accent"})); grid.appendChild(btn);
const btn2 = comp("Button / Default", "HORIZONTAL", {pad: [5, 12, 5, 12], radius: 7, fill: "card", stroke: "border"});
btn2.appendChild(txt("Копировать в новый слой")); grid.appendChild(btn2);

await root.screenshot({scale: 0.5});
return {rootId: root.id, colIds, variables: Object.keys(T).length * 2};
