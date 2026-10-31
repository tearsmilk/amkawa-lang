package milk.naovisual.core.hud;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.modules.hud.*;
import net.fabricmc.fabric.api.client.rendering.v1.hud.HudElement;
import net.fabricmc.fabric.api.client.rendering.v1.hud.HudElementRegistry;
import net.fabricmc.fabric.api.client.rendering.v1.hud.VanillaHudElements;
import net.minecraft.resources.Identifier;

/** Подмена ванильных элементов HUD: пока модуль включён, ванильный элемент не рисуется. */
public final class HudReplacements {
    private HudReplacements() {}

    public static void register() {
        hide(VanillaHudElements.CROSSHAIR, CrossHairModule.class);
        hide(VanillaHudElements.HOTBAR, HotBarModule.class);
        hide(VanillaHudElements.STATUS_EFFECTS, PotionsModule.class);
        hide(VanillaHudElements.BOSS_BAR, BossBarsModule.class);
        hide(VanillaHudElements.SCOREBOARD, ScoreBoardModule.class);
        hide(VanillaHudElements.PLAYER_LIST, TabListModule.class);
    }

    private static void hide(Identifier vanilla, Class<? extends Module> module) {
        HudElementRegistry.replaceElement(vanilla, original -> (HudElement) (g, delta) -> {
            if (!ModuleRegistry.enabled(module)) original.render(g, delta);
        });
    }
}
