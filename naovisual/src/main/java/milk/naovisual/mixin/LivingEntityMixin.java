package milk.naovisual.mixin;

import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.core.util.Targets;
import milk.naovisual.modules.other.HandTweaksModule;
import net.minecraft.client.Minecraft;
import net.minecraft.world.damagesource.DamageSource;
import net.minecraft.world.entity.LivingEntity;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.Inject;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfo;
import org.spongepowered.asm.mixin.injection.callback.CallbackInfoReturnable;

@Mixin(LivingEntity.class)
public abstract class LivingEntityMixin {
    @Inject(method = "getCurrentSwingDuration", at = @At("RETURN"), cancellable = true)
    private void naovisual$swingSpeed(CallbackInfoReturnable<Integer> cir) {
        if ((Object) this != Minecraft.getInstance().player) return;
        HandTweaksModule m = ModuleRegistry.get(HandTweaksModule.class);
        if (m.isEnabled() && m.customSwing()) cir.setReturnValue(Math.max(1, m.swingDuration()));
    }

    @Inject(method = "handleEntityEvent", at = @At("HEAD"))
    private void naovisual$entityEvent(byte id, CallbackInfo ci) {
        if (id == 35) ModuleRegistry.totemPop((LivingEntity) (Object) this);
    }

    @Inject(method = "handleDamageEvent", at = @At("HEAD"))
    private void naovisual$damage(DamageSource source, CallbackInfo ci) {
        LivingEntity self = (LivingEntity) (Object) this;
        if (self.level() != null && self.level().isClientSide()) ModuleRegistry.damage(self);
    }

    @Inject(method = "jumpFromGround", at = @At("HEAD"))
    private void naovisual$jump(CallbackInfo ci) {
        LivingEntity self = (LivingEntity) (Object) this;
        if (self.level() != null && self.level().isClientSide()) ModuleRegistry.jump(self);
    }
}
