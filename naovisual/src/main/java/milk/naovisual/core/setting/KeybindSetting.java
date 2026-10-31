package milk.naovisual.core.setting;

import com.google.gson.JsonElement;
import com.google.gson.JsonPrimitive;

/** Клавиша GLFW (-1 — не назначена). Мышь кодируется как -100 - кнопка. */
public class KeybindSetting extends Setting<Integer> {
    public static final int NONE = -1;

    public KeybindSetting(String name, String description, int defaultKey) {
        super(name, description, defaultKey);
    }

    public boolean isBound() { return value != NONE; }
    public boolean isMouse() { return value <= -100; }
    public int mouseButton() { return -100 - value; }
    public static int ofMouse(int button) { return -100 - button; }

    public String display() {
        if (!isBound()) return "Нет";
        if (isMouse()) return "Мышь " + (mouseButton() + 1);
        return milk.naovisual.core.util.KeyNames.name(value);
    }

    @Override public JsonElement save() { return new JsonPrimitive(value); }

    @Override public void load(JsonElement json) {
        if (json != null && json.isJsonPrimitive() && json.getAsJsonPrimitive().isNumber()) set(json.getAsInt());
    }
}
