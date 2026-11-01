package milk.naovisual.mixin;

import com.mojang.blaze3d.vertex.PoseStack;
import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.modules.hud.NoFireModule;
import net.minecraft.client.renderer.MultiBufferSource;
import net.minecraft.client.renderer.ScreenEffectRenderer;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ScreenEffectRenderer.class)
public abstract class ScreenEffectRendererMixin {
    @Inject(method = "renderFire", at = @At("HEAD"), cancellable = true)
    private static void naovisual$noFire(PoseStack poseStack, MultiBufferSource bufferSource, TextureAtlasSprite sprite, CallbackInfo ci) {
        NoFireModule m = ModuleRegistry.get(NoFireModule.class);
        if (!m.isEnabled()) return;
        if (m.hide()) { ci.cancel(); return; }
        poseStack.translate(0f, -m.offset(), 0f);
    }
}
