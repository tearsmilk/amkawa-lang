package milk.naovisual.menu;

import milk.naovisual.NaoVisual;
import milk.naovisual.core.config.ConfigManager;
import milk.naovisual.core.hud.HudEditorScreen;
import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.*;
import milk.naovisual.core.theme.Theme;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.Friends;
import milk.naovisual.modules.client.ThemeModule;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.screens.Screen;
import net.minecraft.client.input.CharacterEvent;
import net.minecraft.client.input.KeyEvent;
import net.minecraft.client.input.MouseButtonEvent;
import net.minecraft.network.chat.Component;
import org.lwjgl.glfw.GLFW;

import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.function.Consumer;
import java.util.function.IntConsumer;

/**
 * Главное меню. Рисуется в «дизайнерских» единицах 966×699 (в 3 раза больше классических 322×233)
 * и масштабируется под экран (не меньше 1.5× от классического размера).
 */
public class NaoMenuScreen extends Screen {
    public static final int DESIGN_W = 966, DESIGN_H = 699;
    private static final int SIDEBAR_W = 200, LIST_W = 300, PAD = 14, RADIUS = 14;
    // Желаемые множители шрифта в дизайнерских единицах; в init() пересчитываются так, чтобы итоговый масштаб
    // на экране был «чистым» (кратным 0,5 и не меньше 1) — иначе текст размывается и становится нечитаемым.
    private static final float TXT_D = 1.3f, SMALL_D = 1.1f, HEAD_D = 2.0f;
    private float TXT = TXT_D, SMALL = SMALL_D, HEAD = HEAD_D, LOGO = HEAD_D * 1.3f;

    private record Hit(int x, int y, int w, int h, IntConsumer onClick, Consumer<double[]> onDrag, Consumer<Double> onScroll, Runnable onRelease) {
        boolean contains(double px, double py) { return px >= x && px < x + w && py >= y && py < y + h; }
    }

    private final List<Hit> hits = new ArrayList<>();
    private Hit active;                 // удерживаемый элемент (ползунок, пикер)
    private float scale = 1f;
    private int ox, oy;                 // смещение меню на экране
    private final Anim open = new Anim(0f, 14f);
    private final Anim listScroll = new Anim(0f, 18f), settingsScroll = new Anim(0f, 18f);
    private float listMax, settingsMax;
    private double mouseX, mouseY;      // в дизайнерских единицах
    private boolean closing;

    private final TextField search = new TextField(null, 24);
    private final TextField friendField = new TextField(null, 16);
    private final TextField profileField = new TextField(null, 32);
    private TextField focused;
    private KeybindSetting binding;
    private final Set<ColorSetting> expandedColors = new HashSet<>();
    private final Screen parent;

    public NaoMenuScreen() { this(null); }

    public NaoMenuScreen(Screen parent) {
        super(Component.literal(NaoVisual.NAME));
        this.parent = parent;
    }

    public static NaoMenuScreen forModule(Module m) {
        MenuState.page = MenuState.Page.MODULES;
        MenuState.category = m.category();
        MenuState.selected = m;
        return new NaoMenuScreen();
    }

    @Override
    protected void init() {
        ModuleRegistry.get(ThemeModule.class).onMenuOpen();
        open.to(1f);
        float sx = (width - 16) / (float) DESIGN_W, sy = (height - 16) / (float) DESIGN_H;
        float fit = Math.max(0.5f, Math.min(1f, Math.min(sx, sy)));
        float half = (float) Math.floor(fit * 2f) / 2f;          // кратный 0,5 масштаб, если он не ужимает меню больше чем на 10 %
        scale = half >= fit * 0.9f ? half : fit;
        TXT = crisp(TXT_D); SMALL = crisp(SMALL_D); HEAD = crisp(HEAD_D); LOGO = crisp(HEAD_D * 1.3f);
        ox = Math.round((width - DESIGN_W * scale) / 2f);
        oy = Math.round((height - DESIGN_H * scale) / 2f);
    }

    public float menuScale() { return scale; }

    /** Множитель в дизайнерских единицах, дающий на экране чистый масштаб шрифта (см. Render2D.crispScale). */
    private float crisp(float design) { return Render2D.crispScale(design * scale) / scale; }

    // --- отрисовка ----------------------------------------------------------------------------------
    // Ваниль размывает фон один раз за кадр внутри renderBackground (второй вызов blurBeforeThisStratum —
    // IllegalStateException «Can only blur once per frame»), поэтому размытие только здесь, без градиента ванили.
    @Override
    public void renderBackground(GuiGraphics g, int mx, int my, float partial) {
        ThemeModule theme = ModuleRegistry.get(ThemeModule.class);
        if (theme.blur() && minecraft.level != null) g.blurBeforeThisStratum();
    }

    @Override
    public void render(GuiGraphics g, int mx, int my, float partial) {
        long nowNs = System.nanoTime();
        float dt = lastFrameNanos == 0 ? 0.016f : Math.min(0.1f, (nowNs - lastFrameNanos) / 1e9f);
        lastFrameNanos = nowNs;
        frameLerp = 1f - (float) Math.exp(-dt * 14f);
        Theme t = ThemeManager.current();
        ThemeModule theme = ModuleRegistry.get(ThemeModule.class);
        float a = open.get();
        if (closing && a < 0.02f) { minecraft.setScreen(parent); return; }
        g.fill(0, 0, width, height, ColorUtil.argb(Math.round(theme.dim() * a), 0, 0, 0));

        hits.clear();
        mouseX = (mx - ox) / scale;
        mouseY = (my - oy) / scale;

        float s = scale * (0.9f + 0.1f * Anim.easeOut(a));
        int cx = ox + Math.round(DESIGN_W * scale / 2f), cy = oy + Math.round(DESIGN_H * scale / 2f);
        g.pose().pushMatrix();
        g.pose().translate(cx, cy);
        g.pose().scale(s, s);
        g.pose().translate(-DESIGN_W / 2f, -DESIGN_H / 2f);

        int fade = Math.round(255 * Anim.easeOut(a));
        Render2D.shadow(g, 0, 0, DESIGN_W, DESIGN_H, RADIUS, Math.min(fade, 70));
        Render2D.roundedRect(g, 0, 0, DESIGN_W, DESIGN_H, RADIUS, withA(t.background, Math.min(fade, ColorUtil.alpha(t.background))));
        Render2D.roundedOutline(g, 0, 0, DESIGN_W, DESIGN_H, RADIUS, withA(t.border, fade));

        drawSidebar(g, t);
        switch (MenuState.page) {
            case MODULES -> { drawModuleList(g, t); drawSettings(g, t); }
            case FRIENDS -> drawFriends(g, t);
            case PROFILES -> drawProfiles(g, t);
        }
        g.pose().popMatrix();
    }

