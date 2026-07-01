/* Aminakawa interpreter — C port (core language).
 * Build:  gcc -O2 -o amkawa amkawa.c
 * Run:    ./amkawa yourfile.amkawa
 * Note: this is a small tree-walking interpreter. For simplicity it never frees
 * memory (programs are short-lived) — that's fine for a reference implementation.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>
#include <math.h>
#include <setjmp.h>
#include <stdarg.h>
#include <time.h>

/* ---------- errors ---------- */
static jmp_buf g_err;
static char g_msg[600];
static void amk_error(int line, const char *fmt, ...) {
    char buf[500];
    va_list ap; va_start(ap, fmt); vsnprintf(buf, sizeof buf, fmt, ap); va_end(ap);
    if (line > 0) snprintf(g_msg, sizeof g_msg, "line %d: %s", line, buf);
    else snprintf(g_msg, sizeof g_msg, "%s", buf);
    longjmp(g_err, 1);
}
static void *xmalloc(size_t n) { void *p = malloc(n); if (!p) { fprintf(stderr, "out of memory\n"); exit(1); } return p; }
static char *xstrdup(const char *s) { char *r = xmalloc(strlen(s) + 1); strcpy(r, s); return r; }
static char *strcat2(const char *a, const char *b) {
    char *r = xmalloc(strlen(a) + strlen(b) + 1); strcpy(r, a); strcat(r, b); return r;
}

/* ---------- values ---------- */
typedef enum { T_NUM, T_STR, T_BOOL, T_NIL, T_LIST, T_FUNC, T_BUILTIN } VType;
typedef struct Value Value;
typedef struct { Value *items; int len, cap; } List;
typedef struct Node Node;
typedef struct Env Env;
typedef struct { Node *decl; Env *env; } Func;
typedef Value (*BuiltinFn)(Value *args, int n);
struct Value {
    VType t;
    union { double num; char *str; int b; List *list; Func *func; BuiltinFn builtin; } as;
};

static Value V_NIL(void) { Value v; v.t = T_NIL; return v; }
static Value V_NUM(double d) { Value v; v.t = T_NUM; v.as.num = d; return v; }
static Value V_STR(char *s) { Value v; v.t = T_STR; v.as.str = s; return v; }
static Value V_BOOL(int b) { Value v; v.t = T_BOOL; v.as.b = b ? 1 : 0; return v; }
static Value V_LIST(List *l) { Value v; v.t = T_LIST; v.as.list = l; return v; }
static List *new_list(void) { List *l = xmalloc(sizeof(List)); l->items = NULL; l->len = 0; l->cap = 0; return l; }
static void list_push(List *l, Value v) {
    if (l->len == l->cap) { l->cap = l->cap ? l->cap * 2 : 8; l->items = realloc(l->items, l->cap * sizeof(Value)); }
    l->items[l->len++] = v;
}

static int is_num(Value v) { return v.t == T_NUM; }
static int truthy(Value v) {
    switch (v.t) {
        case T_NIL: return 0;
        case T_BOOL: return v.as.b;
        case T_NUM: return v.as.num != 0.0;
        case T_STR: return v.as.str[0] != '\0';
        case T_LIST: return v.as.list->len != 0;
        default: return 1;
    }
}
static const char *type_name(Value v) {
    switch (v.t) { case T_BOOL: return "bool"; case T_NIL: return "mu"; case T_NUM: return "number";
        case T_STR: return "text"; case T_LIST: return "list"; default: return "value"; }
}
static char *fmt_num(double d) {
    char buf[64];
    if (isfinite(d) && d == (double)(long long)d && fabs(d) < 9e15) snprintf(buf, sizeof buf, "%lld", (long long)d);
    else snprintf(buf, sizeof buf, "%g", d);
    return xstrdup(buf);
}
static char *to_text(Value v) {
    switch (v.t) {
        case T_BOOL: return xstrdup(v.as.b ? "hai" : "iie");
        case T_NIL: return xstrdup("mu");
        case T_NUM: return fmt_num(v.as.num);
        case T_STR: return xstrdup(v.as.str);
        case T_LIST: {
            char *r = xstrdup("[");
            for (int i = 0; i < v.as.list->len; i++) {
                if (i) r = strcat2(r, ", ");
                r = strcat2(r, to_text(v.as.list->items[i]));
            }
            return strcat2(r, "]");
        }
        default: return xstrdup("<function>");
    }
}
static int deep_eq(Value a, Value b) {
    if (a.t == T_LIST && b.t == T_LIST) {
        if (a.as.list->len != b.as.list->len) return 0;
        for (int i = 0; i < a.as.list->len; i++) if (!deep_eq(a.as.list->items[i], b.as.list->items[i])) return 0;
        return 1;
    }
    if (a.t != b.t) return 0;
    switch (a.t) {
        case T_NUM: return a.as.num == b.as.num;
        case T_STR: return strcmp(a.as.str, b.as.str) == 0;
        case T_BOOL: return a.as.b == b.as.b;
        case T_NIL: return 1;
        default: return a.as.func == b.as.func;
    }
}

