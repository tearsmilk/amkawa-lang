package milk.naovisual.mixin;

import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.modules.other.AspectRatioModule;
import net.minecraft.client.renderer.GameRenderer;
import org.joml.Matrix4f;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(GameRenderer.class)
public abstract class GameRendererMixin {
    @Inject(method = "getProjectionMatrix", at = @At("RETURN"))
    private void naovisual$aspect(float fov, CallbackInfoReturnable<Matrix4f> cir) {
        AspectRatioModule m = ModuleRegistry.get(AspectRatioModule.class);
        if (m.isEnabled()) m.apply(cir.getReturnValue());
    }
}
