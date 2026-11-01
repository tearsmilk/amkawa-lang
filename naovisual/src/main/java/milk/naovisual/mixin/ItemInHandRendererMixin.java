package milk.naovisual.mixin;

import com.mojang.blaze3d.vertex.PoseStack;
import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.modules.other.HandTweaksModule;
import net.minecraft.client.player.AbstractClientPlayer;
import net.minecraft.client.renderer.ItemInHandRenderer;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.world.InteractionHand;
import net.minecraft.world.item.ItemStack;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

@Mixin(ItemInHandRenderer.class)
public abstract class ItemInHandRendererMixin {
    @Inject(method = "renderArmWithItem", at = @At("HEAD"))
    private void naovisual$handTweaks(AbstractClientPlayer player, float partialTick, float pitch, InteractionHand hand, float swingProgress,
                                       ItemStack stack, float equipProgress, PoseStack poseStack, SubmitNodeCollector collector, int light, CallbackInfo ci) {
        HandTweaksModule m = ModuleRegistry.get(HandTweaksModule.class);
        if (m.isEnabled()) m.transform(poseStack, hand, swingProgress);
    }
}
