package milk.naovisual.modules.client;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.TextSetting;
import net.minecraft.client.player.RemotePlayer;
import net.minecraft.world.entity.EquipmentSlot;

/** Копия игрока на месте для проверки визуалов (только на клиенте). */
public class FakePlayerModule extends Module {
    private final TextSetting name = add(new TextSetting("Имя", "Пусто — ваш ник", "", 16));
    private final BooleanSetting copyArmor = add(new BooleanSetting("Скопировать броню", "", true));
    private RemotePlayer fake;

    public FakePlayerModule() {
        super("FakePlayer", "Фейк-игрок", "Ставит копию вас рядом, чтобы проверить визуалы", ModuleCategory.CLIENT);
    }

    @Override
    public void onEnable() {
        var mc = mc();
        if (mc.player == null || mc.level == null) { setEnabled(false); return; }
        var profile = mc.player.getGameProfile();
        if (!name.get().isBlank()) profile = new com.mojang.authlib.GameProfile(java.util.UUID.nameUUIDFromBytes(("nao:" + name.get()).getBytes()), name.get());
        fake = new RemotePlayer(mc.level, profile);
        fake.setId(-1_000_000 - (int) (System.nanoTime() % 100_000));
        fake.absSnapTo(mc.player.getX(), mc.player.getY(), mc.player.getZ(), mc.player.getYRot(), mc.player.getXRot());
        fake.setYHeadRot(mc.player.getYHeadRot());
        fake.setYBodyRot(mc.player.getYRot());
        fake.setHealth(mc.player.getHealth());
        if (copyArmor.on()) for (EquipmentSlot s : EquipmentSlot.values()) fake.setItemSlot(s, mc.player.getItemBySlot(s).copy());
        mc.level.addEntity(fake);
    }

    @Override
    public void onDisable() {
        if (fake != null) { fake.discard(); fake = null; }
    }

    @Override public void onDisconnect() { fake = null; setEnabled(false); }

    @Override
    public void onTick() {
        if (fake != null && fake.isRemoved()) { fake = null; setEnabled(false); }
    }
}
