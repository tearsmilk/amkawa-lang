package ruruka.suka.rurukasuka.account;

import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

/** Аккаунт игрока, синхронизированный с сайтом RurukaSuka (баланс + купленная косметика). */
public final class RurukaAccount {
    public static final RurukaAccount LOCAL = new RurukaAccount();

    private String token = null;
    private String uuid = null;
    private String nick = null;
    private int balance = 0;
    private boolean loggedIn = false;
    private final Set<Integer> owned = new HashSet<>();
    private final Set<Integer> equipped = new HashSet<>();
    private final Map<Integer,Integer> variants = new HashMap<>(); // cosmeticId -> variantId

    public boolean isLoggedIn() { return loggedIn; }
    public int coins() { return balance; }
    public String uuid() { return uuid; }
    public String nick() { return nick; }
    public String token() { return token; }
    public boolean owns(int cosmeticId) { return owned.contains(cosmeticId); }
    public boolean isEquipped(int cosmeticId) { return equipped.contains(cosmeticId); }
    public int variantOf(int cosmeticId) { Integer v = variants.get(cosmeticId); return v == null ? 0 : v; }
    public java.util.List<Integer> equippedIds() { return new java.util.ArrayList<>(equipped); }

    public void applyLogin(String token, String uuid, String nick, int balance,
                           List<Integer> ownedList, List<Integer> equippedList, Map<Integer,Integer> variantMap) {
        this.token = token; this.uuid = uuid; this.nick = nick;
        this.balance = balance; this.loggedIn = true;
        setOwned(ownedList);
        setEquipped(equippedList);
        setVariants(variantMap);
    }

    public void applyPurchase(int balance, List<Integer> ownedList) {
        this.balance = balance;
        setOwned(ownedList);
    }

    public void applyMe(int balance, String nick, List<Integer> ownedList, List<Integer> equippedList, Map<Integer,Integer> variantMap) {
        this.balance = balance;
        if (nick != null) this.nick = nick;
        setOwned(ownedList);
        setEquipped(equippedList);
        setVariants(variantMap);
    }

    public void applyEquip(List<Integer> equippedList) { setEquipped(equippedList); }

    public void applyVariants(Map<Integer,Integer> variantMap) { setVariants(variantMap); }

    public void setVariantLocal(int cosmeticId, int variantId) {
        if (variantId > 0) variants.put(cosmeticId, variantId); else variants.remove(cosmeticId);
    }

    public void logout() {
        token = null; uuid = null; nick = null; balance = 0; loggedIn = false;
        owned.clear();
        equipped.clear();
        variants.clear();
    }

    private void setOwned(List<Integer> list) {
        owned.clear();
        if (list != null) owned.addAll(list);
    }

    private void setEquipped(List<Integer> list) {
        equipped.clear();
        if (list != null) equipped.addAll(list);
    }

    private void setVariants(Map<Integer,Integer> map) {
        variants.clear();
        if (map != null) variants.putAll(map);
    }

    private RurukaAccount() {}
}