    private static int withA(int c, int a) { return ColorUtil.withAlpha(c, Math.min(ColorUtil.alpha(c), a)); }

    private void drawSidebar(GuiGraphics g, Theme t) {
        Render2D.roundedRect(g, 0, 0, SIDEBAR_W, DESIGN_H, RADIUS, t.panelAlt);
        g.fill(SIDEBAR_W - RADIUS, 0, SIDEBAR_W, DESIGN_H, t.panelAlt);
        g.fill(SIDEBAR_W, 0, SIDEBAR_W + 1, DESIGN_H, t.border);

        // логотип
        Render2D.textCrisp(g, "Nao", PAD + 4, PAD + 6, LOGO, t.text, false);
        Render2D.textCrisp(g, "Visual", PAD + 4 + Render2D.width("Nao") * LOGO, PAD + 6, LOGO, t.accent, false);
        Render2D.textCrisp(g, "v" + NaoVisual.version() + " • " + ConfigManager.profile(), PAD + 4, PAD + 34, SMALL, t.textMuted, false);

        int y = PAD + 60;
        for (ModuleCategory c : ModuleCategory.values()) {
            boolean sel = MenuState.page == MenuState.Page.MODULES && MenuState.category == c;
            boolean hover = hover(PAD, y, SIDEBAR_W - PAD * 2, 34);
            if (sel) Render2D.roundedRect(g, PAD, y, SIDEBAR_W - PAD * 2, 34, 9, ColorUtil.withAlpha(t.accent, 217));
            else if (hover) Render2D.roundedRect(g, PAD, y, SIDEBAR_W - PAD * 2, 34, 9, t.hover());
            int txt = sel ? 0xFFFFFFFF : t.text;
            Render2D.textCrisp(g, icon(c), PAD + 12, y + 10, TXT, sel ? 0xFFFFFFFF : t.accent, false);
            Render2D.textCrisp(g, c.title(), PAD + 34, y + 11, TXT, txt, false);
            int count = 0;
            for (Module m : ModuleRegistry.byCategory(c)) if (m.isEnabled()) count++;
            if (count > 0) Render2D.textCrisp(g, String.valueOf(count), SIDEBAR_W - PAD - 22, y + 11, TXT, sel ? 0xFFFFFFFF : t.textMuted, false);
            final ModuleCategory cat = c;
            hits.add(new Hit(PAD, y, SIDEBAR_W - PAD * 2, 34, b -> {
                MenuState.page = MenuState.Page.MODULES;
                if (MenuState.category != cat) { MenuState.category = cat; MenuState.selected = null; listScroll.snap(0); }
            }, null, null, null));
            y += 38;
        }

        // нижние кнопки
        int by = DESIGN_H - PAD - 34 * 3 - 8 * 2;
        sideButton(g, t, "✎  Редактор HUD", by, MenuState.page == null, () -> minecraft.setScreen(new HudEditorScreen(this)));
        sideButton(g, t, "♥  Друзья", by + 42, MenuState.page == MenuState.Page.FRIENDS, () -> MenuState.page = MenuState.Page.FRIENDS);
        sideButton(g, t, "▤  Профили", by + 84, MenuState.page == MenuState.Page.PROFILES, () -> MenuState.page = MenuState.Page.PROFILES);
    }

    private void sideButton(GuiGraphics g, Theme t, String label, int y, boolean sel, Runnable action) {
        boolean hover = hover(PAD, y, SIDEBAR_W - PAD * 2, 34);
        Render2D.roundedRect(g, PAD, y, SIDEBAR_W - PAD * 2, 34, 9, sel ? t.accentSoft : hover ? t.panel : 0);
        Render2D.roundedOutline(g, PAD, y, SIDEBAR_W - PAD * 2, 34, 9, sel ? soft(t.accent) : t.border);
        Render2D.textCrisp(g, label, PAD + 12, y + 11, TXT, t.text, false);
        hits.add(new Hit(PAD, y, SIDEBAR_W - PAD * 2, 34, b -> action.run(), null, null, null));
    }

    private static String icon(ModuleCategory c) {
        return switch (c) {
            case HUD -> "▣"; case VISUALS -> "◈"; case PARTICLES -> "✦"; case WORLD -> "◐"; case OTHER -> "⚙"; case CLIENT -> "♦";
        };
    }

    private List<Module> visibleModules() {
        List<Module> out = new ArrayList<>();
        String q = search.text.trim().toLowerCase(Locale.ROOT);
        if (q.isEmpty()) return ModuleRegistry.byCategory(MenuState.category);
        for (Module m : ModuleRegistry.all())
            if (m.displayName().toLowerCase(Locale.ROOT).contains(q) || m.id().toLowerCase(Locale.ROOT).contains(q) || m.title().toLowerCase(Locale.ROOT).contains(q)) out.add(m);
        return out;
    }

