// Aminakawa interpreter — Java port (core language).
// Run with JDK 11+ single-file mode:  java Amkawa.java yourfile.amkawa
import java.io.*;
import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import java.util.*;

public class Amkawa {

    // ===== errors / control flow =====
    static class AmkError extends RuntimeException {
        AmkError(String m) { super(m); }
    }
    static class ReturnEx extends RuntimeException {
        final Object value;
        ReturnEx(Object v) { super(null, null, false, false); this.value = v; }
    }

    // ===== tokens =====
    static final Set<String> KEYWORDS = Set.of(
        "tyan","back","moshi","else","while","for","in","and","or","not","hai","iie","mu");

    static class Tok {
        String type; Object value; int line;
        Tok(String t, Object v, int l) { type=t; value=v; line=l; }
    }

    static List<Tok> lex(String s) {
        List<Tok> t = new ArrayList<>();
        int i = 0, n = s.length(), line = 1;
        while (i < n) {
            char c = s.charAt(i);
            if (c == '\n') { t.add(new Tok("NL","\n",line)); line++; i++; continue; }
            if (c == ' ' || c == '\t' || c == '\r') { i++; continue; }
            if (c == '#') { while (i < n && s.charAt(i) != '\n') i++; continue; }
            if (c == '"' || c == '\'') {
                char q = c; i++; StringBuilder b = new StringBuilder();
                while (i < n && s.charAt(i) != q) {
                    char ch = s.charAt(i);
                    if (ch == '\\' && i+1 < n) {
                        char nx = s.charAt(i+1);
                        switch (nx) {
                            case 'n': b.append('\n'); break;
                            case 't': b.append('\t'); break;
                            default: b.append(nx);
                        }
                        i += 2; continue;
                    }
                    if (ch == '\n') line++;
                    b.append(ch); i++;
                }
                if (i >= n) throw new AmkError("line " + line + ": string is missing a closing quote");
                i++; t.add(new Tok("STR", b.toString(), line)); continue;
            }
            if (Character.isDigit(c) || (c == '.' && i+1 < n && Character.isDigit(s.charAt(i+1)))) {
                int st = i; boolean dot = false;
                while (i < n && (Character.isDigit(s.charAt(i)) || s.charAt(i) == '.')) {
                    if (s.charAt(i) == '.') { if (dot) break; dot = true; }
                    i++;
                }
                t.add(new Tok("NUM", Double.parseDouble(s.substring(st, i)), line)); continue;
            }
            if (Character.isLetter(c) || c == '_') {
                int st = i;
                while (i < n && (Character.isLetterOrDigit(s.charAt(i)) || s.charAt(i) == '_')) i++;
                String w = s.substring(st, i);
                t.add(new Tok(KEYWORDS.contains(w) ? w : "NAME", w, line)); continue;
            }
            String two = (i+1 < n) ? s.substring(i, i+2) : "";
            if (two.equals("==")||two.equals("!=")||two.equals("<=")||two.equals(">=")) {
                t.add(new Tok("OP", two, line)); i += 2; continue;
            }
            if ("+-*/%()<>{}[],=".indexOf(c) >= 0) { t.add(new Tok("OP", String.valueOf(c), line)); i++; continue; }
            throw new AmkError("line " + line + ": unexpected character '" + c + "'");
        }
        t.add(new Tok("EOF", null, line));
        return t;
    }

    // ===== AST =====
    sealed interface Node permits NumN,StrN,BoolN,NullN,ListN,NameN,UnaryN,BinN,LogicN,IndexN,CallN,
                                  AssignN,IfN,WhileN,ForN,FuncN,ReturnN,ExprN,BlockN,ProgN {}
    record NumN(double v) implements Node {}
    record StrN(String v) implements Node {}
    record BoolN(boolean v) implements Node {}
    record NullN() implements Node {}
    record ListN(List<Node> items) implements Node {}
    record NameN(String name, int line) implements Node {}
    record UnaryN(String op, Node node, int line) implements Node {}
    record BinN(String op, Node a, Node b, int line) implements Node {}
    record LogicN(String op, Node a, Node b) implements Node {}
    record IndexN(Node target, Node index, int line) implements Node {}
    record CallN(Node callee, List<Node> args, int line) implements Node {}
    record AssignN(Node target, Node value, int line) implements Node {}
    record IfN(Node cond, BlockN then, Node els) implements Node {}
    record WhileN(Node cond, BlockN body) implements Node {}
    record ForN(String var, Node iterable, BlockN body, int line) implements Node {}
    record FuncN(String name, List<String> params, BlockN body, int line) implements Node {}
    record ReturnN(Node value, int line) implements Node {}
    record ExprN(Node expr) implements Node {}
    record BlockN(List<Node> stmts) implements Node {}
    record ProgN(List<Node> stmts) implements Node {}