/* ---------- tokens ---------- */
typedef struct { const char *type; char *sval; double nval; int line; } Tok;
static const char *KW[] = { "tyan","back","moshi","else","while","for","in","and","or","not","hai","iie","mu", NULL };
static const char *keyword(const char *w) {
    for (int i = 0; KW[i]; i++) if (strcmp(KW[i], w) == 0) return KW[i];
    return NULL;
}
typedef struct { Tok *a; int len, cap; } TokList;
static void tok_push(TokList *t, const char *type, char *sval, double nval, int line) {
    if (t->len == t->cap) { t->cap = t->cap ? t->cap * 2 : 64; t->a = realloc(t->a, t->cap * sizeof(Tok)); }
    t->a[t->len].type = type; t->a[t->len].sval = sval; t->a[t->len].nval = nval; t->a[t->len].line = line; t->len++;
}
static int id_start(unsigned char c) { return isalpha(c) || c == '_' || c >= 0x80; }
static int id_cont(unsigned char c) { return isalnum(c) || c == '_' || c >= 0x80; }

static TokList lex(const char *s) {
    TokList t = {0}; int i = 0, line = 1; int n = (int)strlen(s);
    while (i < n) {
        unsigned char c = s[i];
        if (c == '\n') { tok_push(&t, "NL", NULL, 0, line); line++; i++; continue; }
        if (c == ' ' || c == '\t' || c == '\r') { i++; continue; }
        if (c == '#') { while (i < n && s[i] != '\n') i++; continue; }
        if (c == '"' || c == '\'') {
            char q = c; i++; char *buf = xmalloc(n - i + 2); int bl = 0;
            while (i < n && s[i] != q) {
                if (s[i] == '\\' && i + 1 < n) {
                    char nx = s[i + 1];
                    buf[bl++] = (nx == 'n') ? '\n' : (nx == 't') ? '\t' : nx;
                    i += 2; continue;
                }
                if (s[i] == '\n') line++;
                buf[bl++] = s[i++];
            }
            if (i >= n) amk_error(line, "string is missing a closing quote");
            i++; buf[bl] = '\0'; tok_push(&t, "STR", buf, 0, line); continue;
        }
        if (isdigit(c) || (c == '.' && i + 1 < n && isdigit((unsigned char)s[i + 1]))) {
            int st = i, dot = 0;
            while (i < n && (isdigit((unsigned char)s[i]) || s[i] == '.')) {
                if (s[i] == '.') { if (dot) break; dot = 1; }
                i++;
            }
            char *num = xmalloc(i - st + 1); memcpy(num, s + st, i - st); num[i - st] = '\0';
            tok_push(&t, "NUM", NULL, atof(num), line); continue;
        }
        if (id_start(c)) {
            int st = i;
            while (i < n && id_cont((unsigned char)s[i])) i++;
            char *w = xmalloc(i - st + 1); memcpy(w, s + st, i - st); w[i - st] = '\0';
            const char *kw = keyword(w);
            tok_push(&t, kw ? kw : "NAME", w, 0, line); continue;
        }
        if (i + 1 < n) {
            char two[3] = { s[i], s[i + 1], 0 };
            if (!strcmp(two, "==") || !strcmp(two, "!=") || !strcmp(two, "<=") || !strcmp(two, ">=")) {
                tok_push(&t, "OP", xstrdup(two), 0, line); i += 2; continue;
            }
        }
        if (strchr("+-*/%()<>{}[],=", c)) { char op[2] = { c, 0 }; tok_push(&t, "OP", xstrdup(op), 0, line); i++; continue; }
        amk_error(line, "unexpected character '%c'", c);
    }
    tok_push(&t, "EOF", NULL, 0, line);
    return t;
}

