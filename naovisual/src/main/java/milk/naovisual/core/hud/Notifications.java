package milk.naovisual.core.hud;

import milk.naovisual.core.module.Module;

import java.util.ArrayList;
import java.util.List;

/** Очередь уведомлений; рисует их модуль «Уведомления», здесь — только данные. */
public final class Notifications {
    public enum Type { INFO, SUCCESS, WARNING, ERROR }

    public record Note(String title, String text, Type type, long createdAt, long durationMs) {
        public float age() { return (System.currentTimeMillis() - createdAt) / (float) durationMs; }
        public boolean expired() { return System.currentTimeMillis() - createdAt > durationMs; }
    }

    private static final List<Note> NOTES = new ArrayList<>();
    private static boolean moduleToggles = true;

    private Notifications() {}

    public static void push(String title, String text, Type type) { push(title, text, type, 3000); }

    public static void push(String title, String text, Type type, long durationMs) {
        synchronized (NOTES) {
            NOTES.add(new Note(title, text, type, System.currentTimeMillis(), durationMs));
            while (NOTES.size() > 6) NOTES.remove(0);
        }
    }

    public static void setModuleToggles(boolean on) { moduleToggles = on; }

    public static void moduleToggled(Module m) {
        if (!moduleToggles || m instanceof milk.naovisual.modules.hud.NotificationsModule && !m.isEnabled()) return;
        push(m.displayName(), m.isEnabled() ? "Модуль включён" : "Модуль выключен", m.isEnabled() ? Type.SUCCESS : Type.INFO, 2200);
    }

    public static List<Note> snapshot() {
        synchronized (NOTES) {
            NOTES.removeIf(Note::expired);
            return new ArrayList<>(NOTES);
        }
    }

    public static void clear() { synchronized (NOTES) { NOTES.clear(); } }
}