    // ===== parser =====
    static class Parser {
        List<Tok> t; int i = 0;
        Parser(List<Tok> t) { this.t = t; }
        Tok peek() { return t.get(i); }
        Tok adv() { return t.get(i++); }
        boolean at(String type) { return peek().type.equals(type); }
        boolean atOp(String v) { Tok x = peek(); return x.type.equals("OP") && x.value.equals(v); }
        Tok eatOp(String v) { if (!atOp(v)) throw new AmkError("line " + peek().line + ": expected '" + v + "'"); return adv(); }
        Tok expect(String type, String what) { if (!at(type)) throw new AmkError("line " + peek().line + ": expected " + what); return adv(); }
        void skipNL() { while (at("NL")) adv(); }

        ProgN parse() {
            List<Node> s = new ArrayList<>(); skipNL();
            while (!at("EOF")) { s.add(statement()); skipNL(); }
            return new ProgN(s);
        }
        Node statement() {
            Tok x = peek();
            switch (x.type) {
                case "tyan": return funcdef();
                case "moshi": return ifStmt();
                case "while": return whileStmt();
                case "for": return forStmt();
                case "back": return returnStmt();
            }
            Node e = expression();
            if (atOp("=")) {
                int ln = adv().line; Node val = expression();
                if (!(e instanceof NameN) && !(e instanceof IndexN))
                    throw new AmkError("line " + ln + ": left of '=' must be a variable name");
                return new AssignN(e, val, ln);
            }
            return new ExprN(e);
        }
        BlockN block() {
            eatOp("{"); List<Node> s = new ArrayList<>(); skipNL();
            while (!atOp("}") && !at("EOF")) { s.add(statement()); skipNL(); }
            eatOp("}"); return new BlockN(s);
        }
        Node funcdef() {
            int ln = adv().line; String name = (String) expect("NAME","function name").value;
            eatOp("("); skipNL(); List<String> ps = new ArrayList<>();
            if (!atOp(")")) {
                ps.add((String) expect("NAME","parameter name").value); skipNL();
                while (atOp(",")) { adv(); skipNL(); ps.add((String) expect("NAME","parameter name").value); skipNL(); }
            }
            eatOp(")"); return new FuncN(name, ps, block(), ln);
        }
        Node ifStmt() {
            adv(); Node cond = expression(); BlockN then = block(); Node els = null; skipNL();
            if (at("else")) { adv(); skipNL(); els = at("moshi") ? ifStmt() : block(); }
            return new IfN(cond, then, els);
        }
        Node whileStmt() { adv(); return new WhileN(expression(), block()); }
        Node forStmt() {
            int ln = adv().line; String v = (String) expect("NAME","loop variable").value;
            expect("in","'in'"); Node it = expression(); return new ForN(v, it, block(), ln);
        }
        Node returnStmt() {
            int ln = adv().line;
            if (at("NL") || atOp("}") || at("EOF")) return new ReturnN(null, ln);
            return new ReturnN(expression(), ln);
        }
        Node expression() { return logicOr(); }
        Node logicOr() { Node a = logicAnd(); while (at("or")) { adv(); a = new LogicN("or", a, logicAnd()); } return a; }
        Node logicAnd() { Node a = equality(); while (at("and")) { adv(); a = new LogicN("and", a, equality()); } return a; }
        Node equality() { Node a = comparison(); while (atOp("==")||atOp("!=")) { Tok o = adv(); a = new BinN((String)o.value, a, comparison(), o.line); } return a; }
        Node comparison() { Node a = term(); while (atOp("<")||atOp(">")||atOp("<=")||atOp(">=")) { Tok o = adv(); a = new BinN((String)o.value, a, term(), o.line); } return a; }
        Node term() { Node a = factor(); while (atOp("+")||atOp("-")) { Tok o = adv(); a = new BinN((String)o.value, a, factor(), o.line); } return a; }
        Node factor() { Node a = unary(); while (atOp("*")||atOp("/")||atOp("%")) { Tok o = adv(); a = new BinN((String)o.value, a, unary(), o.line); } return a; }
        Node unary() {
            if (at("not")) { Tok o = adv(); return new UnaryN("not", unary(), o.line); }
            if (atOp("-")) { Tok o = adv(); return new UnaryN("-", unary(), o.line); }
            return postfix();
        }
        Node postfix() {
            Node node = primary();
            while (true) {
                if (atOp("(")) {
                    Tok o = adv(); skipNL(); List<Node> args = new ArrayList<>();
                    if (!atOp(")")) {
                        args.add(expression()); skipNL();
                        while (atOp(",")) { adv(); skipNL(); if (atOp(")")) break; args.add(expression()); skipNL(); }
                    }
                    eatOp(")"); node = new CallN(node, args, o.line);
                } else if (atOp("[")) {
                    Tok o = adv(); Node idx = expression(); eatOp("]"); node = new IndexN(node, idx, o.line);
                } else break;
            }
            return node;
        }
        Node primary() {
            Tok x = peek();
            switch (x.type) {
                case "NUM": adv(); return new NumN((Double) x.value);
                case "STR": adv(); return new StrN((String) x.value);
                case "hai": adv(); return new BoolN(true);
                case "iie": adv(); return new BoolN(false);
                case "mu": adv(); return new NullN();
                case "NAME": adv(); return new NameN((String) x.value, x.line);
            }
            if (atOp("(")) { adv(); skipNL(); Node e = expression(); skipNL(); eatOp(")"); return e; }
            if (atOp("[")) {
                adv(); skipNL(); List<Node> items = new ArrayList<>();
                if (!atOp("]")) {
                    items.add(expression()); skipNL();
                    while (atOp(",")) { adv(); skipNL(); if (atOp("]")) break; items.add(expression()); skipNL(); }
                }
                eatOp("]"); return new ListN(items);
            }
            throw new AmkError("line " + x.line + ": unexpected " + (x.value != null ? x.value : "end of file"));
        }
    }