/* ---------- AST ---------- */
typedef enum { N_NUM,N_STR,N_BOOL,N_NIL,N_LIST,N_NAME,N_UNARY,N_BIN,N_LOGIC,N_INDEX,N_CALL,
               N_ASSIGN,N_IF,N_WHILE,N_FOR,N_FUNC,N_RETURN,N_EXPR,N_BLOCK,N_PROG } NKind;
struct Node {
    NKind kind; int line;
    double num; int bval; char *str;      /* op/name/strval */
    Node *a, *b, *c;                       /* children */
    Node **kids; int nkids;                /* list items / call args / block stmts */
    char **names; int nnames;              /* func params */
};
static Node *newnode(NKind k) { Node *n = xmalloc(sizeof(Node)); memset(n, 0, sizeof(Node)); n->kind = k; return n; }

/* ---------- parser ---------- */
typedef struct { Tok *t; int i; } Parser;
static Tok *pk(Parser *p) { return &p->t[p->i]; }
static Tok *adv(Parser *p) { return &p->t[p->i++]; }
static int at(Parser *p, const char *type) { return strcmp(pk(p)->type, type) == 0; }
static int atop(Parser *p, const char *v) { Tok *x = pk(p); return strcmp(x->type, "OP") == 0 && strcmp(x->sval, v) == 0; }
static Tok *eatop(Parser *p, const char *v) { if (!atop(p, v)) amk_error(pk(p)->line, "expected '%s'", v); return adv(p); }
static Tok *expect(Parser *p, const char *type, const char *what) { if (!at(p, type)) amk_error(pk(p)->line, "expected %s", what); return adv(p); }
static void skipnl(Parser *p) { while (at(p, "NL")) adv(p); }

static void kids_push(Node *n, Node *k) {
    n->kids = realloc(n->kids, (n->nkids + 1) * sizeof(Node *)); n->kids[n->nkids++] = k;
}
static void names_push(Node *n, char *nm) {
    n->names = realloc(n->names, (n->nnames + 1) * sizeof(char *)); n->names[n->nnames++] = nm;
}

static Node *expression(Parser *p);
static Node *block(Parser *p);
static Node *statement(Parser *p);

