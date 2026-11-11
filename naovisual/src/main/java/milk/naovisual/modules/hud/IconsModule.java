package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import net.minecraft.client.gui.GuiGraphics;

import java.util.ArrayList;
import java.util.List;

/** Иконки состояния: горение, под водой, элитры, бег, присед, невидимость, низкое здоровье. */
public class IconsModule extends HudModule {
    private final BooleanSetting background = add(new BooleanSetting("Фон", "", true));
    private final BooleanSetting labels = add(new BooleanSetting("Подписи", "Текст рядом с иконкой", true));

    public IconsModule() {
        super("Icons", "Иконки", "Иконки состояний игрока: огонь, вода, элитры, бег и другие", 0.012, 0.4);
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        var p = mc().player;
        List<String[]> rows = new ArrayList<>();
        if (p != null) {
            if (p.isOnFire()) rows.add(new String[]{"🔥", "Горите", "#FFE57A3F"});
            if (p.isUnderWater()) rows.add(new String[]{"≈", "Под водой", "#FF4FB3D9"});
            if (p.isFallFlying()) rows.add(new String[]{"➶", "Полёт", "#FF9AD3E8"});
            if (p.isSprinting()) rows.add(new String[]{"»", "Бег", "#FF5FB36A"});
            if (p.isCrouching()) rows.add(new String[]{"▼", "Присед", "#FFB2ADA3"});
            if (p.isInvisible()) rows.add(new String[]{"◌", "Невидимость", "#FFC9C4BA"});
            if (p.getHealth() <= 6) rows.add(new String[]{"♥", "Мало здоровья", "#FFE05A4F"});
            if (p.getFoodData().getFoodLevel() <= 6) rows.add(new String[]{"✚", "Голод", "#FFE8B84A"});
            if (p.isBlocking()) rows.add(new String[]{"◈", "Блок", "#FF7E8ED8"});
        }
        if (editor && rows.isEmpty()) { rows.add(new String[]{"»", "Бег", "#FF5FB36A"}); rows.add(new String[]{"🔥", "Горите", "#FFE57A3F"}); }
        int rowH = 14;
        int w = labels.on() ? 90 : 18, h = Math.max(rowH, rows.size() * rowH) + 4;
        setSize(w, h);
        if (rows.isEmpty()) return;
        if (background.on()) Panels.panel(g, 0, 0, w, h, 0.85f);
        int y = 2;
        for (String[] r : rows) {
            int c = (int) Long.parseLong(r[2].substring(1), 16);
            Render2D.text(g, r[0], 5, y + 3, c);
            if (labels.on()) Render2D.text(g, r[1], 18, y + 3, Panels.text());
            y += rowH;
        }
    }
}
