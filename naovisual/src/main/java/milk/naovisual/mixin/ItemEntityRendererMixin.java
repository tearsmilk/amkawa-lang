package milk.naovisual.mixin;

import com.mojang.blaze3d.vertex.PoseStack;
import com.mojang.math.Axis;
import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.core.util.ItemPhysicsState;
import milk.naovisual.modules.world.ItemPhysicsModule;
import net.minecraft.client.renderer.SubmitNodeCollector;
import net.minecraft.client.renderer.entity.ItemEntityRenderer;
import net.minecraft.client.renderer.entity.state.ItemEntityRenderState;
import net.minecraft.client.renderer.state.CameraRenderState;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.item.ItemEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.Unique;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.ModifyArg;
import org.spongepowered.asm.mixin.injection.Redirect;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;

/** «Физика предметов»: на земле — без подпрыгивания и вращения, плоские предметы лежат плашмя. */
@Mixin(ItemEntityRenderer.class)
public abstract class ItemEntityRendererMixin {
    @Unique private static ItemEntityRenderState naovisual$current;

    @Unique
    private static boolean naovisual$active(ItemEntityRenderState s) {
        return s instanceof ItemPhysicsState ps && ps.naovisual$onGround() && ModuleRegistry.get(ItemPhysicsModule.class).isEnabled();
    }

    @Unique
    private static boolean naovisual$flat(ItemEntityRenderState s) {
        return s.item.getModelBoundingBox().getZsize() < 0.13;
    }

    @Inject(method = "extractRenderState(Lnet/minecraft/world/entity/item/ItemEntity;Lnet/minecraft/client/renderer/entity/state/ItemEntityRenderState;F)V", at = @At("TAIL"))
    private void naovisual$extract(ItemEntity entity, ItemEntityRenderState state, float partial, CallbackInfo ci) {
        if (state instanceof ItemPhysicsState ps) {
            ps.naovisual$setOnGround(entity.onGround());
            ps.naovisual$setYaw((float) Math.toRadians(Math.floorMod(entity.getId() * 2654435761L >>> 8, 360L)));
        }
    }

    @Inject(method = "submit(Lnet/minecraft/client/renderer/entity/state/ItemEntityRenderState;Lcom/mojang/blaze3d/vertex/PoseStack;Lnet/minecraft/client/renderer/SubmitNodeCollector;Lnet/minecraft/client/renderer/state/CameraRenderState;)V", at = @At("HEAD"))
    private void naovisual$head(ItemEntityRenderState state, PoseStack ps, SubmitNodeCollector c, CameraRenderState cam, CallbackInfo ci) {
        naovisual$current = state;
    }

    @ModifyArg(method = "submit(Lnet/minecraft/client/renderer/entity/state/ItemEntityRenderState;Lcom/mojang/blaze3d/vertex/PoseStack;Lnet/minecraft/client/renderer/SubmitNodeCollector;Lnet/minecraft/client/renderer/state/CameraRenderState;)V",
            at = @At(value = "INVOKE", target = "Lcom/mojang/blaze3d/vertex/PoseStack;translate(FFF)V", ordinal = 0), index = 1)
    private float naovisual$noBob(float y) {
        ItemEntityRenderState s = naovisual$current;
        if (s == null || !naovisual$active(s)) return y;
        if (naovisual$flat(s)) return 0.035f;
        return y - (Mth.sin(s.ageInTicks / 10.0F + ((ItemEntityRenderState) s).bobOffset) * 0.1F + 0.1F);
    }

    @Redirect(method = "submit(Lnet/minecraft/client/renderer/entity/state/ItemEntityRenderState;Lcom/mojang/blaze3d/vertex/PoseStack;Lnet/minecraft/client/renderer/SubmitNodeCollector;Lnet/minecraft/client/renderer/state/CameraRenderState;)V",
            at = @At(value = "INVOKE", target = "Lnet/minecraft/world/entity/item/ItemEntity;getSpin(FF)F"))
    private float naovisual$noSpin(float age, float bob) {
        ItemEntityRenderState s = naovisual$current;
        if (s != null && naovisual$active(s)) return ((ItemPhysicsState) s).naovisual$yaw();
        return ItemEntity.getSpin(age, bob);
    }

    @Inject(method = "submit(Lnet/minecraft/client/renderer/entity/state/ItemEntityRenderState;Lcom/mojang/blaze3d/vertex/PoseStack;Lnet/minecraft/client/renderer/SubmitNodeCollector;Lnet/minecraft/client/renderer/state/CameraRenderState;)V",
            at = @At(value = "INVOKE", target = "Lnet/minecraft/client/renderer/entity/ItemEntityRenderer;submitMultipleFromCount(Lcom/mojang/blaze3d/vertex/PoseStack;Lnet/minecraft/client/renderer/SubmitNodeCollector;ILnet/minecraft/client/renderer/entity/state/ItemClusterRenderState;Lnet/minecraft/util/RandomSource;Lnet/minecraft/world/phys/AABB;)V"))
    private void naovisual$layFlat(ItemEntityRenderState state, PoseStack ps, SubmitNodeCollector c, CameraRenderState cam, CallbackInfo ci) {
        if (naovisual$active(state) && naovisual$flat(state)) ps.mulPose(Axis.XP.rotationDegrees(90));
    }
}
