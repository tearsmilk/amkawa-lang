// Альфа (Alpha) — UI Kit page (Figma Plugin API, run via use_figma in the file «Альфа — UI»). Re-runnable: rebuilds the page.
let page = figma.root.children.find(p => p.name === "UI Kit");
if (!page) { page = figma.createPage(); page.name = "UI Kit"; }
await figma.setCurrentPageAsync(page);
for (const c of await figma.variables.getLocalVariableCollectionsAsync()) if (c.name.startsWith("Alpha")) c.remove();
for (const n of [...page.children]) n.remove();

const fonts = await figma.listAvailableFontsAsync();
const has = (fam, style) => fonts.some(f => f.fontName.family === fam && f.fontName.style === style);
const SANS = "Inter";
const SERIF = ["Source Serif 4", "Lora", "Merriweather", "Playfair Display"].find(f => has(f, "Regular")) || "Inter";
const SERIF_I = has(SERIF, "Italic") ? "Italic" : "Regular";
for (const fn of [{family: SANS, style: "Regular"}, {family: SANS, style: "Medium"}, {family: SANS, style: "Semi Bold"},
                  {family: SERIF, style: "Regular"}, {family: SERIF, style: SERIF_I}]) await figma.loadFontAsync(fn);

const hex = h => { h = h.replace("#", ""); return {r: parseInt(h.slice(0,2),16)/255, g: parseInt(h.slice(2,4),16)/255, b: parseInt(h.slice(4,6),16)/255}; };
// mirrors alpha/alpha/theme.py
const T = {
  "bg": ["#FAF9F5", "#262624"], "panel": ["#F0EEE6", "#1F1E1D"], "card": ["#FFFFFF", "#30302E"], "border": ["#E3DFD3", "#3E3D39"],
  "text": ["#141413", "#F4F2EC"], "muted": ["#6F6E69", "#A6A39A"], "faint": ["#A8A59C", "#6E6C66"], "accent": ["#D97757", "#D97757"],
  "on-accent": ["#FFFFFF", "#FFFFFF"], "selected": ["#E6E2D6", "#3A3936"], "hover": ["#E9E6DC", "#34332F"], "input": ["#FFFFFF", "#262624"],
  "sidebar": ["#F0EEE6", "#1F1E1D"], "list": ["#F0EEE6", "#1F1E1D"], "overdue": ["#D64545", "#E05A5A"],
  "due-soon": ["#E8B23A", "#E8B23A"], "done": ["#4E8A5A", "#7BB487"], "board-a": ["#D97757", "#D97757"], "board-b": ["#C6613F", "#C6613F"],
  "l-green": ["#7BA05B", "#7BA05B"], "l-yellow": ["#E8B23A", "#E8B23A"], "l-orange": ["#E08A4A", "#E08A4A"], "l-red": ["#D6584B", "#D6584B"],
  "l-purple": ["#9B7BC4", "#9B7BC4"], "l-blue": ["#5B8CC4", "#5B8CC4"], "l-sky": ["#5DAFC4", "#5DAFC4"], "white": ["#FFFFFF", "#FFFFFF"], "ink": ["#141413", "#141413"],
};
const V = {Light: {}, Dark: {}};
const colIds = {};
for (const [mi, modeName] of ["Light", "Dark"].entries()) {
  const col = figma.variables.createVariableCollection("Alpha — " + modeName);  // Starter plan: 1 mode per collection
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


// a card face like alpha/widgets.py CardFace: cover?, labels, title, badges, avatars
function cardFace(o = {}) {
  const c = al("VERTICAL", {name: "Card / " + (o.title || "Карточка"), gap: 6, pad: [o.cover ? 0 : 8, 8, 8, 8], radius: 9, fill: "card", stroke: "border"});
  c.resize(256, 40); c.primaryAxisSizingMode = "AUTO"; c.counterAxisSizingMode = "FIXED"; c.counterAxisAlignItems = "MIN"; c.clipsContent = true;
  if (o.cover) { const cv = figma.createRectangle(); cv.resize(256, 30); cv.fills = [fill(o.cover)]; cv.layoutAlign = "STRETCH"; c.appendChild(cv); c.paddingTop = 0; }
  if (o.labels) { const lr = al("HORIZONTAL", {name: "Labels", gap: 4}); for (const [t, col] of o.labels) { const l = al("HORIZONTAL", {name: t, pad: [1, 8, 1, 8], radius: 4, fill: col}); l.appendChild(txt(t, {size: 11, style: "Semi Bold", color: "white"})); lr.appendChild(l); } c.appendChild(lr); }
  const t = txt(o.title || "Карточка", {size: 13, w: 238}); t.name = "Title"; c.appendChild(t);
  if (o.due || o.badges || o.avatars) {
    const br = al("HORIZONTAL", {name: "Badges", gap: 6, align: "CENTER"});
    if (o.due) { const d = al("HORIZONTAL", {name: "Due", pad: [2, 6, 2, 6], radius: 4, fill: o.dueFill || null}); d.appendChild(txt("◷ " + o.due, {size: 11, color: o.dueFill ? (o.dueFill === "due-soon" ? "ink" : "white") : "muted"})); br.appendChild(d); }
    for (const b of o.badges || []) br.appendChild(txt(b, {size: 11, color: "muted"}));
    for (const [ini, col] of o.avatars || []) { const a = al("HORIZONTAL", {name: "Avatar " + ini, radius: 11, fill: col, pad: [3, 4, 3, 4]}); a.appendChild(txt(ini, {size: 9, style: "Semi Bold", color: "white"})); br.appendChild(a); }
    c.appendChild(br);
  }
  return c;
}
function listColumn(name, cards, count) {
  const col = al("VERTICAL", {name: "List / " + name, gap: 8, pad: [8, 8, 8, 8], radius: 12, fill: "list"});
  col.resize(272, 40); col.primaryAxisSizingMode = "AUTO"; col.counterAxisSizingMode = "FIXED";
  const h = al("HORIZONTAL", {name: "Header", align: "CENTER"}); h.resize(256, 24); h.primaryAxisSizingMode = "FIXED"; h.primaryAxisAlignItems = "SPACE_BETWEEN";
  h.appendChild(txt(name, {style: "Semi Bold"})); h.appendChild(txt((count ?? cards.length) + "   •••", {size: 11, color: "muted"})); col.appendChild(h);
  for (const c of cards) col.appendChild(cardFace(c));
  col.appendChild(txt("+  Добавить карточку", {color: "muted"}));
  return col;
}

const root = al("VERTICAL", {name: "Альфа — UI Kit", gap: 40, pad: 56, fill: "bg"});
root.resize(1600, 100); root.primaryAxisSizingMode = "AUTO"; root.counterAxisSizingMode = "FIXED";
const head = al("HORIZONTAL", {name: "Header", gap: 16, align: "CENTER"}); root.appendChild(head);
const icon = al("HORIZONTAL", {name: "App icon", radius: 40, fill: "accent", pad: [6, 30, 26, 30]}); head.appendChild(icon);
icon.appendChild(txt("α", {family: SERIF, style: SERIF_I, size: 96, color: "on-accent"}));
const hc = al("VERTICAL", {name: "Title", gap: 4}); head.appendChild(hc);
hc.appendChild(txt("Альфа — UI Kit", {family: SERIF, size: 40}));
hc.appendChild(txt("Канбан-доски в духе Trello, локально · списки · карточки · виды · автоматизация · коллекции «Alpha — Light» / «Alpha — Dark»", {color: "muted", size: 15}));

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

// Card variants
const cards = [
  ["Plain", {title: "Собрать референсы"}],
  ["Labels + members", {title: "Сверстать шапку", labels: [["Срочно", "l-red"]], due: "18 окт, 15:54", dueFill: "due-soon", badges: ["≡"], avatars: [["Я", "accent"], ["МА", "l-green"]]}],
  ["Overdue", {title: "Форма обратной связи", labels: [["Баг", "l-purple"]], due: "17 окт", dueFill: "overdue"}],
  ["Done", {title: "Логотип", due: "12 окт", dueFill: "done", badges: ["☑ 3/3"]}],
  ["Cover", {title: "Проверить на мобильных", cover: "l-sky", labels: [["Важно", "l-orange"]]}],
].map(([v, o]) => { const c = comp("State=" + v, "VERTICAL", {pad: 0}); c.appendChild(cardFace(o)); return c; });
variants(cards, grid).name = "Card";

// List column
const lc = comp("List column", "VERTICAL", {pad: 0}); lc.appendChild(listColumn("В работе", [{title: "Новый логотип", avatars: [["АП", "l-blue"]]}, {title: "Тексты для разделов", due: "21 окт", badges: ["💬 1", "☑ 1/3"]}])); grid.appendChild(lc);

// Label pills
const pills = comp("Label pills", "HORIZONTAL", {pad: 12, gap: 6});
for (const [n, c] of [["Зелёный", "l-green"], ["Жёлтый", "l-yellow"], ["Оранжевый", "l-orange"], ["Красный", "l-red"], ["Фиолетовый", "l-purple"], ["Синий", "l-blue"], ["Голубой", "l-sky"]]) {
  const l = al("HORIZONTAL", {name: n, pad: [3, 10, 3, 10], radius: 4, fill: c}); l.appendChild(txt(n, {size: 11, style: "Semi Bold", color: "white"})); pills.appendChild(l);
}
grid.appendChild(pills);

// Board tile
const tiles = ["Board", "Template", "Create"].map(v => {
  const t = comp("Kind=" + v, "VERTICAL", {pad: [10, 12, 10, 12], radius: 12, fill: v === "Create" ? "panel" : "board-a", gap: 30});
  t.resize(196, 104); t.primaryAxisSizingMode = "FIXED"; t.counterAxisSizingMode = "FIXED"; t.counterAxisAlignItems = v === "Create" ? "CENTER" : "MIN"; t.primaryAxisAlignItems = v === "Create" ? "CENTER" : "SPACE_BETWEEN";
  if (v === "Create") t.appendChild(txt("+  Создать доску"));
  else { t.appendChild(txt(v === "Board" ? "Запуск сайта" : "Канбан", {family: SERIF, size: 16, color: "white"})); t.appendChild(txt(v === "Board" ? "5 списков · 11 карточек" : "Шаблон", {size: 11, color: "white"})); }
  return t;
});
variants(tiles, grid).name = "Board tile";

// Composer
const compo = comp("Composer", "VERTICAL", {pad: 8, gap: 6, radius: 12, fill: "list"});
const inp = al("HORIZONTAL", {name: "Input", pad: 8, radius: 8, fill: "card", stroke: "border"}); inp.resize(240, 54); inp.primaryAxisSizingMode = "FIXED"; inp.counterAxisSizingMode = "FIXED";
inp.appendChild(txt("Введите название карточки…", {color: "faint"})); compo.appendChild(inp);
const cr = al("HORIZONTAL", {name: "Actions", gap: 8, align: "CENTER"}); const ab = al("HORIZONTAL", {name: "Add", pad: [5, 12, 5, 12], radius: 7, fill: "accent"}); ab.appendChild(txt("Добавить карточку", {style: "Semi Bold", color: "on-accent"})); cr.appendChild(ab); cr.appendChild(txt("✕")); compo.appendChild(cr);
grid.appendChild(compo);

// Popup (labels)
const pop = comp("Popup / Метки", "VERTICAL", {pad: [10, 12, 12, 12], gap: 6, radius: 12, fill: "card", stroke: "border"});
pop.resize(300, 40); pop.counterAxisSizingMode = "FIXED"; pop.counterAxisAlignItems = "MIN";
pop.appendChild(txt("Метки", {style: "Semi Bold", color: "muted"}));
for (const [n, c, on] of [["Срочно", "l-red", true], ["Важно", "l-orange", false], ["Баг", "l-purple", false]]) {
  const r = al("HORIZONTAL", {name: n, gap: 8, align: "CENTER"}); const cb = figma.createRectangle(); cb.resize(14, 14); cb.cornerRadius = 4; cb.fills = [fill(on ? "accent" : "input")]; cb.strokes = [fill("muted")]; cb.strokeWeight = 1; r.appendChild(cb);
  const l = al("HORIZONTAL", {name: "Pill", pad: [6, 10, 6, 10], radius: 4, fill: c}); l.resize(230, 28); l.primaryAxisSizingMode = "FIXED"; l.appendChild(txt(n, {style: "Semi Bold", color: "white"})); r.appendChild(l); pop.appendChild(r);
}
const nb = al("HORIZONTAL", {name: "Create", pad: [5, 12, 5, 12], radius: 7, fill: "card", stroke: "border"}); nb.appendChild(txt("Создать новую метку")); pop.appendChild(nb);
grid.appendChild(pop);

// Rule row
const rr = comp("Rule row", "HORIZONTAL", {pad: [10, 10, 10, 14], gap: 10, radius: 12, fill: "card", stroke: "border"});
rr.resize(720, 40); rr.primaryAxisSizingMode = "FIXED";
rr.appendChild(txt("⚡", {size: 16, color: "accent"}));
const rc = al("VERTICAL", {name: "Text", gap: 2}); rc.layoutGrow = 1;
rc.appendChild(txt("Когда карточка перемещена в список «Готово»: отметить выполненной, добавить метку «Готово»", {w: 520}));
rc.appendChild(txt("Срабатывало: 12 · последний раз 18 окт, 10:54", {size: 11, color: "muted"})); rr.appendChild(rc);
rr.appendChild(txt("☑ вкл    ✎    ⧉    🗑", {color: "muted"})); grid.appendChild(rr);

// Side button + due chips
const sb = comp("Side button", "HORIZONTAL", {pad: [6, 10, 6, 10], radius: 6, fill: "panel", gap: 6}); sb.resize(184, 30); sb.primaryAxisSizingMode = "FIXED";
sb.appendChild(txt("☑  Чек-лист")); grid.appendChild(sb);
const chips = ["later", "soon", "overdue", "done"].map(v => {
  const c = comp("State=" + v, "HORIZONTAL", {pad: [5, 10, 5, 10], radius: 7, fill: {later: "card", soon: "due-soon", overdue: "overdue", done: "done"}[v], stroke: v === "later" ? "border" : null});
  c.appendChild(txt("21 окт, 18:00" + {later: "", soon: "  Скоро", overdue: "  Просрочено", done: "  Выполнено"}[v], {color: v === "later" || v === "soon" ? "ink" : "white"})); return c;
});
variants(chips, grid).name = "Due chip";

await root.screenshot({scale: 0.5});
return {rootId: root.id, colIds, variables: Object.keys(T).length * 2};
