package milk.naovisual.mixin;

import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.modules.world.FogModule;
import net.minecraft.client.Camera;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.fog.FogRenderer;
import org.joml.Vector4f;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(FogRenderer.class)
public abstract class FogRendererMixin {
    @Inject(method = "setupFog", at = @At("RETURN"))
    private void naovisual$fogColor(Camera camera, int renderDistance, DeltaTracker delta, float darkness, ClientLevel level, CallbackInfoReturnable<Vector4f> cir) {
        FogModule m = ModuleRegistry.get(FogModule.class);
        Vector4f c = cir.getReturnValue();
        if (m.isEnabled() && c != null) m.applyColor(c);
    }
}
