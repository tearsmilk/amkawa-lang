package milk.naovisual.modules.other;

import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.TextSetting;
import milk.naovisual.core.util.Friends;
import net.minecraft.network.chat.Component;
import net.minecraft.network.chat.MutableComponent;
import net.minecraft.network.chat.contents.PlainTextContents;

/** Подменяет ваш ник (и ники друзей) в чате на заданный. */
public class NameProtectModule extends Module {
    private final TextSetting fake = add(new TextSetting("Ник", "На что заменить", "Nao", 24));
    private final BooleanSetting friends = add(new BooleanSetting("Друзей тоже", "Заменять ники друзей на «Друг»", false));

    public NameProtectModule() {
        super("NameProtect", "Защита ника", "Скрывает ваш ник в чате и на экране", ModuleCategory.OTHER);
    }

    public String fakeName() { return fake.get().isBlank() ? "Nao" : fake.get(); }

    public Component protect(Component c) {
        if (mc().player == null) return c;
        String real = mc().player.getGameProfile().name();
        if (real.isEmpty()) return c;
        return replace(c, real);
    }

    private Component replace(Component c, String real) {
        MutableComponent out;
        if (c.getContents() instanceof PlainTextContents pt) {
            out = Component.literal(swap(pt.text(), real));
        } else {
            out = c.plainCopy();
        }
        out.setStyle(c.getStyle());
        for (Component s : c.getSiblings()) out.append(replace(s, real));
        return out;
    }

    public String swap(String text, String real) {
        if (text.isEmpty()) return text;
        String r = text.replace(real, fakeName());
        if (friends.on()) for (String f : Friends.all()) r = r.replace(f, "Друг");
        return r;
    }
}