static Node *funcdef(Parser *p) {
    Node *n = newnode(N_FUNC); n->line = adv(p)->line;
    n->str = expect(p, "NAME", "function name")->sval;
    eatop(p, "("); skipnl(p);
    if (!atop(p, ")")) {
        names_push(n, expect(p, "NAME", "parameter name")->sval); skipnl(p);
        while (atop(p, ",")) { adv(p); skipnl(p); names_push(n, expect(p, "NAME", "parameter name")->sval); skipnl(p); }
    }
    eatop(p, ")"); n->b = block(p); return n;
}
static Node *ifstmt(Parser *p) {
    Node *n = newnode(N_IF); adv(p);
    n->a = expression(p); n->b = block(p); skipnl(p);
    if (at(p, "else")) { adv(p); skipnl(p); n->c = at(p, "moshi") ? ifstmt(p) : block(p); }
    return n;
}
static Node *whilestmt(Parser *p) { Node *n = newnode(N_WHILE); adv(p); n->a = expression(p); n->b = block(p); return n; }
static Node *forstmt(Parser *p) {
    Node *n = newnode(N_FOR); n->line = adv(p)->line;
    n->str = expect(p, "NAME", "loop variable")->sval;
    expect(p, "in", "'in'"); n->a = expression(p); n->b = block(p); return n;
}
static Node *returnstmt(Parser *p) {
    Node *n = newnode(N_RETURN); n->line = adv(p)->line;
    if (at(p, "NL") || atop(p, "}") || at(p, "EOF")) return n;
    n->a = expression(p); return n;
}
static Node *primary(Parser *p) {
    Tok *x = pk(p);
    if (!strcmp(x->type, "NUM")) { adv(p); Node *n = newnode(N_NUM); n->num = x->nval; return n; }
    if (!strcmp(x->type, "STR")) { adv(p); Node *n = newnode(N_STR); n->str = x->sval; return n; }
    if (!strcmp(x->type, "hai")) { adv(p); Node *n = newnode(N_BOOL); n->bval = 1; return n; }
    if (!strcmp(x->type, "iie")) { adv(p); Node *n = newnode(N_BOOL); n->bval = 0; return n; }
    if (!strcmp(x->type, "mu")) { adv(p); return newnode(N_NIL); }
    if (!strcmp(x->type, "NAME")) { adv(p); Node *n = newnode(N_NAME); n->str = x->sval; n->line = x->line; return n; }
    if (atop(p, "(")) { adv(p); skipnl(p); Node *e = expression(p); skipnl(p); eatop(p, ")"); return e; }
    if (atop(p, "[")) {
        adv(p); skipnl(p); Node *n = newnode(N_LIST);
        if (!atop(p, "]")) {
            kids_push(n, expression(p)); skipnl(p);
            while (atop(p, ",")) { adv(p); skipnl(p); if (atop(p, "]")) break; kids_push(n, expression(p)); skipnl(p); }
        }
        eatop(p, "]"); return n;
    }
    amk_error(x->line, "unexpected %s", x->sval ? x->sval : "end of file");
    return NULL;
}
static Node *postfix(Parser *p) {
    Node *node = primary(p);
    for (;;) {
        if (atop(p, "(")) {
            Node *c = newnode(N_CALL); c->a = node; c->line = adv(p)->line; skipnl(p);
            if (!atop(p, ")")) {
                kids_push(c, expression(p)); skipnl(p);
                while (atop(p, ",")) { adv(p); skipnl(p); if (atop(p, ")")) break; kids_push(c, expression(p)); skipnl(p); }
            }
            eatop(p, ")"); node = c;
        } else if (atop(p, "[")) {
            Node *ix = newnode(N_INDEX); ix->a = node; ix->line = adv(p)->line; ix->b = expression(p); eatop(p, "]"); node = ix;
        } else break;
    }
    return node;
}
static Node *unary(Parser *p) {
    if (at(p, "not")) { Node *n = newnode(N_UNARY); n->str = "not"; n->line = adv(p)->line; n->a = unary(p); return n; }
    if (atop(p, "-")) { Node *n = newnode(N_UNARY); n->str = "-"; n->line = adv(p)->line; n->a = unary(p); return n; }
    return postfix(p);
}
static Node *binlevel(Parser *p, Node *(*sub)(Parser *), const char **ops, int isKwOr) {
    Node *a = sub(p);
    for (;;) {
        int matched = -1;
        for (int i = 0; ops[i]; i++) {
            if (isKwOr) { if (at(p, ops[i])) { matched = i; break; } }
            else { if (atop(p, ops[i])) { matched = i; break; } }
        }
        if (matched < 0) break;
        Tok *o = adv(p);
        Node *n;
        if (isKwOr) { n = newnode(N_LOGIC); n->str = (char *)ops[matched]; }
        else { n = newnode(N_BIN); n->str = xstrdup(o->sval); n->line = o->line; }
        n->a = a; n->b = sub(p); a = n;
    }
    return a;
}
static Node *factor(Parser *p) { static const char *ops[] = {"*","/","%",NULL}; return binlevel(p, unary, ops, 0); }
static Node *term(Parser *p) { static const char *ops[] = {"+","-",NULL}; return binlevel(p, factor, ops, 0); }
static Node *comparison(Parser *p) { static const char *ops[] = {"<",">","<=",">=",NULL}; return binlevel(p, term, ops, 0); }
static Node *equality(Parser *p) { static const char *ops[] = {"==","!=",NULL}; return binlevel(p, comparison, ops, 0); }
static Node *logicand(Parser *p) { static const char *ops[] = {"and",NULL}; return binlevel(p, equality, ops, 1); }
static Node *logicor(Parser *p) { static const char *ops[] = {"or",NULL}; return binlevel(p, logicand, ops, 1); }
static Node *expression(Parser *p) { return logicor(p); }

