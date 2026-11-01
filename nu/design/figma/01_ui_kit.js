// Ню (Nu) — UI Kit page (Figma Plugin API, run via use_figma in the file «Ню — UI»). Re-runnable: rebuilds the page.
let page = figma.root.children.find(p => p.name === "UI Kit");
if (!page) { page = figma.createPage(); page.name = "UI Kit"; }
await figma.setCurrentPageAsync(page);
for (const c of await figma.variables.getLocalVariableCollectionsAsync()) if (c.name.startsWith("Nu")) c.remove();
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
// mirrors nu/theme.py
const T = {
  "bg": ["#FAF9F5", "#262624"], "sidebar": ["#F0EEE6", "#1F1E1D"], "activity": ["#E9E6DC", "#1A1918"], "card": ["#FFFFFF", "#30302E"],
  "border": ["#E3DFD3", "#3E3D39"], "text": ["#141413", "#F4F2EC"], "muted": ["#6F6E69", "#A6A39A"], "faint": ["#A8A59C", "#6E6C66"],
  "accent": ["#D97757", "#D97757"], "on-accent": ["#FFFFFF", "#FFFFFF"], "selected": ["#E6E2D6", "#3A3936"], "hover": ["#E9E6DC", "#34332F"],
  "input": ["#FFFFFF", "#262624"], "editor": ["#FFFFFF", "#262624"], "line-no": ["#B4B0A5", "#5E5C57"], "current-line": ["#F7F5EF", "#2C2B29"],
  "selection": ["#F6DED3", "#4A362D"], "find": ["#F7D9A8", "#5C4A2A"], "guide": ["#ECE9E0", "#33322F"], "terminal": ["#FFFFFF", "#1F1E1D"],
  "tab-inactive": ["#F0EEE6", "#1F1E1D"],
  "git-modified": ["#B5862E", "#E2C27A"], "git-added": ["#3E8E63", "#7BB487"], "git-deleted": ["#C2453E", "#E5736B"],
  "syn-keyword": ["#A0461F", "#E8916F"], "syn-string": ["#3E7C4F", "#9CC28A"], "syn-number": ["#8A4FC2", "#C3A6F0"],
  "syn-comment": ["#8A8780", "#8A877F"], "syn-function": ["#2E5E9E", "#8FB5E8"], "syn-class": ["#9A6B12", "#E2C27A"],
  "syn-builtin": ["#2B7C8C", "#7EC4C9"],
};
const V = {Light: {}, Dark: {}};
const colIds = {};
for (const [mi, modeName] of ["Light", "Dark"].entries()) {
  const col = figma.variables.createVariableCollection("Nu — " + modeName);  // Starter plan: 1 mode per collection
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

const root = al("VERTICAL", {name: "Ню — UI Kit", gap: 40, pad: 56, fill: "bg"});
root.resize(1600, 100); root.primaryAxisSizingMode = "AUTO"; root.counterAxisSizingMode = "FIXED";
const head = al("HORIZONTAL", {name: "Header", gap: 16, align: "CENTER"}); root.appendChild(head);
head.appendChild(txt("ν", {family: SERIF, style: SERIF_I, size: 64, color: "accent"}));
const hc = al("VERTICAL", {name: "Title", gap: 4}); head.appendChild(hc);
hc.appendChild(txt("Ню — UI Kit", {family: SERIF, size: 40}));
hc.appendChild(txt("Редактор кода · стиль Claude · токены в коллекциях «Nu — Light» и «Nu — Dark»", {color: "muted", size: 15}));

// ---- colour swatches
for (const modeName of ["Light", "Dark"]) {
  MODE = modeName;
  const row = al("HORIZONTAL", {name: "Swatches / " + modeName, gap: 10, pad: 20, radius: 14, fill: "bg", stroke: "border"});
  row.layoutWrap = "WRAP"; row.resize(1488, 100); row.primaryAxisSizingMode = "FIXED"; row.counterAxisSpacing = 12;
  for (const name of Object.keys(T)) {
    const sw = al("VERTICAL", {name, gap: 4});
    const r = figma.createRectangle(); r.resize(72, 44); r.cornerRadius = 8; r.fills = [fill(name)]; r.strokes = [fill("border")]; r.strokeWeight = 1;
    sw.appendChild(r); sw.appendChild(txt(name, {size: 10, color: "muted"}));
    row.appendChild(sw);
  }
  root.appendChild(row);
}
MODE = "Light";

// ---- type
const type = al("VERTICAL", {name: "Type ramp", gap: 10, pad: 24, radius: 14, fill: "card", stroke: "border"}); root.appendChild(type);
type.appendChild(txt("Заголовок — serif 30", {family: SERIF, size: 30}));
type.appendChild(txt("ПРОВОДНИК — section 11 semibold", {size: 11, style: "Semi Bold", color: "muted"}));
type.appendChild(txt("Интерфейс — Inter 13", {size: 13}));
type.appendChild(txt("def hello(): return 'код — mono 13'", {family: MONO, size: 13}));

const grid = al("HORIZONTAL", {name: "Components", gap: 24}); grid.layoutWrap = "WRAP"; grid.counterAxisSpacing = 24;
grid.resize(1488, 100); grid.primaryAxisSizingMode = "FIXED"; root.appendChild(grid);
const ids = {};

// Button
const btns = [["Accent", "accent", "on-accent", null], ["Secondary", "card", "text", "border"], ["Link", null, "accent", null]].map(([k, bg, fg, st]) => {
  const c = comp("Kind=" + k, "HORIZONTAL", {pad: [6, 14, 6, 14], radius: 8, fill: bg, stroke: st});
  const t = txt(k === "Link" ? "Открыть папку…" : k === "Accent" ? "Зафиксировать" : "Отмена", {color: fg, style: k === "Accent" ? "Semi Bold" : "Regular"}); t.name = "Label"; c.appendChild(t);
  return c;
});
ids.button = variants(btns, grid, {Label: "Кнопка"}).id; grid.children[grid.children.length - 1].name = "Button";

// Activity bar item
const acts = ["Default", "Active"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [11, 14, 11, 14], fill: s === "Active" ? "sidebar" : "activity"});
  if (s === "Active") { c.strokes = [fill("accent")]; c.strokeTopWeight = 0; c.strokeRightWeight = 0; c.strokeBottomWeight = 0; c.strokeLeftWeight = 2; }
  c.appendChild(txt("⧉", {size: 20, color: "muted"}));
  return c;
});
variants(acts, grid).name = "Activity item";

