package milk.naovisual.core.hud;

import milk.naovisual.NaoVisual;
import milk.naovisual.core.module.ModuleRegistry;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.Minecraft;
import net.minecraft.client.gui.GuiGraphics;

/** Рисует все включённые HUD-модули одним элементом Fabric HUD. */
public final class HudManager {
    private HudManager() {}

    public static void render(GuiGraphics g, DeltaTracker delta) {
        Minecraft mc = Minecraft.getInstance();
        if (mc.options.hideGui || mc.player == null) return;
        if (mc.screen instanceof HudEditorScreen) return; // редактор рисует сам
        float partial = delta.getGameTimeDeltaPartialTick(false);
        for (HudModule m : ModuleRegistry.hudModules()) {
            if (!m.isEnabled()) continue;
            try {
                m.render(g, partial, false);
            } catch (Exception e) {
                NaoVisual.LOGGER.error("HUD {}: ошибка отрисовки", m.id(), e);
            }
        }
        ModuleRegistry.renderOverlay(g, delta);
    }
}