static Node *block(Parser *p) {
    Node *n = newnode(N_BLOCK); eatop(p, "{"); skipnl(p);
    while (!atop(p, "}") && !at(p, "EOF")) { kids_push(n, statement(p)); skipnl(p); }
    eatop(p, "}"); return n;
}
static Node *statement(Parser *p) {
    Tok *x = pk(p);
    if (!strcmp(x->type, "tyan")) return funcdef(p);
    if (!strcmp(x->type, "moshi")) return ifstmt(p);
    if (!strcmp(x->type, "while")) return whilestmt(p);
    if (!strcmp(x->type, "for")) return forstmt(p);
    if (!strcmp(x->type, "back")) return returnstmt(p);
    Node *e = expression(p);
    if (atop(p, "=")) {
        Node *n = newnode(N_ASSIGN); n->line = adv(p)->line; n->a = e; n->b = expression(p);
        if (e->kind != N_NAME && e->kind != N_INDEX) amk_error(n->line, "left of '=' must be a variable name");
        return n;
    }
    Node *n = newnode(N_EXPR); n->a = e; return n;
}
static Node *parse(TokList *t) {
    Parser p = { t->a, 0 }; Node *prog = newnode(N_PROG); skipnl(&p);
    while (!at(&p, "EOF")) { kids_push(prog, statement(&p)); skipnl(&p); }
    return prog;
}

/* ---------- environment ---------- */
typedef struct { char *name; Value val; } Entry;
struct Env { Entry *e; int len, cap; Env *parent; };
static Env *new_env(Env *parent) { Env *env = xmalloc(sizeof(Env)); env->e = NULL; env->len = 0; env->cap = 0; env->parent = parent; return env; }
static int env_find(Env *env, const char *name) {
    for (int i = 0; i < env->len; i++) if (strcmp(env->e[i].name, name) == 0) return i;
    return -1;
}
static void env_define(Env *env, const char *name, Value v) {
    int idx = env_find(env, name);
    if (idx >= 0) { env->e[idx].val = v; return; }
    if (env->len == env->cap) { env->cap = env->cap ? env->cap * 2 : 8; env->e = realloc(env->e, env->cap * sizeof(Entry)); }
    env->e[env->len].name = xstrdup(name); env->e[env->len].val = v; env->len++;
}
static Value env_get(Env *env, const char *name, int line) {
    for (Env *e = env; e; e = e->parent) { int i = env_find(e, name); if (i >= 0) return e->e[i].val; }
    amk_error(line, "unknown name '%s'", name); return V_NIL();
}
static void env_assign(Env *env, const char *name, Value v) {
    for (Env *e = env; e; e = e->parent) { int i = env_find(e, name); if (i >= 0) { e->e[i].val = v; return; } }
    env_define(env, name, v);
}

/* ---------- interpreter ---------- */
static int g_returning = 0;
static Value g_retval;

static Value eval(Node *node, Env *env);
static void exec(Node *node, Env *env);

