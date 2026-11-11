package milk.naovisual.mixin;

import milk.naovisual.core.module.ModuleRegistry;
import milk.naovisual.modules.other.NameProtectModule;
import net.minecraft.client.GuiMessageTag;
import net.minecraft.client.gui.components.ChatComponent;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MessageSignature;
import org.spongepowered.asm.mixin.Mixin;
import org.spongepowered.asm.mixin.injection.At;
import org.spongepowered.asm.mixin.injection.ModifyVariable;

@Mixin(ChatComponent.class)
public abstract class ChatComponentMixin {
    @ModifyVariable(method = "addMessage(Lnet/minecraft/network/chat/Component;Lnet/minecraft/network/chat/MessageSignature;Lnet/minecraft/client/GuiMessageTag;)V",
            at = @At("HEAD"), argsOnly = true, ordinal = 0)
    private Component naovisual$protect(Component message, Component original, MessageSignature signature, GuiMessageTag tag) {
        NameProtectModule m = ModuleRegistry.get(NameProtectModule.class);
        return m.isEnabled() ? m.protect(message) : message;
    }
}
