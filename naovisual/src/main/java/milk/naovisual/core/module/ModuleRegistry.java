package milk.naovisual.core.module;

import milk.naovisual.NaoVisual;
import milk.naovisual.core.hud.HudModule;
import net.fabricmc.fabric.api.client.rendering.v1.world.WorldRenderContext;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.gui.GuiGraphics;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.LivingEntity;

import java.util.ArrayList;
import java.util.Collections;
import java.util.List;
import java.util.Optional;
import java.util.function.Consumer;

/** Реестр модулей и рассылка событий. */
public final class ModuleRegistry {
    private static final List<Module> MODULES = new ArrayList<>();

    private ModuleRegistry() {}

    public static <M extends Module> M register(M m) {
        for (Module existing : MODULES) if (existing.id().equals(m.id())) throw new IllegalStateException("duplicate module " + m.id());
        MODULES.add(m);
        return m;
    }

    public static List<Module> all() { return Collections.unmodifiableList(MODULES); }

    public static List<Module> byCategory(ModuleCategory c) {
        List<Module> out = new ArrayList<>();
        for (Module m : MODULES) if (m.category() == c) out.add(m);
        return out;
    }

    public static List<HudModule> hudModules() {
        List<HudModule> out = new ArrayList<>();
        for (Module m : MODULES) if (m instanceof HudModule h) out.add(h);
        return out;
    }

    public static Optional<Module> byId(String id) {
        for (Module m : MODULES) if (m.id().equalsIgnoreCase(id)) return Optional.of(m);
        return Optional.empty();
    }

    @SuppressWarnings("unchecked")
    public static <M extends Module> M get(Class<M> type) {
        for (Module m : MODULES) if (type.isInstance(m)) return (M) m;
        throw new IllegalStateException("module not registered: " + type.getSimpleName());
    }

    public static boolean enabled(Class<? extends Module> type) {
        for (Module m : MODULES) if (type.isInstance(m)) return m.isEnabled();
        return false;
    }

    public static void clear() { MODULES.clear(); }

    // --- рассылка -------------------------------------------------------------------------------------
    private static void each(Consumer<Module> fn, String what) {
        for (Module m : MODULES) {
            if (!m.isEnabled()) continue;
            try {
                fn.accept(m);
            } catch (Exception e) {
                NaoVisual.LOGGER.error("Модуль {}: ошибка в {}", m.id(), what, e);
            }
        }
    }

    public static void tick() { each(Module::onTick, "onTick"); }
    public static void renderWorld(WorldRenderContext ctx) { each(m -> m.onRenderWorld(ctx), "onRenderWorld"); }
    public static void renderOverlay(GuiGraphics g, DeltaTracker d) { each(m -> m.onRenderOverlay(g, d), "onRenderOverlay"); }
    public static void attack(Entity e) { each(m -> m.onAttack(e), "onAttack"); }
    public static void totemPop(LivingEntity e) { each(m -> m.onTotemPop(e), "onTotemPop"); }
    public static void damage(LivingEntity e) { each(m -> m.onDamage(e), "onDamage"); }
    public static void jump(LivingEntity e) { each(m -> m.onJump(e), "onJump"); }
    public static void joinWorld() { each(Module::onJoinWorld, "onJoinWorld"); }
    public static void disconnect() { each(Module::onDisconnect, "onDisconnect"); }

    /** Нажатие клавиши: сначала биндинги модулей, затем обработчики включённых модулей. */
    public static void key(int key) {
        for (Module m : MODULES) if (m.bind.isBound() && m.bind.get() == key) m.toggle();
        for (Module m : MODULES) {
            if (!m.isEnabled()) continue;
            try { if (m.onKey(key)) return; } catch (Exception e) { NaoVisual.LOGGER.error("Модуль {}: onKey", m.id(), e); }
        }
    }
}
