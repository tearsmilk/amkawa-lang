package milk.naovisual.core.setting;

import com.google.gson.JsonElement;
import com.google.gson.JsonPrimitive;

public class TextSetting extends Setting<String> {
    private final int maxLength;

    public TextSetting(String name, String description, String defaultValue) {
        this(name, description, defaultValue, 64);
    }

    public TextSetting(String name, String description, String defaultValue, int maxLength) {
        super(name, description, defaultValue);
        this.maxLength = maxLength;
    }

    public int maxLength() { return maxLength; }

    @Override public void set(String v) {
        if (v == null) return;
        if (v.length() > maxLength) v = v.substring(0, maxLength);
        super.set(v);
    }

    @Override public JsonElement save() { return new JsonPrimitive(value); }

    @Override public void load(JsonElement json) {
        if (json != null && json.isJsonPrimitive()) set(json.getAsString());
    }
}
