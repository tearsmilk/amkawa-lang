package milk.naovisual.modules.client;

import milk.naovisual.NaoVisual;
import milk.naovisual.core.discord.DiscordRpc;
import milk.naovisual.core.module.Module;
import milk.naovisual.core.module.ModuleCategory;
import milk.naovisual.core.setting.BooleanSetting;
import milk.naovisual.core.setting.TextSetting;

/** Discord Rich Presence: сервер, ник, время в игре. */
public class DiscordModule extends Module {
    private final TextSetting appId = add(new TextSetting("ID приложения", "Discord Application ID (своё — на discord.com/developers)", "1562885493018988664", 32));
    private final BooleanSetting showServer = add(new BooleanSetting("Показывать сервер", "", true));
    private final BooleanSetting showName = add(new BooleanSetting("Показывать ник", "", true));
    private final TextSetting largeImage = add(new TextSetting("Картинка", "Ключ ассета приложения", "logo", 32));
    private final DiscordRpc rpc = new DiscordRpc();
    private final long startedAt = System.currentTimeMillis();
    private int ticks;

    public DiscordModule() {
        super("Discord", "Discord", "Статус активности в Discord: сервер, ник и время в игре", ModuleCategory.CLIENT);
    }

    @Override public void onEnable() { ticks = 0; }

    @Override
    public void onDisable() {
        rpc.clearActivity();
        rpc.close();
    }

    @Override
    public void onTick() {
        if (++ticks % 100 != 1) return;   // раз в 5 секунд
        if (!rpc.isConnected()) rpc.connect(appId.get().trim());
        if (!rpc.isConnected()) return;
        String details = NaoVisual.NAME + " " + NaoVisual.version();
        String state;
        if (mc().level == null) state = "В меню";
        else if (mc().getCurrentServer() != null) state = showServer.on() ? "Играет на " + mc().getCurrentServer().ip : "На сервере";
        else state = "Одиночная игра";
        if (showName.on() && mc().player != null) details = mc().player.getGameProfile().name() + " • " + details;
        rpc.setActivity(details, state, largeImage.get(), NaoVisual.NAME, null, null, startedAt);
    }

    public void shutdown() { rpc.clearActivity(); rpc.close(); }
}