static void exec_block(Node *b, Env *env) {
    for (int i = 0; i < b->nkids; i++) { exec(b->kids[i], env); if (g_returning) return; }
}
static void numck(Value a, Value b, int line, const char *op) {
    if (!(is_num(a) && is_num(b))) amk_error(line, "'%s' needs two numbers, got %s and %s", op, type_name(a), type_name(b));
}
static Value get_index(Value target, Value idx, int line) {
    if (idx.t != T_NUM || idx.as.num != floor(idx.as.num)) amk_error(line, "index must be a whole number");
    int i = (int)idx.as.num;
    if (target.t == T_LIST) { List *l = target.as.list; if (i < 0) i += l->len; if (i < 0 || i >= l->len) amk_error(line, "index out of range"); return l->items[i]; }
    if (target.t == T_STR) { int len = (int)strlen(target.as.str); if (i < 0) i += len; if (i < 0 || i >= len) amk_error(line, "index out of range"); char *r = xmalloc(2); r[0] = target.as.str[i]; r[1] = 0; return V_STR(r); }
    amk_error(line, "only a list or text can be indexed"); return V_NIL();
}
static void set_index(Value target, Value idx, Value val, int line) {
    if (idx.t != T_NUM || idx.as.num != floor(idx.as.num)) amk_error(line, "index must be a whole number");
    int i = (int)idx.as.num;
    if (target.t == T_LIST) { List *l = target.as.list; if (i < 0) i += l->len; if (i < 0 || i >= l->len) amk_error(line, "index out of range"); l->items[i] = val; return; }
    amk_error(line, "only a list can be changed by index");
}
static Value call_value(Value callee, Value *args, int nargs, int line) {
    if (callee.t == T_FUNC) {
        Node *decl = callee.as.func->decl;
        if (nargs != decl->nnames) amk_error(line, "function '%s' wants %d argument(s), got %d", decl->str, decl->nnames, nargs);
        Env *local = new_env(callee.as.func->env);
        for (int i = 0; i < nargs; i++) env_define(local, decl->names[i], args[i]);
        exec_block(decl->b, local);
        if (g_returning) { g_returning = 0; return g_retval; }
        return V_NIL();
    }
    if (callee.t == T_BUILTIN) return callee.as.builtin(args, nargs);
    amk_error(line, "this is not a function, cannot call it with ()"); return V_NIL();
}

static Value binop(Node *node, Env *env) {
    const char *op = node->str; int line = node->line;
    Value a = eval(node->a, env), b = eval(node->b, env);
    if (!strcmp(op, "+")) {
        if (a.t == T_STR || b.t == T_STR) return V_STR(strcat2(to_text(a), to_text(b)));
        if (a.t == T_LIST && b.t == T_LIST) { List *r = new_list(); for (int i = 0; i < a.as.list->len; i++) list_push(r, a.as.list->items[i]); for (int i = 0; i < b.as.list->len; i++) list_push(r, b.as.list->items[i]); return V_LIST(r); }
        numck(a, b, line, "+"); return V_NUM(a.as.num + b.as.num);
    }
    if (!strcmp(op, "-")) { numck(a, b, line, "-"); return V_NUM(a.as.num - b.as.num); }
    if (!strcmp(op, "*")) { numck(a, b, line, "*"); return V_NUM(a.as.num * b.as.num); }
    if (!strcmp(op, "/")) { numck(a, b, line, "/"); if (b.as.num == 0) amk_error(line, "division by zero"); return V_NUM(a.as.num / b.as.num); }
    if (!strcmp(op, "%")) { numck(a, b, line, "%"); if (b.as.num == 0) amk_error(line, "division by zero"); return V_NUM(fmod(a.as.num, b.as.num)); }
    if (!strcmp(op, "==")) return V_BOOL(deep_eq(a, b));
    if (!strcmp(op, "!=")) return V_BOOL(!deep_eq(a, b));
    int ok = (is_num(a) && is_num(b)) || (a.t == T_STR && b.t == T_STR);
    if (!ok) amk_error(line, "cannot compare %s and %s", type_name(a), type_name(b));
    int cmp;
    if (a.t == T_NUM) cmp = (a.as.num < b.as.num) ? -1 : (a.as.num > b.as.num) ? 1 : 0;
    else cmp = strcmp(a.as.str, b.as.str);
    if (!strcmp(op, "<")) return V_BOOL(cmp < 0);
    if (!strcmp(op, ">")) return V_BOOL(cmp > 0);
    if (!strcmp(op, "<=")) return V_BOOL(cmp <= 0);
    return V_BOOL(cmp >= 0);
}