    private void drawModuleList(GuiGraphics g, Theme t) {
        int x0 = SIDEBAR_W + 1, w = LIST_W;
        g.fill(x0 + w, 0, x0 + w + 1, DESIGN_H, t.border);
        // поиск
        drawTextField(g, t, search, x0 + PAD, PAD, w - PAD * 2, 32, "Поиск…");
        String title = search.text.isBlank() ? MenuState.category.title() : "Результаты поиска";
        Render2D.textCrisp(g, title, x0 + PAD + 2, PAD + 44, SMALL, t.textMuted, false);

        int top = PAD + 62, bottom = DESIGN_H - PAD;
        List<Module> mods = visibleModules();
        int rowH = 58, gap = 8;
        listMax = Math.max(0, mods.size() * (rowH + gap) - (bottom - top));
        float sc = listScroll.get();
        Render2D.scissor(g, x0, top, w, bottom - top);
        int y = top - Math.round(sc);
        for (Module m : mods) {
            if (y + rowH >= top && y <= bottom) {
                boolean selected = MenuState.selected == m;
                boolean hover = hover(x0 + PAD, y, w - PAD * 2, rowH) && mouseY >= top && mouseY < bottom;
                Render2D.roundedRect(g, x0 + PAD, y, w - PAD * 2, rowH, 10, hover || selected ? t.panel : withA(t.panel, t.light ? 170 : 110));
                if (selected) Render2D.roundedOutline(g, x0 + PAD, y, w - PAD * 2, rowH, 10, soft(t.accent));
                Render2D.textCrisp(g, m.displayName(), x0 + PAD + 14, y + 12, TXT, t.text, false);
                Render2D.textCrisp(g, Render2D.trim(m.description(), (int) ((w - PAD * 2 - 90) / SMALL)), x0 + PAD + 14, y + 32, SMALL, t.textMuted, false);
                if (m.bind.isBound()) {
                    String k = m.bind.display();
                    int kw = (int) (Render2D.width(k) * SMALL) + 10;
                    Render2D.roundedRect(g, x0 + w - PAD - 74 - kw, y + 10, kw, 16, 5, t.panelAlt);
                    Render2D.textCrisp(g, k, x0 + w - PAD - 74 - kw + 5, y + 14, SMALL, t.textMuted, false);
                }
                drawSwitch(g, t, x0 + w - PAD - 60, y + rowH / 2 - 11, m.isEnabled(), m);
                final Module mod = m;
                hits.add(new Hit(x0 + w - PAD - 60, y, 46, rowH, b -> mod.toggle(), null, null, null));
                hits.add(new Hit(x0 + PAD, y, w - PAD * 2 - 60, rowH, b -> {
                    if (b == GLFW.GLFW_MOUSE_BUTTON_RIGHT) mod.toggle();
                    else { MenuState.selected = mod; settingsScroll.snap(0); }
                }, null, null, null));
            }
            y += rowH + gap;
        }
        Render2D.unscissor(g);
        hits.add(new Hit(x0, top, w, bottom - top, null, null, d -> listScroll.to(clamp(listScroll.target() - d.floatValue() * 40, 0, listMax)), null));
    }

    private void drawSwitch(GuiGraphics g, Theme t, int x, int y, boolean on) { drawSwitch(g, t, x, y, on, null); }

    /** Переключатель с плавным ходом ручки и перетеканием цвета (key — объект настройки/модуля для анимации). */
    private void drawSwitch(GuiGraphics g, Theme t, int x, int y, boolean on, Object key) {
        float p = key == null ? (on ? 1f : 0f) : Anim.easeInOut(animate(key, on ? 1f : 0f));
        int track = ColorUtil.lerp(ColorUtil.withAlpha(t.textMuted, 70), t.accent, p);
        Render2D.roundedRect(g, x, y, 46, 22, 11, track);
        int kx = Math.round(x + 2 + 24 * p);
        Render2D.circle(g, kx + 9, y + 12, 9, 0x33000000);
        Render2D.circle(g, kx + 9, y + 11, 9, 0xFFFBF6F1);
    }

    private final java.util.IdentityHashMap<Object, float[]> anims = new java.util.IdentityHashMap<>();
    private long lastFrameNanos;
    private float frameLerp = 1f;

    /** Экспоненциальное сглаживание значения к цели, независимое от FPS. */
    private float animate(Object key, float target) {
        float[] v = anims.computeIfAbsent(key, k -> new float[]{target});
        v[0] += (target - v[0]) * frameLerp;
        if (Math.abs(target - v[0]) < 0.001f) v[0] = target;
        return v[0];
    }

    // --- настройки ---------------------------------------------------------------------------------
    private void drawSettings(GuiGraphics g, Theme t) {
        int x0 = SIDEBAR_W + 1 + LIST_W + 1, w = DESIGN_W - x0, cw = w - PAD * 2;
        Module m = MenuState.selected;
        if (m == null) {
            Render2D.textCrisp(g, "Выберите модуль", x0 + w / 2f - Render2D.width("Выберите модуль") * TXT / 2f, DESIGN_H / 2f - 20, TXT, t.textMuted, false);
            Render2D.textCrisp(g, "ЛКМ — настройки, переключатель — вкл/выкл, ПКМ — быстрое переключение", x0 + w / 2f - Render2D.width("ЛКМ — настройки, переключатель — вкл/выкл, ПКМ — быстрое переключение") * SMALL / 2f, DESIGN_H / 2f, SMALL, t.textMuted, false);
            return;
        }
        int top = PAD, bottom = DESIGN_H - PAD;
        float sc = settingsScroll.get();
        Render2D.scissor(g, x0, top, w, bottom - top);
        int y = top - Math.round(sc);
        // заголовок
        Render2D.textCrisp(g, m.displayName(), x0 + PAD, y + 4, HEAD, t.text, false);
        drawSwitch(g, t, x0 + w - PAD - 46, y + 2, m.isEnabled(), m);
        hits.add(new Hit(x0 + w - PAD - 46, y, 46, 24, b -> m.toggle(), null, null, null));
        y += 30;
        for (String line : wrap(m.description(), (int) (cw / SMALL))) { Render2D.textCrisp(g, line, x0 + PAD, y, SMALL, t.textMuted, false); y += 13; }
        y += 8;
        g.fill(x0 + PAD, y, x0 + w - PAD, y + 1, t.border);
        y += 12;
        // клавиша и скрытие
        y = drawKeybind(g, t, m.bind, m, x0 + PAD, y, cw);
        if (m instanceof HudModule) y = drawButtonRow(g, t, "Позиция на экране", "Редактор HUD", x0 + PAD, y, cw, () -> minecraft.setScreen(new HudEditorScreen(this)));
        y = drawBoolean(g, t, m.hideInList, x0 + PAD, y, cw);
        y += 4;
        g.fill(x0 + PAD, y, x0 + w - PAD, y + 1, t.border);
        y += 12;
        y = drawSettingList(g, t, m.settings(), x0 + PAD, y, cw);
        y += 6;
        y = drawButtonRow(g, t, "Сбросить настройки модуля", "Сбросить", x0 + PAD, y, cw, () -> { m.resetSettings(); ConfigManager.markDirty(); });
        settingsMax = Math.max(0, y + Math.round(sc) - bottom + 8);
        Render2D.unscissor(g);
        hits.add(new Hit(x0, top, w, bottom - top, null, null, d -> settingsScroll.to(clamp(settingsScroll.target() - d.floatValue() * 40, 0, settingsMax)), null));
    }

