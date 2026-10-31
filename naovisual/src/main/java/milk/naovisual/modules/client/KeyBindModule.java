package milk.naovisual.modules.client;

import milk.naovisual.core.hud.HudEditorScreen;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.KeybindSetting;
import milk.naovisual.core.util.Friends;
import net.minecraft.world.entity.player.Player;
import org.lwjgl.glfw.GLFW;

import java.util.ArrayList;
import java.util.List;

/** Горячие клавиши клиента: редактор HUD, добавить друга под прицелом, панель клавиш модулей. */
public class KeyBindModule extends Module {
    private final KeybindSetting hudEditor = add(new KeybindSetting("Редактор HUD", "Открыть редактор позиций", GLFW.GLFW_KEY_RIGHT_CONTROL));
    private final KeybindSetting friendKey = add(new KeybindSetting("Друг под прицелом", "Добавить / убрать игрока под прицелом из друзей", KeybindSetting.NONE));
    private final BooleanSetting chatHint = add(new BooleanSetting("Подсказки в чат", "Сообщать о действиях клавиш", true));

    public KeyBindModule() {
        super("KeyBind", "Клавиши", "Горячие клавиши клиента (меню — правый Shift, задаётся в настройках управления)", ModuleCategory.CLIENT);
    }

    @Override public boolean defaultEnabled() { return true; }

    public List<Integer> extraKeys() {
        List<Integer> keys = new ArrayList<>();
        if (isEnabled()) {
            if (hudEditor.isBound()) keys.add(hudEditor.get());
            if (friendKey.isBound()) keys.add(friendKey.get());
        }
        return keys;
    }

    /** @return true, если клавиша обработана. */
    public boolean handle(int key) {
        if (!isEnabled()) return false;
        if (hudEditor.isBound() && key == hudEditor.get()) { mc().setScreen(new HudEditorScreen(null)); return true; }
        if (friendKey.isBound() && key == friendKey.get()) {
            if (mc().crosshairPickEntity instanceof Player p && p != mc().player) {
                String n = p.getGameProfile().name();
                Friends.toggle(n);
                if (chatHint.on() && mc().player != null) mc().gui.getChat().addMessage(net.minecraft.network.chat.Component.literal("§7[§6Nao§7] " + (Friends.contains(n) ? "§f" + n + " §aдобавлен в друзья" : "§f" + n + " §cубран из друзей")));
            }
            return true;
        }
        return false;
    }
}