    // ===== values =====
    static class FuncVal { FuncN decl; Env env; FuncVal(FuncN d, Env e) { decl=d; env=e; } }
    interface Builtin { Object call(List<Object> args); }

    static class Env {
        Map<String,Object> vars = new HashMap<>(); Env parent;
        Env(Env p) { parent = p; }
        Object get(String name, int line) {
            for (Env e = this; e != null; e = e.parent) if (e.vars.containsKey(name)) return e.vars.get(name);
            throw new AmkError("line " + line + ": unknown name '" + name + "'");
        }
        void assign(String name, Object v) {
            for (Env e = this; e != null; e = e.parent) if (e.vars.containsKey(name)) { e.vars.put(name, v); return; }
            vars.put(name, v);
        }
        void define(String name, Object v) { vars.put(name, v); }
    }

    // ===== helpers =====
    static boolean isNum(Object v) { return v instanceof Double; }
    static boolean truthy(Object v) {
        if (v == null || Boolean.FALSE.equals(v)) return false;
        if (Boolean.TRUE.equals(v)) return true;
        if (v instanceof Double d) return d != 0.0;
        if (v instanceof String s) return !s.isEmpty();
        if (v instanceof List<?> l) return !l.isEmpty();
        return true;
    }
    static String fmtNum(double d) {
        if (!Double.isInfinite(d) && d == Math.rint(d) && Math.abs(d) < 1e15) return Long.toString((long) d);
        return Double.toString(d);
    }
    @SuppressWarnings("unchecked")
    static String toText(Object v) {
        if (Boolean.TRUE.equals(v)) return "hai";
        if (Boolean.FALSE.equals(v)) return "iie";
        if (v == null) return "mu";
        if (v instanceof Double d) return fmtNum(d);
        if (v instanceof List<?> l) {
            StringBuilder b = new StringBuilder("[");
            for (int k = 0; k < l.size(); k++) { if (k > 0) b.append(", "); b.append(toText(l.get(k))); }
            return b.append("]").toString();
        }
        return v.toString();
    }
    static String typeName(Object v) {
        if (v instanceof Boolean) return "bool";
        if (v == null) return "mu";
        if (v instanceof Double) return "number";
        if (v instanceof String) return "text";
        if (v instanceof List) return "list";
        return "value";
    }
    static boolean deepEq(Object a, Object b) {
        if (a instanceof List<?> la && b instanceof List<?> lb) {
            if (la.size() != lb.size()) return false;
            for (int k = 0; k < la.size(); k++) if (!deepEq(la.get(k), lb.get(k))) return false;
            return true;
        }
        return Objects.equals(a, b);
    }