    private int drawSettingList(GuiGraphics g, Theme t, List<Setting<?>> list, int x, int y, int w) {
        for (Setting<?> s : list) {
            if (!s.isVisible()) continue;
            if (s instanceof BooleanSetting b) y = drawBoolean(g, t, b, x, y, w);
            else if (s instanceof NumberSetting n) y = drawNumber(g, t, n, x, y, w);
            else if (s instanceof ColorSetting c) y = drawColor(g, t, c, x, y, w);
            else if (s instanceof SelectSetting sel) y = drawSelect(g, t, sel, x, y, w);
            else if (s instanceof MultiSelectSetting ms) y = drawMultiSelect(g, t, ms, x, y, w);
            else if (s instanceof KeybindSetting k) y = drawKeybind(g, t, k, null, x, y, w);
            else if (s instanceof TextSetting txt) y = drawText(g, t, txt, x, y, w);
            else if (s instanceof GroupSetting gr) y = drawGroup(g, t, gr, x, y, w);
        }
        return y;
    }

    private int label(GuiGraphics g, Theme t, Setting<?> s, int x, int y) {
        Render2D.textCrisp(g, s.name(), x, y + 6, TXT, t.text, false);
        if (!s.description().isBlank()) Render2D.textCrisp(g, s.description(), x, y + 21, SMALL, t.textMuted, false);
        return s.description().isBlank() ? 30 : 42;
    }

    private int drawBoolean(GuiGraphics g, Theme t, BooleanSetting b, int x, int y, int w) {
        int h = label(g, t, b, x, y);
        drawSwitch(g, t, x + w - 46, y + 4, b.get(), b);
        hits.add(new Hit(x, y, w, h, btn -> { b.toggle(); ConfigManager.markDirty(); }, null, null, null));
        return y + h;
    }

    private int drawNumber(GuiGraphics g, Theme t, NumberSetting n, int x, int y, int w) {
        Render2D.textCrisp(g, n.name(), x, y + 6, TXT, t.text, false);
        Render2D.textCrisp(g, n.format(), x + w - Render2D.width(n.format()) * TXT, y + 6, TXT, t.accent, false);
        int sy = y + (n.description().isBlank() ? 24 : 36), sw = w;
        if (!n.description().isBlank()) Render2D.textCrisp(g, n.description(), x, y + 21, SMALL, t.textMuted, false);
        Render2D.roundedRect(g, x, sy, sw, 6, 3, ColorUtil.withAlpha(t.textMuted, 60));
        int fw = Math.round(sw * animate(n, (float) n.fraction()));
        Render2D.roundedRect(g, x, sy, Math.max(6, fw), 6, 3, t.accent);
        Render2D.circle(g, x + fw, sy + 4, 8, 0x33000000);
        Render2D.circle(g, x + fw, sy + 3, 8, 0xFFFBF6F1);
        Render2D.circle(g, x + fw, sy + 3, 4, t.accent);
        final int sx = x;
        Consumer<double[]> drag = p -> { n.setFraction((p[0] - sx) / sw); ConfigManager.markDirty(); };
        hits.add(new Hit(x - 6, sy - 10, sw + 12, 26, null, drag, null, null));
        return y + (n.description().isBlank() ? 42 : 54);
    }

