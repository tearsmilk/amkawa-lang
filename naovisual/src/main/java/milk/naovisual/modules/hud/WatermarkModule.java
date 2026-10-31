package milk.naovisual.modules.hud;

import milk.naovisual.NaoVisual;
import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.setting.SelectSetting;
import milk.naovisual.core.setting.TextSetting;
import milk.naovisual.core.util.TextUtil;
import net.minecraft.client.gui.GuiGraphics;

public class WatermarkModule extends HudModule {
    private final TextSetting text = add(new TextSetting("Текст", "Название в водяном знаке", NaoVisual.NAME, 24));
    private final SelectSetting style = add(new SelectSetting("Стиль", "", "Плашка", "Плашка", "Текст", "Минимал"));
    private final BooleanSetting fps = add(new BooleanSetting("FPS", "", true));
    private final BooleanSetting ping = add(new BooleanSetting("Пинг", "", true));
    private final BooleanSetting clock = add(new BooleanSetting("Время", "Системное время", true));
    private final BooleanSetting server = add(new BooleanSetting("Сервер", "Адрес сервера", false));
    private final ColorSetting accent = add(new ColorSetting("Акцент", "Цвет первой буквы и разделителей", 0xFFD97757));

    public WatermarkModule() {
        super("Watermark", "Водяной знак", "Название клиента, FPS, пинг и время в углу экрана", 0.012, 0.015);
        accent.setMode(ColorSetting.Mode.THEME);
    }

    @Override public boolean defaultEnabled() { return true; }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        StringBuilder extra = new StringBuilder();
        if (fps.on()) extra.append(mc().getFps()).append(" fps");
        if (ping.on() && mc().getConnection() != null && mc().player != null) {
            var info = mc().getConnection().getPlayerInfo(mc().player.getUUID());
            if (info != null) { if (!extra.isEmpty()) extra.append("  "); extra.append(info.getLatency()).append(" ms"); }
        }
        if (clock.on()) { if (!extra.isEmpty()) extra.append("  "); extra.append(TextUtil.time()); }
        if (server.on()) {
            String ip = mc().getCurrentServer() != null ? mc().getCurrentServer().ip : "одиночная игра";
            if (!extra.isEmpty()) extra.append("  "); extra.append(ip);
        }
        String name = text.get().isBlank() ? NaoVisual.NAME : text.get();
        String first = name.substring(0, 1), rest = name.substring(1);
        int nameW = Render2D.width(name), extraW = extra.isEmpty() ? 0 : Render2D.width(extra.toString()) + 10;
        int ac = accent.color();
        switch (style.get()) {
            case "Плашка" -> {
                int w = nameW + extraW + 14, h = 16;
                setSize(w, h);
                Panels.panel(g, 0, 0, w, h, 0.9f);
                Render2D.rect(g, 0, 4, 2, h - 8, ac);
                Render2D.text(g, first, 7, 4, ac);
                Render2D.text(g, rest, 7 + Render2D.width(first), 4, Panels.text());
                if (!extra.isEmpty()) {
                    Render2D.rect(g, 7 + nameW + 4, 4, 1, h - 8, ac);
                    Render2D.text(g, extra.toString(), 7 + nameW + 10, 4, Panels.muted());
                }
            }
            case "Текст" -> {
                int w = nameW + extraW, h = 10;
                setSize(w, h);
                Render2D.textShadow(g, first, 0, 0, ac);
                Render2D.textShadow(g, rest, Render2D.width(first), 0, 0xFFFFFFFF);
                if (!extra.isEmpty()) Render2D.textShadow(g, extra.toString(), nameW + 10, 0, 0xFFDDDDDD);
            }
            default -> {
                int w = nameW + (fps.on() ? Render2D.width(" " + mc().getFps()) : 0), h = 10;
                setSize(w, h);
                Render2D.textShadow(g, name, 0, 0, ac);
                if (fps.on()) Render2D.textShadow(g, " " + mc().getFps(), nameW, 0, 0xFFFFFFFF);
            }
        }
    }
}