// Editor tab
const tabs = [["Active", false], ["Inactive", false], ["Modified", true]].map(([s, mod]) => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [8, 10, 8, 14], gap: 8, fill: s === "Active" ? "editor" : "tab-inactive"});
  c.strokes = [fill(s === "Active" ? "accent" : "border")]; c.strokeTopWeight = s === "Active" ? 2 : 0; c.strokeLeftWeight = 0; c.strokeBottomWeight = 0; c.strokeRightWeight = 1;
  c.appendChild(txt("py", {size: 10, style: "Semi Bold", color: "syn-function"}));
  const t = txt((mod ? "● " : "") + "terminal.py", {color: s === "Inactive" ? "muted" : "text"}); t.name = "Name"; c.appendChild(t);
  c.appendChild(txt("×", {size: 14, color: "muted"}));
  return c;
});
variants(tabs, grid).name = "Editor tab";

// Tree item
const tree = [["Folder", "▸  ▭", "nu", "text"], ["File", "py", "editor.py", "text"], ["Modified", "py", "ui.py", "git-modified"],
              ["Untracked", "JS", "app.js", "git-added"], ["Selected", "py", "terminal.py", "text"]].map(([s, icon, name, color]) => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [4, 10, 4, 10], gap: 8, radius: 5, fill: s === "Selected" ? "selected" : null});
  c.resize(220, c.height); c.primaryAxisSizingMode = "FIXED";
  c.appendChild(txt(icon, {size: 10, style: "Semi Bold", color: s === "Folder" ? "muted" : "syn-function"}));
  const t = txt(name, {color}); t.name = "Name"; c.appendChild(t);
  return c;
});
variants(tree, grid).name = "Tree item";