    private int drawColor(GuiGraphics g, Theme t, ColorSetting c, int x, int y, int w) {
        int h = label(g, t, c, x, y);
        int col = c.color();
        Render2D.roundedRect(g, x + w - 60, y + 3, 60, 24, 7, t.border);
        Render2D.roundedRect(g, x + w - 59, y + 4, 58, 22, 6, col);
        hits.add(new Hit(x, y, w, h, b -> { if (expandedColors.contains(c)) expandedColors.remove(c); else expandedColors.add(c); }, null, null, null));
        y += h;
        if (!expandedColors.contains(c)) return y;
        // пикер
        int ph = 150;
        Render2D.roundedRect(g, x, y, w, ph, 10, t.panel);
        Render2D.roundedOutline(g, x, y, w, ph, 10, t.border);
        float[] hsv = toHsv(c.get());
        int sq = 110, sqx = x + 12, sqy = y + 12;
        int hueColor = ColorUtil.hsv(hsv[0], 1f, 1f);
        for (int i = 0; i < sq; i += 2) {
            int cc = ColorUtil.lerp(0xFFFFFFFF, hueColor, i / (float) (sq - 1));
            g.fillGradient(sqx + i, sqy, sqx + i + 2, sqy + sq, cc, 0xFF000000);
        }
        int px = sqx + Math.round(hsv[1] * (sq - 1)), py = sqy + Math.round((1 - hsv[2]) * (sq - 1));
        Render2D.outline(g, px - 3, py - 3, 7, 7, 0xFFFFFFFF);
        Render2D.outline(g, px - 2, py - 2, 5, 5, 0xFF000000);
        Consumer<double[]> dragSv = p -> {
            float sat = clamp((float) ((p[0] - sqx) / (sq - 1)), 0, 1), val = 1 - clamp((float) ((p[1] - sqy) / (sq - 1)), 0, 1);
            c.set(ColorUtil.withAlpha(ColorUtil.hsv(hsv[0], sat, val), ColorUtil.alpha(c.get())));
            ConfigManager.markDirty();
        };
        hits.add(new Hit(sqx, sqy, sq, sq, null, dragSv, null, null));
        // оттенок
        int hx = sqx + sq + 12, hy = y + 12, hw = 14;
        for (int i = 0; i < sq; i++) g.fill(hx, hy + i, hx + hw, hy + i + 1, ColorUtil.hsv(i / (float) sq, 1f, 1f));
        int hp = hy + Math.round(hsv[0] * (sq - 1));
        Render2D.outline(g, hx - 1, hp - 1, hw + 2, 3, 0xFFFFFFFF);
        hits.add(new Hit(hx, hy, hw, sq, null, p -> {
            float hue = clamp((float) ((p[1] - hy) / (sq - 1)), 0, 0.999f);
            c.set(ColorUtil.withAlpha(ColorUtil.hsv(hue, hsv[1], hsv[2]), ColorUtil.alpha(c.get())));
            ConfigManager.markDirty();
        }, null, null));
        // альфа
        int ax = hx + hw + 10;
        if (c.hasAlpha()) {
            for (int i = 0; i < sq; i++) g.fill(ax, hy + i, ax + hw, hy + i + 1, ColorUtil.withAlpha(c.rgb() | 0xFF000000, 255 - Math.round(i / (float) sq * 255)));
            int ap = hy + Math.round((1 - ColorUtil.alpha(c.get()) / 255f) * (sq - 1));
            Render2D.outline(g, ax - 1, ap - 1, hw + 2, 3, 0xFFFFFFFF);
            hits.add(new Hit(ax, hy, hw, sq, null, p -> {
                int al = Math.round((1 - clamp((float) ((p[1] - hy) / (sq - 1)), 0, 1)) * 255);
                c.set(ColorUtil.withAlpha(c.get(), al));
                ConfigManager.markDirty();
            }, null, null));
        }
        // режимы и hex
        int bx = ax + hw + 16, by = y + 12;
        for (ColorSetting.Mode mode : ColorSetting.Mode.values()) {
            boolean sel = c.mode() == mode;
            int bw = (int) (Render2D.width(mode.title) * SMALL) + 16;
            Render2D.roundedRect(g, bx, by, bw, 20, 6, sel ? t.accent : t.panelAlt);
            Render2D.textCrisp(g, mode.title, bx + 8, by + 5, SMALL, sel ? 0xFFFFFFFF : t.text, false);
            hits.add(new Hit(bx, by, bw, 20, b -> { c.setMode(mode); ConfigManager.markDirty(); }, null, null, null));
            by += 26;
        }
        Render2D.textCrisp(g, ColorUtil.hex(c.get()), bx, by + 6, SMALL, t.textMuted, false);
        // пресеты
        int[] presets = {0xFFD97757, 0xFFE05A4F, 0xFFE8B84A, 0xFF5FB36A, 0xFF4FB3D9, 0xFF7E8ED8, 0xFFE88AA8, 0xFFFFFFFF, 0xFF2B2A28};
        int pxx = bx;
        for (int pc : presets) {
            Render2D.roundedRect(g, pxx, y + ph - 26, 14, 14, 4, pc);
            final int preset = pc;
            hits.add(new Hit(pxx, y + ph - 26, 14, 14, b -> { c.set(ColorUtil.withAlpha(preset, ColorUtil.alpha(c.get()))); ConfigManager.markDirty(); }, null, null, null));
            pxx += 18;
        }
        return y + ph + 8;
    }

    private int drawSelect(GuiGraphics g, Theme t, SelectSetting s, int x, int y, int w) {
        Render2D.textCrisp(g, s.name(), x, y + 6, TXT, t.text, false);
        int yy = y + 22;
        if (!s.description().isBlank()) { Render2D.textCrisp(g, s.description(), x, y + 21, SMALL, t.textMuted, false); yy += 14; }
        int cx = x;
        for (String o : s.options()) {
            int cw = (int) (Render2D.width(o) * SMALL) + 18;
            if (cx + cw > x + w) { cx = x; yy += 26; }
            boolean sel = s.is(o);
            Render2D.roundedRect(g, cx, yy, cw, 22, 7, sel ? t.accent : t.panel);
            if (!sel) Render2D.roundedOutline(g, cx, yy, cw, 22, 7, t.border);
            Render2D.textCrisp(g, o, cx + 9, yy + 6, SMALL, sel ? 0xFFFFFFFF : t.text, false);
            final String opt = o;
            hits.add(new Hit(cx, yy, cw, 22, b -> { s.set(opt); ConfigManager.markDirty(); }, null, null, null));
            cx += cw + 6;
        }
        return yy + 32;
    }

    private int drawMultiSelect(GuiGraphics g, Theme t, MultiSelectSetting s, int x, int y, int w) {
        Render2D.textCrisp(g, s.name(), x, y + 6, TXT, t.text, false);
        int yy = y + 22;
        if (!s.description().isBlank()) { Render2D.textCrisp(g, s.description(), x, y + 21, SMALL, t.textMuted, false); yy += 14; }
        int cx = x;
        for (String o : s.options()) {
            int cw = (int) (Render2D.width(o) * SMALL) + 18;
            if (cx + cw > x + w) { cx = x; yy += 26; }
            boolean sel = s.has(o);
            Render2D.roundedRect(g, cx, yy, cw, 22, 7, sel ? t.accentSoft : t.panel);
            Render2D.roundedOutline(g, cx, yy, cw, 22, 7, sel ? soft(t.accent) : t.border);
            Render2D.textCrisp(g, o, cx + 9, yy + 6, SMALL, t.text, false);
            final String opt = o;
            hits.add(new Hit(cx, yy, cw, 22, b -> { s.toggle(opt); ConfigManager.markDirty(); }, null, null, null));
            cx += cw + 6;
        }
        return yy + 32;
    }

