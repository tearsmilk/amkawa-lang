package milk.naovisual.core.setting;

import com.google.gson.JsonElement;

import java.util.function.BooleanSupplier;
import java.util.function.Consumer;

/** Базовая настройка модуля: имя, описание, значение по умолчанию, условие видимости и сериализация в JSON. */
public abstract class Setting<T> {
    private final String name;
    private final String description;
    protected final T defaultValue;
    protected T value;
    private BooleanSupplier visible = () -> true;
    private Consumer<T> onChange = v -> {};

    protected Setting(String name, String description, T defaultValue) {
        this.name = name;
        this.description = description;
        this.defaultValue = defaultValue;
        this.value = defaultValue;
    }

    public String name() { return name; }
    public String description() { return description; }
    public T get() { return value; }
    public T defaultValue() { return defaultValue; }

    public void set(T v) {
        if (v == null) return;
        T old = value;
        value = v;
        if (old == null || !old.equals(v)) onChange.accept(v);
    }

    public void reset() { set(defaultValue); }

    /** Показывать настройку только при выполнении условия (например, когда включён родительский флажок). */
    @SuppressWarnings("unchecked")
    public <S extends Setting<T>> S visibleWhen(BooleanSupplier condition) {
        this.visible = condition;
        return (S) this;
    }

    @SuppressWarnings("unchecked")
    public <S extends Setting<T>> S onChange(Consumer<T> listener) {
        this.onChange = listener;
        return (S) this;
    }

    public boolean isVisible() { return visible.getAsBoolean(); }

    public abstract JsonElement save();
    public abstract void load(JsonElement json);

    /** Короткий ключ для JSON: имя без пробелов, в нижнем регистре. */
    public String key() {
        return name.toLowerCase().replace(' ', '_');
    }
}
