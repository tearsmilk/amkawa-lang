package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Notifications;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.theme.Theme;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import net.minecraft.client.gui.GuiGraphics;

import java.util.List;

public class NotificationsModule extends HudModule {
    private final BooleanSetting toggles = add(new BooleanSetting("Переключение модулей", "Уведомлять о включении и выключении", true).onChange(Notifications::setModuleToggles));
    private final SelectSetting direction = add(new SelectSetting("Направление", "Куда растёт стопка", "Вверх", "Вверх", "Вниз"));
    private final BooleanSetting progress = add(new BooleanSetting("Полоса времени", "", true));

    public NotificationsModule() {
        super("Notifications", "Уведомления", "Всплывающие уведомления клиента (модули, события)", 0.985, 0.9);
    }

    @Override public boolean defaultEnabled() { return true; }
    @Override public void onEnable() { Notifications.setModuleToggles(toggles.on()); }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        List<Notifications.Note> notes = Notifications.snapshot();
        if (editor && notes.isEmpty()) notes = List.of(new Notifications.Note("NaoVisual", "Пример уведомления", Notifications.Type.INFO, System.currentTimeMillis() - 1000, 3000));
        int w = 150, rowH = 26, gap = 4;
        setSize(w, rowH);
        Theme t = ThemeManager.current();
        boolean up = direction.is("Вверх");
        int y = 0;
        for (int i = notes.size() - 1; i >= 0; i--) {
            Notifications.Note n = notes.get(i);
            float age = n.age();
            float in = Anim.easeOut(Math.min(1f, age * n.durationMs() / 250f));
            float out = age > 0.85f ? 1f - (age - 0.85f) / 0.15f : 1f;
            float alpha = Math.min(in, out);
            int slide = Math.round((1f - in) * 30);
            int ny = up ? -y : y;
            int c = typeColor(n.type(), t);
            Render2D.roundedRect(g, slide, ny, w, rowH, 5, ColorUtil.withAlpha(t.panel, Math.round(235 * alpha)));
            Render2D.rect(g, slide, ny + 5, 2, rowH - 10, ColorUtil.withAlpha(c, Math.round(255 * alpha)));
            Render2D.text(g, Render2D.trim(n.title(), w - 14), slide + 8, ny + 4, ColorUtil.withAlpha(t.text, Math.max(10, Math.round(255 * alpha))));
            Render2D.text(g, Render2D.trim(n.text(), w - 14), slide + 8, ny + 14, ColorUtil.withAlpha(t.textMuted, Math.max(10, Math.round(255 * alpha))));
            if (progress.on()) Render2D.rect(g, slide + 8, ny + rowH - 2, Math.round((w - 16) * (1f - Math.min(1f, age))), 1, ColorUtil.withAlpha(c, Math.round(200 * alpha)));
            y += rowH + gap;
        }
    }

    private static int typeColor(Notifications.Type type, Theme t) {
        return switch (type) {
            case SUCCESS -> t.success;
            case WARNING -> 0xFFE8B84A;
            case ERROR -> t.danger;
            default -> t.accent;
        };
    }
}