    private int drawKeybind(GuiGraphics g, Theme t, KeybindSetting k, Module owner, int x, int y, int w) {
        int h = label(g, t, k, x, y);
        boolean waiting = binding == k;
        String txt = waiting ? "Нажмите клавишу…" : k.display();
        int bw = (int) (Render2D.width(txt) * SMALL) + 20;
        Render2D.roundedRect(g, x + w - bw, y + 4, bw, 22, 7, waiting ? t.accent : t.panel);
        Render2D.roundedOutline(g, x + w - bw, y + 4, bw, 22, 7, waiting ? soft(t.accent) : t.border);
        Render2D.textCrisp(g, txt, x + w - bw + 10, y + 10, SMALL, waiting ? 0xFFFFFFFF : t.text, false);
        hits.add(new Hit(x + w - bw, y + 4, bw, 22, b -> {
            if (b == GLFW.GLFW_MOUSE_BUTTON_RIGHT) { k.set(KeybindSetting.NONE); ConfigManager.markDirty(); binding = null; }
            else { binding = k; focused = null; }
        }, null, null, null));
        return y + h;
    }

    private int drawText(GuiGraphics g, Theme t, TextSetting s, int x, int y, int w) {
        Render2D.textCrisp(g, s.name(), x, y + 6, TXT, t.text, false);
        int yy = y + 22;
        if (!s.description().isBlank()) { Render2D.textCrisp(g, s.description(), x, y + 21, SMALL, t.textMuted, false); yy += 14; }
        TextField f = fieldFor(s);
        drawTextField(g, t, f, x, yy, w, 28, "");
        return yy + 36;
    }

    private int drawGroup(GuiGraphics g, Theme t, GroupSetting gr, int x, int y, int w) {
        Render2D.roundedRect(g, x, y, w, 30, 8, t.panel);
        Render2D.textCrisp(g, (gr.expanded() ? "▾  " : "▸  ") + gr.name(), x + 10, y + 9, TXT, t.text, false);
        if (!gr.description().isBlank()) Render2D.textCrisp(g, gr.description(), x + w - Render2D.width(gr.description()) * SMALL - 10, y + 10, SMALL, t.textMuted, false);
        hits.add(new Hit(x, y, w, 30, b -> gr.toggleExpanded(), null, null, null));
        y += 36;
        if (!gr.expanded()) return y;
        int startY = y;
        y = drawSettingList(g, t, gr.children(), x + 16, y, w - 16);
        g.fill(x + 4, startY, x + 6, y - 6, t.border);
        return y + 4;
    }

    private int drawButtonRow(GuiGraphics g, Theme t, String label, String button, int x, int y, int w, Runnable action) {
        Render2D.textCrisp(g, label, x, y + 6, TXT, t.text, false);
        int bw = (int) (Render2D.width(button) * SMALL) + 20;
        boolean hover = hover(x + w - bw, y + 2, bw, 24);
        Render2D.roundedRect(g, x + w - bw, y + 2, bw, 24, 7, hover ? t.accent : t.panel);
        Render2D.roundedOutline(g, x + w - bw, y + 2, bw, 24, 7, hover ? soft(t.accent) : t.border);
        Render2D.textCrisp(g, button, x + w - bw + 10, y + 9, SMALL, hover ? 0xFFFFFFFF : t.text, false);
        hits.add(new Hit(x + w - bw, y + 2, bw, 24, b -> action.run(), null, null, null));
        return y + 32;
    }

    // --- друзья / профили ------------------------------------------------------------------------------
    private void drawFriends(GuiGraphics g, Theme t) {
        int x0 = SIDEBAR_W + 1 + PAD * 2, w = DESIGN_W - x0 - PAD * 2;
        Render2D.textCrisp(g, "Друзья", x0, PAD + 4, HEAD, t.text, false);
        Render2D.textCrisp(g, "Друзья подсвечиваются отдельным цветом в HUD и визуалах. Ник без учёта регистра.", x0, PAD + 30, SMALL, t.textMuted, false);
        drawTextField(g, t, friendField, x0, PAD + 54, w - 120, 30, "Ник игрока");
        boolean hover = hover(x0 + w - 110, PAD + 54, 110, 30);
        Render2D.roundedRect(g, x0 + w - 110, PAD + 54, 110, 30, 8, hover ? ColorUtil.darker(t.accent, 0.9f) : t.accent);
        Render2D.textCrisp(g, "Добавить", x0 + w - 110 + 55 - Render2D.width("Добавить") * TXT / 2f, PAD + 63, TXT, 0xFFFFFFFF, false);
        hits.add(new Hit(x0 + w - 110, PAD + 54, 110, 30, b -> addFriend(), null, null, null));
        int y = PAD + 100;
        List<String> names = new ArrayList<>(Friends.all());
        if (minecraft.getConnection() != null) {
            // онлайн-игроки, которых можно добавить одним кликом
            int cx = x0; int yy = y;
            Render2D.textCrisp(g, "Сейчас на сервере:", x0, yy, SMALL, t.textMuted, false);
            yy += 16;
            for (var info : minecraft.getConnection().getOnlinePlayers()) {
                String n = info.getProfile().name();
                if (minecraft.player != null && n.equals(minecraft.player.getGameProfile().name())) continue;
                int cw = (int) (Render2D.width(n) * SMALL) + 18;
                if (cx + cw > x0 + w) { cx = x0; yy += 26; }
                boolean f = Friends.contains(n);
                Render2D.roundedRect(g, cx, yy, cw, 22, 7, f ? t.accentSoft : t.panel);
                Render2D.roundedOutline(g, cx, yy, cw, 22, 7, f ? soft(t.accent) : t.border);
                Render2D.textCrisp(g, n, cx + 9, yy + 6, SMALL, t.text, false);
                hits.add(new Hit(cx, yy, cw, 22, b -> Friends.toggle(n), null, null, null));
                cx += cw + 6;
            }
            y = yy + 40;
        }
        if (names.isEmpty()) Render2D.textCrisp(g, "Список пуст", x0, y, TXT, t.textMuted, false);
        for (String n : names) {
            Render2D.roundedRect(g, x0, y, w, 36, 9, t.panel);
            Render2D.textCrisp(g, n, x0 + 14, y + 11, TXT, t.text, false);
            boolean h = hover(x0 + w - 90, y + 6, 80, 24);
            Render2D.roundedRect(g, x0 + w - 90, y + 6, 80, 24, 7, h ? t.danger : t.panelAlt);
            Render2D.textCrisp(g, "Удалить", x0 + w - 90 + 40 - Render2D.width("Удалить") * SMALL / 2f, y + 13, SMALL, h ? 0xFFFFFFFF : t.text, false);
            hits.add(new Hit(x0 + w - 90, y + 6, 80, 24, b -> Friends.remove(n), null, null, null));
            y += 42;
        }
    }

