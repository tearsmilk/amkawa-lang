package milk.naovisual.modules.hud;

import milk.naovisual.core.hud.HudModule;
import milk.naovisual.core.hud.Panels;
import milk.naovisual.core.render.Render2D;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.ColorSetting;
import milk.naovisual.core.theme.ThemeManager;
import milk.naovisual.core.util.Anim;
import milk.naovisual.core.util.ColorUtil;
import milk.naovisual.core.util.TextUtil;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.client.gui.components.PlayerFaceRenderer;
import net.minecraft.client.player.LocalPlayer;

/** Карточка игрока: голова, ник, здоровье, еда, броня, координаты. */
public class PlayerInfoModule extends HudModule {
    private final BooleanSetting coords = add(new BooleanSetting("Координаты", "", true));
    private final BooleanSetting direction = add(new BooleanSetting("Направление", "Сторона света и биом", true));
    private final BooleanSetting food = add(new BooleanSetting("Еда", "", true));
    private final BooleanSetting speed = add(new BooleanSetting("Скорость", "Блоков в секунду", true));
    private final ColorSetting healthColor = add(new ColorSetting("Цвет здоровья", "", 0xFFE05A4F));
    private final Anim healthAnim = new Anim(1f, 8f);

    public PlayerInfoModule() {
        super("PlayerInfo", "Игрок", "Карточка с головой, ником, здоровьем, едой и координатами", 0.012, 0.9);
    }

    @Override
    protected void renderHud(GuiGraphics g, float partial, boolean editor) {
        LocalPlayer p = mc().player;
        int w = 140, h = 44 + (coords.on() ? 11 : 0) + (direction.on() ? 11 : 0) + (speed.on() ? 11 : 0);
        setSize(w, h);
        Panels.panel(g, 0, 0, w, h, 0.9f);
        var t = ThemeManager.current();
        if (p != null) {
            var skin = p.getSkin();
            PlayerFaceRenderer.draw(g, skin, 5, 5, 20);
        } else Render2D.roundedRect(g, 5, 5, 20, 20, 3, t.border);
        String name = p == null ? "Игрок" : p.getGameProfile().name();
        Render2D.text(g, name, 30, 5, t.text);
        float hp = p == null ? 20 : p.getHealth() + p.getAbsorptionAmount(), max = p == null ? 20 : p.getMaxHealth();
        healthAnim.to(hp / Math.max(1, max));
        String hpText = TextUtil.fixed(hp, 1) + " ♥";
        Render2D.text(g, hpText, w - 5 - Render2D.width(hpText), 5, healthColor.color());
        Render2D.bar(g, 30, 16, w - 35, 4, healthAnim.get(), ColorUtil.withAlpha(t.border, 160), healthColor.color());
        int y = 24;
        if (food.on()) {
            int f = p == null ? 20 : p.getFoodData().getFoodLevel();
            Render2D.bar(g, 30, y, w - 35, 3, f / 20f, ColorUtil.withAlpha(t.border, 160), 0xFFE8B84A);
            y += 6;
        }
        int armor = p == null ? 0 : p.getArmorValue();
        Render2D.text(g, "Броня " + armor + "  Ур. " + (p == null ? 0 : p.experienceLevel), 30, y + 1, t.textMuted);
        y = 32;
        y += 12;
        if (coords.on()) {
            String c = p == null ? "0 0 0" : (int) Math.floor(p.getX()) + "  " + (int) Math.floor(p.getY()) + "  " + (int) Math.floor(p.getZ());
            Render2D.text(g, "XYZ  " + c, 5, y, t.text);
            y += 11;
        }
        if (direction.on()) {
            String dir = p == null ? "С" : compass(p.getYRot());
            String biome = "";
            if (p != null && mc().level != null) {
                var key = mc().level.getBiome(p.blockPosition()).unwrapKey();
                if (key.isPresent()) biome = key.get().identifier().getPath().replace('_', ' ');
            }
            Render2D.text(g, dir + "  " + Render2D.trim(biome, w - 30), 5, y, t.textMuted);
            y += 11;
        }
        if (speed.on()) {
            double bps = p == null ? 0 : Math.hypot(p.getX() - p.xo, p.getZ() - p.zo) * 20;
            Render2D.text(g, TextUtil.fixed(bps, 1) + " бл/с", 5, y, t.textMuted);
        }
    }

    private static String compass(float yaw) {
        float y = ((yaw % 360) + 360) % 360;
        if (y < 22.5 || y >= 337.5) return "Юг";
        if (y < 67.5) return "Юго-запад";
        if (y < 112.5) return "Запад";
        if (y < 157.5) return "Северо-запад";
        if (y < 202.5) return "Север";
        if (y < 247.5) return "Северо-восток";
        if (y < 292.5) return "Восток";
        return "Юго-восток";
    }
}
