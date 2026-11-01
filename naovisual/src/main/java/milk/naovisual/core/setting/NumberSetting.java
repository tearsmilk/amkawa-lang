package milk.naovisual.core.setting;

import com.google.gson.JsonElement;
import com.google.gson.JsonPrimitive;

/** Число с диапазоном и шагом; хранится как double, есть удобные getInt/getFloat. */
public class NumberSetting extends Setting<Double> {
    private final double min, max, step;
    private final String suffix;

    public NumberSetting(String name, String description, double defaultValue, double min, double max, double step) {
        this(name, description, defaultValue, min, max, step, "");
    }

    public NumberSetting(String name, String description, double defaultValue, double min, double max, double step, String suffix) {
        super(name, description, defaultValue);
        this.min = min;
        this.max = max;
        this.step = step;
        this.suffix = suffix;
    }

    public double min() { return min; }
    public double max() { return max; }
    public double step() { return step; }
    public String suffix() { return suffix; }
    public int getInt() { return (int) Math.round(value); }
    public float getFloat() { return value.floatValue(); }

    /** Нормализованное значение 0..1 для ползунка. */
    public double fraction() { return max == min ? 0 : (value - min) / (max - min); }

    public void setFraction(double f) {
        set(min + Math.max(0, Math.min(1, f)) * (max - min));
    }

    @Override
    public void set(Double v) {
        if (v == null || v.isNaN()) return;
        double clamped = Math.max(min, Math.min(max, v));
        if (step > 0) clamped = min + Math.round((clamped - min) / step) * step;
        // убираем шум двоичного представления
        clamped = Math.round(clamped * 1_000_000d) / 1_000_000d;
        super.set(Math.max(min, Math.min(max, clamped)));
    }

    public String format() {
        if (step >= 1 && Math.floor(step) == step) return getInt() + suffix;
        String s = String.format(java.util.Locale.ROOT, "%.2f", value);
        if (s.endsWith("0")) s = s.substring(0, s.length() - 1);
        return s + suffix;
    }

    @Override public JsonElement save() { return new JsonPrimitive(value); }

    @Override public void load(JsonElement json) {
        if (json != null && json.isJsonPrimitive() && json.getAsJsonPrimitive().isNumber()) set(json.getAsDouble());
    }
}