    private void addFriend() {
        if (Friends.add(friendField.text)) friendField.text = "";
    }

    private void drawProfiles(GuiGraphics g, Theme t) {
        int x0 = SIDEBAR_W + 1 + PAD * 2, w = DESIGN_W - x0 - PAD * 2;
        Render2D.textCrisp(g, "Профили", x0, PAD + 4, HEAD, t.text, false);
        Render2D.textCrisp(g, "Файлы config/naovisual/profiles/<имя>.json. Текущий: " + ConfigManager.profile(), x0, PAD + 30, SMALL, t.textMuted, false);
        drawTextField(g, t, profileField, x0, PAD + 54, w - 250, 30, "Имя нового профиля");
        button(g, t, "Создать", x0 + w - 240, PAD + 54, 115, 30, true, () -> {
            if (!profileField.text.isBlank()) { ConfigManager.saveAs(profileField.text); profileField.text = ""; }
        });
        button(g, t, "Сохранить", x0 + w - 115, PAD + 54, 115, 30, false, ConfigManager::save);
        int y = PAD + 100;
        for (String p : ConfigManager.profiles()) {
            boolean cur = p.equals(ConfigManager.profile());
            Render2D.roundedRect(g, x0, y, w, 36, 9, t.panel);
            if (cur) Render2D.roundedOutline(g, x0, y, w, 36, 9, soft(t.accent));
            Render2D.textCrisp(g, p + (cur ? "  •  активен" : ""), x0 + 14, y + 11, TXT, t.text, false);
            if (!cur) {
                button(g, t, "Загрузить", x0 + w - 190, y + 6, 90, 24, true, () -> ConfigManager.loadProfile(p));
                boolean h = hover(x0 + w - 90, y + 6, 80, 24);
                Render2D.roundedRect(g, x0 + w - 90, y + 6, 80, 24, 7, h ? t.danger : t.panelAlt);
                Render2D.textCrisp(g, "Удалить", x0 + w - 90 + 40 - Render2D.width("Удалить") * SMALL / 2f, y + 13, SMALL, h ? 0xFFFFFFFF : t.text, false);
                hits.add(new Hit(x0 + w - 90, y + 6, 80, 24, b -> ConfigManager.deleteProfile(p), null, null, null));
            }
            y += 42;
        }
    }

    private void button(GuiGraphics g, Theme t, String label, int x, int y, int w, int h, boolean primary, Runnable action) {
        boolean hover = hover(x, y, w, h);
        int bg = primary ? (hover ? ColorUtil.darker(t.accent, 0.9f) : t.accent) : (hover ? t.panelAlt : t.panel);
        Render2D.roundedRect(g, x, y, w, h, 8, bg);
        if (!primary) Render2D.roundedOutline(g, x, y, w, h, 8, t.border);
        Render2D.textCrisp(g, label, x + w / 2f - Render2D.width(label) * SMALL / 2f, y + h / 2f - 5, SMALL, primary ? 0xFFFFFFFF : t.text, false);
        hits.add(new Hit(x, y, w, h, b -> action.run(), null, null, null));
    }

    // --- текстовые поля -------------------------------------------------------------------------------
    private static final class TextField {
        final TextSetting setting;
        final int max;
        String text;
        TextField(TextSetting s, int max) { this.setting = s; this.max = max; this.text = s == null ? "" : s.get(); }
    }

    private final java.util.Map<TextSetting, TextField> fields = new java.util.HashMap<>();

    private TextField fieldFor(TextSetting s) {
        TextField f = fields.get(s);
        if (f == null) { f = new TextField(s, s.maxLength()); fields.put(s, f); }
        if (focused != f) f.text = s.get();
        return f;
    }

    private void drawTextField(GuiGraphics g, Theme t, TextField f, int x, int y, int w, int h, String placeholder) {
        boolean foc = focused == f;
        Render2D.roundedRect(g, x, y, w, h, 8, t.panel);
        Render2D.roundedOutline(g, x, y, w, h, 8, foc ? soft(t.accent) : t.border);
        String shown = f.text.isEmpty() && !foc ? placeholder : f.text;
        boolean blink = foc && (System.currentTimeMillis() / 500) % 2 == 0;
        Render2D.textCrisp(g, shown + (blink ? "_" : ""), x + 10, y + h / 2f - 5, SMALL, f.text.isEmpty() && !foc ? t.textMuted : t.text, false);
        hits.add(new Hit(x, y, w, h, b -> { focused = f; binding = null; }, null, null, null));
    }

