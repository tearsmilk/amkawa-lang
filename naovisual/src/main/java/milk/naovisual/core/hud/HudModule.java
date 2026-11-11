package milk.naovisual.core.hud;

import com.google.gson.JsonObject;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.NumberSetting;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;

/**
 * HUD-модуль с перетаскиваемой позицией. Позиция хранится как доля экрана (0..1) для левого верхнего угла,
 * а размер модуль сообщает сам через setSize во время отрисовки.
 */
public abstract class HudModule extends Module {
    private double fx, fy;        // доля экрана
    private int width = 40, height = 20;
    public final NumberSetting scale = new NumberSetting("Масштаб", "Размер элемента", 1.0, 0.5, 3.0, 0.05, "×");

    protected HudModule(String id, String title, String description, double fx, double fy) {
        super(id, title, description, ModuleCategory.HUD);
        this.fx = fx;
        this.fy = fy;
        add(scale);
    }

    public int width() { return width; }
    public int height() { return height; }
    public float scale() { return scale.getFloat(); }

    protected void setSize(int w, int h) { width = Math.max(1, w); height = Math.max(1, h); }

    /** Экранные координаты левого верхнего угла с учётом масштаба (в GUI-пикселях). */
    public int x() {
        int sw = Minecraft.getInstance().getWindow().getGuiScaledWidth();
        return clampX((int) Math.round(fx * sw), sw);
    }

    public int y() {
        int sh = Minecraft.getInstance().getWindow().getGuiScaledHeight();
        return clampY((int) Math.round(fy * sh), sh);
    }

    public int scaledWidth() { return Math.round(width * scale()); }
    public int scaledHeight() { return Math.round(height * scale()); }

    private int clampX(int x, int sw) { return Math.max(0, Math.min(sw - scaledWidth(), x)); }
    private int clampY(int y, int sh) { return Math.max(0, Math.min(sh - scaledHeight(), y)); }

    public void setPosition(int x, int y) {
        int sw = Minecraft.getInstance().getWindow().getGuiScaledWidth();
        int sh = Minecraft.getInstance().getWindow().getGuiScaledHeight();
        fx = clampX(x, sw) / (double) sw;
        fy = clampY(y, sh) / (double) sh;
    }

    public void setFraction(double x, double y) { fx = x; fy = y; }
    public double fractionX() { return fx; }
    public double fractionY() { return fy; }

    /** Отрисовка в локальных координатах (0,0 — левый верхний угол, масштаб уже применён). */
    protected abstract void renderHud(GuiGraphics g, float partial, boolean editor);

    /** Вызывается менеджером HUD: применяет позицию и масштаб. */
    public final void render(GuiGraphics g, float partial, boolean editor) {
        g.pose().pushMatrix();
        g.pose().translate(x(), y());
        g.pose().scale(scale(), scale());
        renderHud(g, partial, editor);
        g.pose().popMatrix();
    }

    /** Показывать ли модуль в редакторе HUD даже без мира. */
    public boolean previewInEditor() { return true; }

    @Override protected void saveExtra(JsonObject o) {
        JsonObject p = new JsonObject();
        p.addProperty("x", fx);
        p.addProperty("y", fy);
        o.add("pos", p);
    }

    @Override protected void loadExtra(JsonObject o) {
        if (o.has("pos") && o.get("pos").isJsonObject()) {
            JsonObject p = o.getAsJsonObject("pos");
            if (p.has("x")) fx = p.get("x").getAsDouble();
            if (p.has("y")) fy = p.get("y").getAsDouble();
        }
    }
}
