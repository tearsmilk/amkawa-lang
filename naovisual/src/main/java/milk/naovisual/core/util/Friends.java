package milk.naovisual.core.util;

import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.player.Player;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Locale;

/** Список друзей по нику (без учёта регистра). */
public final class Friends {
    private static final List<String> NAMES = new ArrayList<>();

    private Friends() {}

    public static List<String> all() { return Collections.unmodifiableList(NAMES); }

    public static void setAll(List<String> names) {
        NAMES.clear();
        for (String n : names) if (n != null && !n.isBlank() && !contains(n)) NAMES.add(n.trim());
    }

    public static boolean contains(String name) {
        if (name == null) return false;
        String l = name.trim().toLowerCase(Locale.ROOT);
        for (String n : NAMES) if (n.toLowerCase(Locale.ROOT).equals(l)) return true;
        return false;
    }

    public static boolean isFriend(Entity e) {
        return e instanceof Player p && contains(p.getGameProfile().name());
    }

    public static boolean add(String name) {
        if (name == null || name.isBlank() || contains(name)) return false;
        NAMES.add(name.trim());
        milk.naovisual.core.config.ConfigManager.markDirty();
        return true;
    }

    public static boolean remove(String name) {
        boolean r = NAMES.removeIf(n -> n.equalsIgnoreCase(name == null ? "" : name.trim()));
        if (r) milk.naovisual.core.config.ConfigManager.markDirty();
        return r;
    }

    public static void toggle(String name) {
        if (!remove(name)) add(name);
    }
}