// Status bar item
const st = comp("Status item", "HORIZONTAL", {pad: [2, 8, 2, 8], radius: 4});
st.appendChild(txt("Стр 120, стлб 1", {size: 12, color: "muted"})); grid.appendChild(st);

// Input
const inp = comp("Input", "HORIZONTAL", {pad: [6, 10, 6, 10], radius: 7, fill: "input", stroke: "border"});
inp.resize(260, inp.height); inp.primaryAxisSizingMode = "FIXED";
inp.appendChild(txt("Найти", {color: "muted"})); grid.appendChild(inp);

// Find bar
const fb = comp("Find bar", "HORIZONTAL", {pad: [6, 8, 6, 8], gap: 6, radius: 9, fill: "card", stroke: "border"});
fb.appendChild(txt("›", {color: "muted"}));
const fi = al("HORIZONTAL", {name: "Query", pad: [4, 8, 4, 8], radius: 6, fill: "input", stroke: "accent"}); fi.appendChild(txt("term")); fb.appendChild(fi);
for (const s of ["Aa", "ab", ".*"]) fb.appendChild(txt(s, {size: 12, color: "muted"}));
fb.appendChild(txt("3 из 44", {size: 12, color: "muted"}));
for (const s of ["⌃", "⌄", "×"]) fb.appendChild(txt(s, {color: "muted"}));
grid.appendChild(fb);

// Palette item
const pis = ["Default", "Selected"].map(s => {
  const c = comp("State=" + s, "HORIZONTAL", {pad: [6, 10, 6, 10], gap: 10, radius: 6, fill: s === "Selected" ? "selected" : null});
  c.resize(420, c.height); c.primaryAxisSizingMode = "FIXED";
  const t = txt("Вид: Разделить редактор", {}); t.name = "Title"; c.appendChild(t);
  c.appendChild(txt("⌘\\", {size: 12, color: "muted"}));
  return c;
});
variants(pis, grid, {Title: "Команда"}).name = "Palette item";

// Code line (syntax)
const code = comp("Code line", "HORIZONTAL", {pad: [2, 10, 2, 0], gap: 0, fill: "current-line"});
const ln = txt("120", {family: MONO, color: "line-no"}); ln.textAlignHorizontal = "RIGHT"; ln.resize(40, ln.height); code.appendChild(ln);
const sp = figma.createFrame(); sp.fills = []; sp.resize(24, 4); code.appendChild(sp);
for (const [s, c] of [["def ", "syn-keyword"], ["hello", "syn-function"], ["(name): ", "text"], ["return ", "syn-keyword"],
                      ["f\"Привет, {name}\"", "syn-string"], ["  # ν", "syn-comment"]]) code.appendChild(txt(s, {family: MONO, color: c}));
grid.appendChild(code);

// Terminal line
const term = comp("Terminal line", "HORIZONTAL", {pad: [4, 10, 4, 10], gap: 0, fill: "terminal"});
for (const [s, c] of [["~/proj ", "syn-function"], ["% ", "muted"], ["python3 run.py", "text"]]) term.appendChild(txt(s, {family: MONO, color: c}));
const cur = figma.createRectangle(); cur.resize(8, 16); cur.fills = [fill("accent")]; cur.opacity = 0.7; term.appendChild(cur);
grid.appendChild(term);

// SCM row
const scm = comp("Git change", "HORIZONTAL", {pad: [5, 10, 5, 10], gap: 8, radius: 6});
scm.resize(260, scm.height); scm.primaryAxisSizingMode = "FIXED";
scm.appendChild(txt("py", {size: 10, style: "Semi Bold", color: "syn-function"}));
const sn = txt("nu/ui.py", {color: "git-modified"}); sn.layoutGrow = 1; scm.appendChild(sn);
scm.appendChild(txt("M", {style: "Semi Bold", color: "git-modified"}));
grid.appendChild(scm);

await root.screenshot({scale: 0.5});
return {rootId: root.id, colIds, fonts: {SERIF, MONO}, variables: Object.keys(T).length * 2};