    // ===== interpreter =====
    Env globals = new Env(null);
    BufferedReader stdin = new BufferedReader(new InputStreamReader(System.in, StandardCharsets.UTF_8));

    Amkawa() { installBuiltins(); }

    void run(ProgN p) {
        for (Node s : p.stmts()) {
            try { exec(s, globals); }
            catch (ReturnEx r) { throw new AmkError("'back' can only be used inside a function (tyan)"); }
        }
    }

    void execBlock(BlockN b, Env env) { for (Node s : b.stmts()) exec(s, env); }

    void exec(Node node, Env env) {
        if (node instanceof ExprN e) { eval(e.expr(), env); return; }
        if (node instanceof FuncN f) { env.define(f.name(), new FuncVal(f, env)); return; }
        if (node instanceof AssignN a) {
            Object val = eval(a.value(), env);
            if (a.target() instanceof NameN nm) env.assign(nm.name(), val);
            else { IndexN ix = (IndexN) a.target(); Object tg = eval(ix.target(), env); Object idx = eval(ix.index(), env); setIndex(tg, idx, val, ix.line()); }
            return;
        }
        if (node instanceof IfN f) {
            if (truthy(eval(f.cond(), env))) execBlock(f.then(), env);
            else if (f.els() != null) { if (f.els() instanceof BlockN bl) execBlock(bl, env); else exec(f.els(), env); }
            return;
        }
        if (node instanceof WhileN w) {
            long guard = 0;
            while (truthy(eval(w.cond(), env))) { execBlock(w.body(), env); if (++guard > 100000000L) throw new AmkError("loop ran too long (possible infinite loop)"); }
            return;
        }
        if (node instanceof ForN fr) {
            Object coll = eval(fr.iterable(), env);
            if (coll instanceof List<?> l) { for (Object item : l) { env.assign(fr.var(), item); execBlock(fr.body(), env); } }
            else if (coll instanceof String s) { for (int k = 0; k < s.length(); k++) { env.assign(fr.var(), String.valueOf(s.charAt(k))); execBlock(fr.body(), env); } }
            else throw new AmkError("line " + fr.line() + ": 'for ... in ...' needs a list or text");
            return;
        }
        if (node instanceof ReturnN r) { throw new ReturnEx(r.value() != null ? eval(r.value(), env) : null); }
        throw new AmkError("cannot run node " + node.getClass().getSimpleName());
    }