    // --- ввод -------------------------------------------------------------------------------------------
    @Override
    public boolean mouseClicked(MouseButtonEvent e, boolean dbl) {
        double px = (e.x() - ox) / scale, py = (e.y() - oy) / scale;
        if (binding != null) {
            if (e.button() != GLFW.GLFW_MOUSE_BUTTON_LEFT) {
                binding.set(KeybindSetting.ofMouse(e.button()));
                ConfigManager.markDirty();
            }
            binding = null;
            if (e.button() != GLFW.GLFW_MOUSE_BUTTON_LEFT) return true;
        }
        TextField prevFocus = focused;
        focused = null;
        for (int i = hits.size() - 1; i >= 0; i--) {
            Hit h = hits.get(i);
            if (!h.contains(px, py)) continue;
            if (h.onDrag != null && e.button() == GLFW.GLFW_MOUSE_BUTTON_LEFT) { active = h; h.onDrag.accept(new double[]{px, py}); return true; }
            if (h.onClick != null) { h.onClick.accept(e.button()); commitField(prevFocus); return true; }
        }
        commitField(prevFocus);
        if (px < 0 || py < 0 || px > DESIGN_W || py > DESIGN_H) onClose();
        return true;
    }

    private void commitField(TextField f) {
        if (f != null && f.setting != null && focused != f) { f.setting.set(f.text); ConfigManager.markDirty(); }
    }

    @Override
    public boolean mouseDragged(MouseButtonEvent e, double dx, double dy) {
        if (active != null && active.onDrag != null) {
            active.onDrag.accept(new double[]{(e.x() - ox) / scale, (e.y() - oy) / scale});
            return true;
        }
        return false;
    }

    @Override
    public boolean mouseReleased(MouseButtonEvent e) {
        if (active != null) { if (active.onRelease != null) active.onRelease.run(); active = null; return true; }
        return false;
    }

    @Override
    public boolean mouseScrolled(double mx, double my, double hx, double vy) {
        double px = (mx - ox) / scale, py = (my - oy) / scale;
        for (int i = hits.size() - 1; i >= 0; i--) {
            Hit h = hits.get(i);
            if (h.onScroll != null && h.contains(px, py)) { h.onScroll.accept(vy); return true; }
        }
        return false;
    }

    @Override
    public boolean keyPressed(KeyEvent e) {
        if (binding != null) {
            if (e.key() == GLFW.GLFW_KEY_ESCAPE || e.key() == GLFW.GLFW_KEY_BACKSPACE || e.key() == GLFW.GLFW_KEY_DELETE) binding.set(KeybindSetting.NONE);
            else binding.set(e.key());
            ConfigManager.markDirty();
            binding = null;
            return true;
        }
        if (focused != null) {
            if (e.key() == GLFW.GLFW_KEY_BACKSPACE && !focused.text.isEmpty()) {
                focused.text = focused.text.substring(0, focused.text.length() - 1);
                if (focused.setting != null) { focused.setting.set(focused.text); ConfigManager.markDirty(); }
                return true;
            }
            if (e.key() == GLFW.GLFW_KEY_ENTER || e.key() == GLFW.GLFW_KEY_KP_ENTER) {
                if (focused == friendField) addFriend();
                else if (focused == profileField && !profileField.text.isBlank()) { ConfigManager.saveAs(profileField.text); profileField.text = ""; }
                TextField f = focused; focused = null; commitField(f);
                return true;
            }
            if (e.key() == GLFW.GLFW_KEY_ESCAPE) { TextField f = focused; focused = null; commitField(f); return true; }
            return true;
        }
        if (e.key() == GLFW.GLFW_KEY_ESCAPE || isMenuKey(e)) {
            onClose();
            return true;
        }
        return super.keyPressed(e);
    }

    private boolean isMenuKey(KeyEvent e) {
        return milk.naovisual.NaoVisualClient.menuKey.matches(e);
    }

    @Override
    public boolean charTyped(CharacterEvent e) {
        if (focused == null) return false;
        String s = e.codepointAsString();
        if (focused.text.length() + s.length() <= focused.max) {
            focused.text += s;
            if (focused.setting != null) { focused.setting.set(focused.text); ConfigManager.markDirty(); }
        }
        return true;
    }

    @Override
    public void onClose() {
        if (closing) return;
        closing = true;
        open.to(0f);
        ConfigManager.save();
        ModuleRegistry.get(ThemeModule.class).onMenuClose();
    }

    @Override public boolean isPauseScreen() { return false; }
    @Override public boolean shouldCloseOnEsc() { return false; }

    // --- утилиты ------------------------------------------------------------------------------------------
    private boolean hover(int x, int y, int w, int h) { return mouseX >= x && mouseX < x + w && mouseY >= y && mouseY < y + h; }
    private static float clamp(float v, float a, float b) { return Math.max(a, Math.min(b, v)); }

    private static float[] toHsv(int argb) {
        float r = ColorUtil.red(argb) / 255f, g = ColorUtil.green(argb) / 255f, b = ColorUtil.blue(argb) / 255f;
        float max = Math.max(r, Math.max(g, b)), min = Math.min(r, Math.min(g, b)), d = max - min;
        float h = 0;
        if (d > 0) {
            if (max == r) h = ((g - b) / d) % 6; else if (max == g) h = (b - r) / d + 2; else h = (r - g) / d + 4;
            h /= 6f; if (h < 0) h += 1;
        }
        return new float[]{h, max == 0 ? 0 : d / max, max};
    }

    private static List<String> wrap(String text, int maxChars) {
        List<String> out = new ArrayList<>();
        if (text == null) return out;
        StringBuilder line = new StringBuilder();
        for (String word : text.split(" ")) {
            if (Render2D.width(line + " " + word) > maxChars && !line.isEmpty()) { out.add(line.toString()); line = new StringBuilder(); }
            if (!line.isEmpty()) line.append(' ');
            line.append(word);
        }
        if (!line.isEmpty()) out.add(line.toString());
        return out;
    }

    /** Мягкая обводка выделения: акцент на 45 %. */
    private static int soft(int c) { return milk.naovisual.core.util.ColorUtil.withAlpha(c, Math.round(milk.naovisual.core.util.ColorUtil.alpha(c) * 0.45f)); }
}