static Value eval(Node *node, Env *env) {
    switch (node->kind) {
        case N_NUM: return V_NUM(node->num);
        case N_STR: return V_STR(node->str);
        case N_BOOL: return V_BOOL(node->bval);
        case N_NIL: return V_NIL();
        case N_LIST: { List *l = new_list(); for (int i = 0; i < node->nkids; i++) list_push(l, eval(node->kids[i], env)); return V_LIST(l); }
        case N_NAME: return env_get(env, node->str, node->line);
        case N_UNARY: {
            Value v = eval(node->a, env);
            if (!strcmp(node->str, "not")) return V_BOOL(!truthy(v));
            if (!is_num(v)) amk_error(node->line, "minus works only on a number");
            return V_NUM(-v.as.num);
        }
        case N_LOGIC: {
            Value left = eval(node->a, env);
            if (!strcmp(node->str, "and")) return truthy(left) ? V_BOOL(truthy(eval(node->b, env))) : V_BOOL(0);
            return truthy(left) ? V_BOOL(1) : V_BOOL(truthy(eval(node->b, env)));
        }
        case N_BIN: return binop(node, env);
        case N_INDEX: { Value tg = eval(node->a, env); Value ix = eval(node->b, env); return get_index(tg, ix, node->line); }
        case N_CALL: {
            Value callee = eval(node->a, env);
            Value *args = node->nkids ? xmalloc(node->nkids * sizeof(Value)) : NULL;
            for (int i = 0; i < node->nkids; i++) args[i] = eval(node->kids[i], env);
            return call_value(callee, args, node->nkids, node->line);
        }
        default: amk_error(node->line, "cannot evaluate node"); return V_NIL();
    }
}

static void exec(Node *node, Env *env) {
    switch (node->kind) {
        case N_EXPR: eval(node->a, env); return;
        case N_FUNC: { Value v; v.t = T_FUNC; v.as.func = xmalloc(sizeof(Func)); v.as.func->decl = node; v.as.func->env = env; env_define(env, node->str, v); return; }
        case N_ASSIGN: {
            Value val = eval(node->b, env);
            if (node->a->kind == N_NAME) env_assign(env, node->a->str, val);
            else { Value tg = eval(node->a->a, env); Value ix = eval(node->a->b, env); set_index(tg, ix, val, node->a->line); }
            return;
        }
        case N_IF: {
            if (truthy(eval(node->a, env))) exec_block(node->b, env);
            else if (node->c) { if (node->c->kind == N_BLOCK) exec_block(node->c, env); else exec(node->c, env); }
            return;
        }
        case N_WHILE: {
            long guard = 0;
            while (truthy(eval(node->a, env))) { exec_block(node->b, env); if (g_returning) return; if (++guard > 100000000L) amk_error(0, "loop ran too long (possible infinite loop)"); }
            return;
        }
        case N_FOR: {
            Value coll = eval(node->a, env);
            if (coll.t == T_LIST) { for (int i = 0; i < coll.as.list->len; i++) { env_assign(env, node->str, coll.as.list->items[i]); exec_block(node->b, env); if (g_returning) return; } }
            else if (coll.t == T_STR) { for (int i = 0; coll.as.str[i]; i++) { char *ch = xmalloc(2); ch[0] = coll.as.str[i]; ch[1] = 0; env_assign(env, node->str, V_STR(ch)); exec_block(node->b, env); if (g_returning) return; } }
            else amk_error(node->line, "'for ... in ...' needs a list or text");
            return;
        }
        case N_RETURN: { g_retval = node->a ? eval(node->a, env) : V_NIL(); g_returning = 1; return; }
        default: amk_error(node->line, "cannot run node"); return;
    }
}