    @SuppressWarnings("unchecked")
    Object eval(Node node, Env env) {
        if (node instanceof NumN n) return n.v();
        if (node instanceof StrN n) return n.v();
        if (node instanceof BoolN n) return n.v();
        if (node instanceof NullN) return null;
        if (node instanceof ListN n) {
            List<Object> out = new ArrayList<>();
            for (Node e : n.items()) out.add(eval(e, env));
            return out;
        }
        if (node instanceof NameN n) return env.get(n.name(), n.line());
        if (node instanceof UnaryN u) {
            Object v = eval(u.node(), env);
            if (u.op().equals("not")) return !truthy(v);
            if (!isNum(v)) throw new AmkError("line " + u.line() + ": minus works only on a number");
            return -((Double) v);
        }
        if (node instanceof LogicN lg) {
            Object left = eval(lg.a(), env);
            if (lg.op().equals("and")) return truthy(left) ? truthy(eval(lg.b(), env)) : Boolean.FALSE;
            return truthy(left) ? Boolean.TRUE : truthy(eval(lg.b(), env));
        }
        if (node instanceof BinN b) return binop(b, env);
        if (node instanceof IndexN ix) { Object tg = eval(ix.target(), env); Object idx = eval(ix.index(), env); return getIndex(tg, idx, ix.line()); }
        if (node instanceof CallN c) {
            Object callee = eval(c.callee(), env);
            List<Object> args = new ArrayList<>();
            for (Node a : c.args()) args.add(eval(a, env));
            return call(callee, args, c.line());
        }
        throw new AmkError("cannot evaluate " + node.getClass().getSimpleName());
    }

    @SuppressWarnings("unchecked")
    Object binop(BinN node, Env env) {
        String op = node.op(); int line = node.line();
        Object a = eval(node.a(), env), b = eval(node.b(), env);
        switch (op) {
            case "+":
                if (a instanceof String || b instanceof String) return toText(a) + toText(b);
                if (a instanceof List && b instanceof List) { List<Object> r = new ArrayList<>((List<Object>)a); r.addAll((List<Object>)b); return r; }
                numck(a, b, line, "+"); return (Double)a + (Double)b;
            case "-": numck(a,b,line,"-"); return (Double)a - (Double)b;
            case "*":
                if (a instanceof String s && b instanceof Double d) return s.repeat(Math.max(0,(int)(double)d));
                if (b instanceof String s2 && a instanceof Double d2) return s2.repeat(Math.max(0,(int)(double)d2));
                numck(a,b,line,"*"); return (Double)a * (Double)b;
            case "/": numck(a,b,line,"/"); if ((Double)b == 0.0) throw new AmkError("line " + line + ": division by zero"); return (Double)a / (Double)b;
            case "%": numck(a,b,line,"%"); if ((Double)b == 0.0) throw new AmkError("line " + line + ": division by zero"); return (Double)a % (Double)b;
            case "==": return deepEq(a, b);
            case "!=": return !deepEq(a, b);
            default:
                boolean ok = (isNum(a) && isNum(b)) || (a instanceof String && b instanceof String);
                if (!ok) throw new AmkError("line " + line + ": cannot compare " + typeName(a) + " and " + typeName(b));
                int cmp;
                if (a instanceof Double) cmp = Double.compare((Double)a, (Double)b);
                else cmp = ((String)a).compareTo((String)b);
                switch (op) { case "<": return cmp < 0; case ">": return cmp > 0; case "<=": return cmp <= 0; default: return cmp >= 0; }
        }
    }
    static void numck(Object a, Object b, int line, String op) {
        if (!(isNum(a) && isNum(b))) throw new AmkError("line " + line + ": '" + op + "' needs two numbers, got " + typeName(a) + " and " + typeName(b));
    }

    @SuppressWarnings("unchecked")
    Object call(Object callee, List<Object> args, int line) {
        if (callee instanceof FuncVal fv) {
            FuncN decl = fv.decl;
            if (args.size() != decl.params().size())
                throw new AmkError("line " + line + ": function '" + decl.name() + "' wants " + decl.params().size() + " argument(s), got " + args.size());
            Env local = new Env(fv.env);
            for (int k = 0; k < args.size(); k++) local.define(decl.params().get(k), args.get(k));
            try { execBlock(decl.body(), local); } catch (ReturnEx r) { return r.value; }
            return null;
        }
        if (callee instanceof Builtin bi) return bi.call(args);
        throw new AmkError("line " + line + ": this is not a function, cannot call it with ()");
    }

