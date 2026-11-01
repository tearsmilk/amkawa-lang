// Дзета (Zeta) — UI Kit page (Figma Plugin API, run via use_figma in the file «Дзета — UI»). Re-runnable: rebuilds the page.
let page = figma.root.children.find(p => p.name === "UI Kit");
if (!page) { page = figma.createPage(); page.name = "UI Kit"; }
await figma.setCurrentPageAsync(page);
for (const c of await figma.variables.getLocalVariableCollectionsAsync()) if (c.name.startsWith("Zeta")) c.remove();
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
// mirrors zeta/theme.py
const T = {
  "bg": ["#FAF9F5", "#262624"], "panel": ["#F0EEE6", "#1F1E1D"], "card": ["#FFFFFF", "#30302E"], "border": ["#E3DFD3", "#3E3D39"],
  "text": ["#141413", "#F4F2EC"], "muted": ["#6F6E69", "#A6A39A"], "faint": ["#A8A59C", "#6E6C66"], "accent": ["#D97757", "#D97757"],
  "on-accent": ["#FFFFFF", "#FFFFFF"], "selected": ["#E6E2D6", "#3A3936"], "hover": ["#E9E6DC", "#34332F"], "input": ["#FFFFFF", "#262624"],
  "canvas": ["#E9E6DC", "#191918"], "checker-a": ["#FFFFFF", "#3A3936"], "checker-b": ["#E8E5DD", "#2E2D2B"],
  "cel": ["#D97757", "#D97757"], "cel-empty": ["#C9C4B6", "#55534D"], "frame-current": ["#F6DED3", "#4A362D"],
  "onion-prev": ["#C8463C", "#C8463C"], "onion-next": ["#3C6EC8", "#3C6EC8"],
};
const V = {Light: {}, Dark: {}};
const colIds = {};
for (const [mi, modeName] of ["Light", "Dark"].entries()) {
  const col = figma.variables.createVariableCollection("Zeta — " + modeName);  // Starter plan: 1 mode per collection
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


const root = al("VERTICAL", {name: "Дзета — UI Kit", gap: 40, pad: 56, fill: "bg"});
root.resize(1600, 100); root.primaryAxisSizingMode = "AUTO"; root.counterAxisSizingMode = "FIXED";
const head = al("HORIZONTAL", {name: "Header", gap: 16, align: "CENTER"}); root.appendChild(head);
head.appendChild(txt("ζ", {family: SERIF, style: SERIF_I, size: 64, color: "accent"}));
const hc = al("VERTICAL", {name: "Title", gap: 4}); head.appendChild(hc);
hc.appendChild(txt("Дзета — UI Kit", {family: SERIF, size: 40}));
hc.appendChild(txt("Пиксель-арт и анимация · стиль Claude · токены в коллекциях «Zeta — Light» и «Zeta — Dark»", {color: "muted", size: 15}));

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

// pixel helper: draws a text mask as 1-unit squares
function pixels(mask, unit, colors, name) {
  const rows = mask.trim().split("\n");
  const f = figma.createFrame(); f.name = name; f.fills = []; f.resize(rows[0].length * unit, rows.length * unit);
  rows.forEach((row, y) => [...row].forEach((ch, x) => {
    if (colors[ch]) { const r = figma.createRectangle(); r.resize(unit, unit); r.x = x * unit; r.y = y * unit; r.fills = [fill(colors[ch])]; f.appendChild(r); }
  }));
  return f;
}
const ZETA = `
...##########...
...##########...
.......####.....
......###.......
.....###........
....###.........
...###..........
...##...........
..###...........
..##............
..##............
..###...........
...#########....
....#########...
..........###...
...........##...
..........###...
.........###....
........##......`;
const logoRow = al("HORIZONTAL", {name: "Logo", gap: 24, align: "CENTER", pad: 24, radius: 14, fill: "card", stroke: "border"}); root.appendChild(logoRow);
const tile = al("HORIZONTAL", {name: "App icon", radius: 44, fill: "accent", pad: 34}); tile.appendChild(pixels(ZETA, 8, {"#": "on-accent"}, "ζ pixel")); logoRow.appendChild(tile);
logoRow.appendChild(txt("Иконка: пиксельная ζ (16×19, штрих 2 px) на терракотовом скруглённом квадрате", {color: "muted", size: 14}));

const grid = al("HORIZONTAL", {name: "Components", gap: 24}); grid.layoutWrap = "WRAP"; grid.counterAxisSpacing = 24;
grid.resize(1488, 100); grid.primaryAxisSizingMode = "FIXED"; root.appendChild(grid);

// Tool button
const toolBtns = ["Default", "Active"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [6, 11, 6, 11], radius: 7, fill: s === "Active" ? "selected" : null, stroke: s === "Active" ? "accent" : null});
  c.appendChild(pixels("..........##\n.........#oo#\n........#oo#.\n.......#oo#..\n......#oo#...\n.....#oo#....\n....#oo#.....\n...#oo#......\n..#oo#.......\n..##.........", 2, {"#": "text", "o": "accent"}, "pencil"));
  return c;
});
variants(toolBtns, grid).name = "Tool button";

