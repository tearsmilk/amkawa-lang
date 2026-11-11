package milk.naovisual.mixin;

import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.modules.world.FogModule;
import net.minecraft.client.Camera;
import net.minecraft.client.DeltaTracker;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.fog.FogData;
import net.minecraft.client.renderer.fog.environment.AtmosphericFogEnvironment;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(AtmosphericFogEnvironment.class)
public abstract class AtmosphericFogEnvironmentMixin {
    @Inject(method = "setupFog", at = @At("TAIL"))
    private void naovisual$fog(FogData data, Camera camera, ClientLevel level, float viewDistance, DeltaTracker delta, CallbackInfo ci) {
        FogModule m = ModuleRegistry.get(FogModule.class);
        if (m.isEnabled()) m.apply(data, viewDistance);
    }
}