    @SuppressWarnings("unchecked")
    Object getIndex(Object target, Object idx, int line) {
        if (!(idx instanceof Double d) || d != Math.rint(d)) throw new AmkError("line " + line + ": index must be a whole number");
        int i = (int)(double)(Double) idx;
        if (target instanceof List<?> l) { if (i < 0) i += l.size(); if (i < 0 || i >= l.size()) throw new AmkError("line " + line + ": index out of range"); return l.get(i); }
        if (target instanceof String s) { if (i < 0) i += s.length(); if (i < 0 || i >= s.length()) throw new AmkError("line " + line + ": index out of range"); return String.valueOf(s.charAt(i)); }
        throw new AmkError("line " + line + ": only a list or text can be indexed");
    }
    @SuppressWarnings("unchecked")
    void setIndex(Object target, Object idx, Object val, int line) {
        if (!(idx instanceof Double d) || d != Math.rint(d)) throw new AmkError("line " + line + ": index must be a whole number");
        int i = (int)(double)(Double) idx;
        if (target instanceof List) { List<Object> l = (List<Object>) target; if (i < 0) i += l.size(); if (i < 0 || i >= l.size()) throw new AmkError("line " + line + ": index out of range"); l.set(i, val); return; }
        throw new AmkError("line " + line + ": only a list can be changed by index");
    }

    @SuppressWarnings("unchecked")
    void installBuiltins() {
        Env g = globals;
        g.define("nya", (Builtin) a -> {
            StringBuilder b = new StringBuilder();
            for (int k = 0; k < a.size(); k++) { if (k > 0) b.append(" "); b.append(toText(a.get(k))); }
            System.out.println(b.toString()); return null;
        });
        g.define("len", (Builtin) a -> {
            Object x = a.get(0);
            if (x instanceof List<?> l) return (double) l.size();
            if (x instanceof String s) return (double) s.length();
            throw new AmkError("len() needs a list or text");
        });
        g.define("num", (Builtin) a -> {
            Object x = a.get(0);
            if (x instanceof Double) return x;
            if (x instanceof Boolean bb) return bb ? 1.0 : 0.0;
            if (x instanceof String s) { try { return Double.parseDouble(s.trim()); } catch (Exception e) { throw new AmkError("cannot turn '" + s + "' into a number"); } }
            throw new AmkError("num() does not understand this value");
        });
        g.define("str", (Builtin) a -> toText(a.get(0)));
        g.define("ask", (Builtin) a -> {
            if (!a.isEmpty()) { System.out.print(toText(a.get(0))); System.out.flush(); }
            try { String line = stdin.readLine(); return line == null ? "" : line; }
            catch (IOException e) { return ""; }
        });
        g.define("range", (Builtin) a -> {
            int start, end, step = 1;
            if (a.size() == 1) { start = 0; end = (int)(double)(Double) a.get(0); }
            else { start = (int)(double)(Double) a.get(0); end = (int)(double)(Double) a.get(1); if (a.size() >= 3) step = (int)(double)(Double) a.get(2); }
            if (step == 0) throw new AmkError("range step cannot be 0");
            List<Object> out = new ArrayList<>();
            if (step > 0) for (int k = start; k < end; k += step) out.add((double) k);
            else for (int k = start; k > end; k += step) out.add((double) k);
            return out;
        });
        g.define("push", (Builtin) a -> {
            if (!(a.get(0) instanceof List)) throw new AmkError("push() needs a list");
            ((List<Object>) a.get(0)).add(a.get(1)); return null;
        });
        g.define("random", (Builtin) a -> {
            int lo = (int)(double)(Double) a.get(0), hi = (int)(double)(Double) a.get(1);
            if (hi < lo) { int t = lo; lo = hi; hi = t; }
            return (double)(lo + (int)(Math.random() * (hi - lo + 1)));
        });
    }

    // ===== entry =====
    public static void main(String[] argv) throws IOException {
        System.setOut(new PrintStream(new FileOutputStream(FileDescriptor.out), true, StandardCharsets.UTF_8));
        if (argv.length < 1) { System.err.println("usage: java Amkawa.java file.amkawa"); System.exit(1); }
        String src = Files.readString(Path.of(argv[0]));
        try {
            ProgN prog = new Parser(lex(src)).parse();
            new Amkawa().run(prog);
        } catch (AmkError e) {
            System.out.println("amkawa error: " + e.getMessage());
            System.exit(1);
        }
    }
}