// Colour swatches
const sw = comp("Colour swatches", "HORIZONTAL", {pad: 6, gap: 0});
const back = figma.createRectangle(); back.resize(30, 30); back.fills = [fill("text")]; back.strokes = [fill("border")]; back.strokeWeight = 1;
const front = figma.createRectangle(); front.resize(30, 30); front.fills = [fill("accent")]; front.strokes = [fill("border")]; front.strokeWeight = 1;
const swf = figma.createFrame(); swf.fills = []; swf.resize(50, 50); swf.appendChild(back); back.x = 18; back.y = 18; swf.appendChild(front); front.x = 2; front.y = 2;
sw.appendChild(swf); sw.appendChild(txt("⇄", {color: "muted"})); grid.appendChild(sw);

// Palette cell
const cells = ["Default", "Primary", "Add"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: 0});
  const r = figma.createRectangle(); r.resize(16, 16);
  if (s === "Add") { r.fills = []; r.strokes = [fill("muted")]; r.dashPattern = [2, 2]; r.strokeWeight = 1; }
  else { r.fills = [fill(s === "Primary" ? "accent" : "cel-empty")]; if (s === "Primary") { r.strokes = [fill("text")]; r.strokeWeight = 2; } }
  c.appendChild(r); return c;
});
variants(cells, grid).name = "Palette cell";

// Timeline cel
const cels = [["Filled", "cel", null], ["Empty", null, "cel-empty"], ["Current", "cel", null]].map(([s, f, st]) => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: 7, fill: s === "Current" ? "frame-current" : null});
  const e = figma.createEllipse(); e.resize(s === "Empty" ? 7 : 9, s === "Empty" ? 7 : 9);
  e.fills = f ? [fill(f)] : []; if (st) { e.strokes = [fill(st)]; e.strokeWeight = 1; }
  c.appendChild(e); return c;
});
variants(cels, grid).name = "Timeline cel";

// Layer row
const lrows = [["Visible", "●", "text", null], ["Hidden", "○", "faint", null], ["Selected", "●", "text", "selected"], ["Locked", "●", "text", null]].map(([s, eye, col, bg]) => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [4, 8, 4, 8], gap: 10, fill: bg});
  c.resize(190, c.height); c.primaryAxisSizingMode = "FIXED";
  c.appendChild(txt(eye, {color: col})); c.appendChild(txt(s === "Locked" ? "🔒" : "·", {color: "faint"}));
  const t = txt("Слизень", {color: s === "Hidden" ? "muted" : "text"}); t.name = "Name"; c.appendChild(t);
  return c;
});
variants(lrows, grid, {Name: "Слой"}).name = "Layer row";

// Tag
const tag = comp("Tag", "HORIZONTAL", {pad: [1, 6, 1, 6], fill: "accent"}); tag.resize(96, 14); tag.primaryAxisSizingMode = "FIXED";
tag.appendChild(txt("прыжок", {size: 10, color: "on-accent"})); grid.appendChild(tag);

// Option (context bar)
const opt = comp("Context option", "HORIZONTAL", {gap: 6});
opt.appendChild(txt("Кисть", {color: "muted"}));
const ob = al("HORIZONTAL", {name: "Spin", pad: [3, 8, 3, 8], radius: 6, fill: "input", stroke: "border"}); ob.appendChild(txt("1 px")); opt.appendChild(ob);
grid.appendChild(opt);

// Button
const btn = comp("Button / Accent", "HORIZONTAL", {pad: [5, 12, 5, 12], radius: 7, fill: "accent"});
btn.appendChild(txt("Создать", {style: "Semi Bold", color: "on-accent"})); grid.appendChild(btn);

await root.screenshot({scale: 0.5});
return {rootId: root.id, colIds, variables: Object.keys(T).length * 2};