/* ---------- builtins ---------- */
static Value bi_nya(Value *a, int n) {
    for (int i = 0; i < n; i++) { if (i) fputc(' ', stdout); fputs(to_text(a[i]), stdout); }
    fputc('\n', stdout); return V_NIL();
}
static Value bi_len(Value *a, int n) {
    (void)n; if (a[0].t == T_LIST) return V_NUM(a[0].as.list->len); if (a[0].t == T_STR) return V_NUM((double)strlen(a[0].as.str));
    amk_error(0, "len() needs a list or text"); return V_NIL();
}
static Value bi_num(Value *a, int n) {
    (void)n; if (a[0].t == T_NUM) return a[0]; if (a[0].t == T_BOOL) return V_NUM(a[0].as.b ? 1 : 0);
    if (a[0].t == T_STR) { char *end; double d = strtod(a[0].as.str, &end); while (*end == ' ') end++; if (end == a[0].as.str || *end != '\0') amk_error(0, "cannot turn '%s' into a number", a[0].as.str); return V_NUM(d); }
    amk_error(0, "num() does not understand this value"); return V_NIL();
}
static Value bi_str(Value *a, int n) { (void)n; return V_STR(to_text(a[0])); }
static Value bi_ask(Value *a, int n) {
    if (n >= 1) { fputs(to_text(a[0]), stdout); fflush(stdout); }
    char *line = NULL; size_t cap = 0; ssize_t r = getline(&line, &cap, stdin);
    if (r < 0) return V_STR(xstrdup(""));
    if (r > 0 && line[r - 1] == '\n') line[r - 1] = '\0';
    return V_STR(line);
}
static Value bi_range(Value *a, int n) {
    int start, end, step = 1;
    if (n == 1) { start = 0; end = (int)a[0].as.num; }
    else { start = (int)a[0].as.num; end = (int)a[1].as.num; if (n >= 3) step = (int)a[2].as.num; }
    if (step == 0) amk_error(0, "range step cannot be 0");
    List *l = new_list();
    if (step > 0) for (int k = start; k < end; k += step) list_push(l, V_NUM(k));
    else for (int k = start; k > end; k += step) list_push(l, V_NUM(k));
    return V_LIST(l);
}
static Value bi_push(Value *a, int n) { (void)n; if (a[0].t != T_LIST) amk_error(0, "push() needs a list"); list_push(a[0].as.list, a[1]); return V_NIL(); }
static Value bi_random(Value *a, int n) {
    (void)n; int lo = (int)a[0].as.num, hi = (int)a[1].as.num;
    if (hi < lo) { int t = lo; lo = hi; hi = t; }
    return V_NUM(lo + rand() % (hi - lo + 1));
}
static void def_builtin(Env *g, const char *name, BuiltinFn fn) { Value v; v.t = T_BUILTIN; v.as.builtin = fn; env_define(g, name, v); }

/* ---------- main ---------- */
static char *read_file(const char *path) {
    FILE *f = fopen(path, "rb");
    if (!f) { fprintf(stderr, "cannot open file: %s\n", path); exit(1); }
    fseek(f, 0, SEEK_END); long sz = ftell(f); fseek(f, 0, SEEK_SET);
    char *buf = xmalloc(sz + 1); size_t got = fread(buf, 1, sz, f); buf[got] = 0; fclose(f); return buf;
}
int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s file.amkawa\n", argv[0]); return 1; }
    srand((unsigned)time(NULL));
    char *src = read_file(argv[1]);
    if (setjmp(g_err)) { printf("amkawa error: %s\n", g_msg); return 1; }
    TokList toks = lex(src);
    Node *prog = parse(&toks);
    Env *globals = new_env(NULL);
    def_builtin(globals, "nya", bi_nya);
    def_builtin(globals, "len", bi_len);
    def_builtin(globals, "num", bi_num);
    def_builtin(globals, "str", bi_str);
    def_builtin(globals, "ask", bi_ask);
    def_builtin(globals, "range", bi_range);
    def_builtin(globals, "push", bi_push);
    def_builtin(globals, "random", bi_random);
    for (int i = 0; i < prog->nkids; i++) { exec(prog->kids[i], globals); if (g_returning) { printf("amkawa error: 'back' can only be used inside a function (tyan)\n"); return 1; } }
    return 0;
}
