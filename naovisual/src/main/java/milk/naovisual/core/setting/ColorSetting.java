package milk.naovisual.core.setting;

import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import milk.naovisual.core.util.ColorUtil;

/** Цвет ARGB с режимами: свой / радуга / цвет темы. */
public class ColorSetting extends Setting<Integer> {
    public enum Mode { CUSTOM("Свой"), RAINBOW("Радуга"), THEME("Тема");
        public final String title;
        Mode(String t) { title = t; }
    }

    private Mode mode = Mode.CUSTOM;
    private final boolean alpha;

    public ColorSetting(String name, String description, int argb) {
        this(name, description, argb, true);
    }

    public ColorSetting(String name, String description, int argb, boolean alpha) {
        super(name, description, argb);
        this.alpha = alpha;
    }

    public boolean hasAlpha() { return alpha; }
    public Mode mode() { return mode; }
    public void setMode(Mode m) { mode = m; }

    /** Итоговый цвет с учётом режима. Для радуги фаза берётся из времени, offset сдвигает её (для градиентов). */
    public int color() { return color(0); }

    public int color(double offset) {
        int a = ColorUtil.alpha(value);
        return switch (mode) {
            case RAINBOW -> ColorUtil.withAlpha(ColorUtil.rainbow(offset), a);
            case THEME -> ColorUtil.withAlpha(milk.naovisual.core.theme.ThemeManager.current().accent, a);
            case CUSTOM -> value;
        };
    }

    public int rgb() { return value & 0xFFFFFF; }

    @Override public JsonElement save() {
        JsonObject o = new JsonObject();
        o.addProperty("argb", value);
        o.addProperty("mode", mode.name());
        return o;
    }

    @Override public void load(JsonElement json) {
        if (json == null) return;
        if (json.isJsonPrimitive()) { set(json.getAsInt()); return; }
        if (!json.isJsonObject()) return;
        JsonObject o = json.getAsJsonObject();
        if (o.has("argb")) set(o.get("argb").getAsInt());
        if (o.has("mode")) {
            try { mode = Mode.valueOf(o.get("mode").getAsString()); } catch (IllegalArgumentException ignored) {}
        }
    }
}
