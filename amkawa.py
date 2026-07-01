#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Aminakawa (.amkawa) — a tiny anime-flavored programming language.
One file: lexer -> parser -> tree-walking interpreter.

Run:  python amkawa.py yourfile.amkawa
"""
import sys

# ============================================================
#  ERRORS
# ============================================================
class AmkError(Exception):
    def __init__(self, msg, line=None):
        self.msg = msg
        self.line = line
    def __str__(self):
        if self.line:
            return "line %d: %s" % (self.line, self.msg)
        return self.msg


# ============================================================
#  LEXER
# ============================================================
KEYWORDS = {
    "tyan",   # def
    "back",   # return
    "moshi",  # if
    "else",   # else
    "while",  # while
    "for",    # for
    "in",     # in
    "and", "or", "not",
    "hai",    # true
    "iie",    # false
    "mu",     # null / none
}

class Tok:
    __slots__ = ("type", "value", "line")
    def __init__(self, t, v, l):
        self.type = t; self.value = v; self.line = l
    def __repr__(self):
        return "Tok(%s, %r)" % (self.type, self.value)

def lex(src):
    toks = []
    i = 0; n = len(src); line = 1
    while i < n:
        c = src[i]
        if c == "\n":
            toks.append(Tok("NL", "\n", line)); line += 1; i += 1; continue
        if c in " \t\r":
            i += 1; continue
        if c == "#":
            while i < n and src[i] != "\n":
                i += 1
            continue
        # strings
        if c == '"' or c == "'":
            quote = c; i += 1; buf = []
            while i < n and src[i] != quote:
                ch = src[i]
                if ch == "\\" and i + 1 < n:
                    nxt = src[i + 1]
                    buf.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"', "'": "'"}.get(nxt, nxt))
                    i += 2; continue
                if ch == "\n":
                    line += 1
                buf.append(ch); i += 1
            if i >= n:
                raise AmkError("string is missing a closing quote", line)
            i += 1
            toks.append(Tok("STR", "".join(buf), line)); continue
        # numbers
        if c.isdigit() or (c == "." and i + 1 < n and src[i + 1].isdigit()):
            start = i; dot = False
            while i < n and (src[i].isdigit() or src[i] == "."):
                if src[i] == ".":
                    if dot:
                        break
                    dot = True
                i += 1
            text = src[start:i]
            toks.append(Tok("NUM", float(text) if dot else int(text), line)); continue
        # names / keywords
        if c.isalpha() or c == "_":
            start = i
            while i < n and (src[i].isalnum() or src[i] == "_"):
                i += 1
            word = src[start:i]
            toks.append(Tok(word if word in KEYWORDS else "NAME", word, line)); continue
        # operators
        two = src[i:i + 2]
        if two in ("==", "!=", "<=", ">="):
            toks.append(Tok("OP", two, line)); i += 2; continue
        if c in "+-*/%()<>{}[],=":
            toks.append(Tok("OP", c, line)); i += 1; continue
        raise AmkError("unexpected character %r" % c, line)
    toks.append(Tok("EOF", None, line))
    return toks


# ============================================================
#  AST
# ============================================================
class Num:      __slots__=("v",);            
class Str:      __slots__=("v",)
class Bool:     __slots__=("v",)
class Null:     __slots__=()
class ListLit:  __slots__=("items",)
class Name:     __slots__=("name","line")
class Unary:    __slots__=("op","node","line")
class Bin:      __slots__=("op","a","b","line")
class Logic:    __slots__=("op","a","b")
class Index:    __slots__=("target","index","line")
class Call:     __slots__=("callee","args","line")
class Assign:   __slots__=("target","value","line")
class IfS:      __slots__=("cond","then","els")
class WhileS:   __slots__=("cond","body")
class ForS:     __slots__=("var","iterable","body","line")
class FuncS:    __slots__=("name","params","body","line")
class ReturnS:  __slots__=("value","line")
class ExprS:    __slots__=("expr",)
class Block:    __slots__=("stmts",)
class Program:  __slots__=("stmts",)

def _mk(cls, **kw):
    o = cls.__new__(cls)
    for k, v in kw.items():
        setattr(o, k, v)
    return o


# ============================================================
#  PARSER  (recursive descent)
# ============================================================
class Parser:
    def __init__(self, toks):
        self.toks = toks; self.i = 0
    def peek(self):
        return self.toks[self.i]
    def advance(self):
        t = self.toks[self.i]; self.i += 1; return t
    def at(self, *types):
        return self.peek().type in types
    def at_op(self, v):
        t = self.peek(); return t.type == "OP" and t.value == v
    def eat_op(self, v, what=None):
        if not self.at_op(v):
            raise AmkError("expected %s" % (what or ("'%s'" % v)), self.peek().line)
        return self.advance()
    def expect(self, type_, what=None):
        if self.peek().type != type_:
            raise AmkError("expected %s" % (what or type_), self.peek().line)
        return self.advance()
    def skip_nl(self):
        while self.at("NL"):
            self.advance()

    def parse(self):
        stmts = []; self.skip_nl()
        while not self.at("EOF"):
            stmts.append(self.statement()); self.skip_nl()
        return _mk(Program, stmts=stmts)

    def statement(self):
        t = self.peek()
        if t.type == "tyan":  return self.funcdef()
        if t.type == "moshi": return self.if_stmt()
        if t.type == "while": return self.while_stmt()
        if t.type == "for":   return self.for_stmt()
        if t.type == "back":  return self.return_stmt()
        expr = self.expression()
        if self.at_op("="):
            line = self.advance().line
            value = self.expression()
            if not isinstance(expr, (Name, Index)):
                raise AmkError("left of '=' must be a variable name", line)
            return _mk(Assign, target=expr, value=value, line=line)
        return _mk(ExprS, expr=expr)

    def block(self):
        self.eat_op("{", "'{'"); stmts = []; self.skip_nl()
        while not self.at_op("}") and not self.at("EOF"):
            stmts.append(self.statement()); self.skip_nl()
        self.eat_op("}", "'}'")
        return _mk(Block, stmts=stmts)

    def funcdef(self):
        line = self.advance().line
        name = self.expect("NAME", "function name").value
        self.eat_op("(", "'('"); params = []
        if not self.at_op(")"):
            params.append(self.expect("NAME", "parameter name").value)
            while self.at_op(","):
                self.advance(); params.append(self.expect("NAME", "parameter name").value)
        self.eat_op(")", "')'")
        return _mk(FuncS, name=name, params=params, body=self.block(), line=line)

    def if_stmt(self):
        self.advance()
        cond = self.expression(); then = self.block(); els = None
        self.skip_nl()
        if self.at("else"):
            self.advance(); self.skip_nl()
            els = self.if_stmt() if self.at("moshi") else self.block()
        return _mk(IfS, cond=cond, then=then, els=els)

    def while_stmt(self):
        self.advance()
        return _mk(WhileS, cond=self.expression(), body=self.block())

    def for_stmt(self):
        line = self.advance().line
        var = self.expect("NAME", "loop variable").value
        self.expect("in", "'in'")
        it = self.expression()
        return _mk(ForS, var=var, iterable=it, body=self.block(), line=line)

    def return_stmt(self):
        line = self.advance().line
        if self.at("NL") or self.at_op("}") or self.at("EOF"):
            return _mk(ReturnS, value=None, line=line)
        return _mk(ReturnS, value=self.expression(), line=line)

    # ---- expressions ----
    def expression(self):
        return self.logic_or()
    def logic_or(self):
        a = self.logic_and()
        while self.at("or"):
            self.advance(); a = _mk(Logic, op="or", a=a, b=self.logic_and())
        return a
    def logic_and(self):
        a = self.equality()
        while self.at("and"):
            self.advance(); a = _mk(Logic, op="and", a=a, b=self.equality())
        return a
    def equality(self):
        a = self.comparison()
        while self.at_op("==") or self.at_op("!="):
            t = self.advance(); a = _mk(Bin, op=t.value, a=a, b=self.comparison(), line=t.line)
        return a
    def comparison(self):
        a = self.term()
        while self.at_op("<") or self.at_op(">") or self.at_op("<=") or self.at_op(">="):
            t = self.advance(); a = _mk(Bin, op=t.value, a=a, b=self.term(), line=t.line)
        return a
    def term(self):
        a = self.factor()
        while self.at_op("+") or self.at_op("-"):
            t = self.advance(); a = _mk(Bin, op=t.value, a=a, b=self.factor(), line=t.line)
        return a
    def factor(self):
        a = self.unary()
        while self.at_op("*") or self.at_op("/") or self.at_op("%"):
            t = self.advance(); a = _mk(Bin, op=t.value, a=a, b=self.unary(), line=t.line)
        return a
    def unary(self):
        if self.at("not"):
            t = self.advance(); return _mk(Unary, op="not", node=self.unary(), line=t.line)
        if self.at_op("-"):
            t = self.advance(); return _mk(Unary, op="-", node=self.unary(), line=t.line)
        return self.postfix()
    def postfix(self):
        node = self.primary()
        while True:
            if self.at_op("("):
                t = self.advance(); args = []
                if not self.at_op(")"):
                    args.append(self.expression())
                    while self.at_op(","):
                        self.advance(); args.append(self.expression())
                self.eat_op(")", "')'")
                node = _mk(Call, callee=node, args=args, line=t.line)
            elif self.at_op("["):
                t = self.advance(); idx = self.expression(); self.eat_op("]", "']'")
                node = _mk(Index, target=node, index=idx, line=t.line)
            else:
                break
        return node
    def primary(self):
        t = self.peek()
        if t.type == "NUM": self.advance(); return _mk(Num, v=t.value)
        if t.type == "STR": self.advance(); return _mk(Str, v=t.value)
        if t.type == "hai": self.advance(); return _mk(Bool, v=True)
        if t.type == "iie": self.advance(); return _mk(Bool, v=False)
        if t.type == "mu":  self.advance(); return _mk(Null)
        if t.type == "NAME": self.advance(); return _mk(Name, name=t.value, line=t.line)
        if self.at_op("("):
            self.advance(); e = self.expression(); self.eat_op(")", "')'"); return e
        if self.at_op("["):
            self.advance(); items = []
            if not self.at_op("]"):
                items.append(self.expression())
                while self.at_op(","):
                    self.advance(); items.append(self.expression())
            self.eat_op("]", "']'")
            return _mk(ListLit, items=items)
        raise AmkError("unexpected %s" % (t.value if t.value is not None else "end of file"), t.line)


# ============================================================
#  VALUES / HELPERS
# ============================================================
def is_num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)

def truthy(v):
    if v is None or v is False: return False
    if v is True: return True
    if isinstance(v, (int, float)): return v != 0
    if isinstance(v, str): return len(v) > 0
    if isinstance(v, list): return len(v) > 0
    return True

def to_text(v):
    if v is True: return "hai"
    if v is False: return "iie"
    if v is None: return "mu"
    if isinstance(v, float):
        return str(int(v)) if v.is_integer() else repr(v)
    if isinstance(v, list):
        return "[" + ", ".join(to_text(x) for x in v) + "]"
    return str(v)

def typename(v):
    if v is True or v is False: return "bool"
    if v is None: return "mu"
    if is_num(v): return "number"
    if isinstance(v, str): return "text"
    if isinstance(v, list): return "list"
    return "value"

def equals(a, b):
    return a == b

def _numck(a, b, line, op):
    if not (is_num(a) and is_num(b)):
        raise AmkError("'%s' needs two numbers, got %s and %s" % (op, typename(a), typename(b)), line)


# ============================================================
#  INTERPRETER
# ============================================================
class Function:
    __slots__ = ("decl", "env")
    def __init__(self, decl, env):
        self.decl = decl; self.env = env

class ReturnSignal(Exception):
    def __init__(self, value):
        self.value = value

class Env:
    __slots__ = ("vars", "parent")
    def __init__(self, parent=None):
        self.vars = {}; self.parent = parent
    def get(self, name, line=None):
        e = self
        while e is not None:
            if name in e.vars:
                return e.vars[name]
            e = e.parent
        raise AmkError("unknown name '%s'" % name, line)
    def assign(self, name, value):
        e = self
        while e is not None:
            if name in e.vars:
                e.vars[name] = value; return
            e = e.parent
        self.vars[name] = value
    def define(self, name, value):
        self.vars[name] = value


class Interp:
    def __init__(self):
        self.globals = Env()
        self._install_builtins()

    def run(self, program):
        for s in program.stmts:
            try:
                self.exec(s, self.globals)
            except ReturnSignal:
                raise AmkError("'back' can only be used inside a function (tyan)")

    # ---- statements ----
    def exec(self, node, env):
        k = node.__class__.__name__
        if k == "ExprS":
            self.eval(node.expr, env); return
        if k == "FuncS":
            env.define(node.name, Function(node, env)); return
        if k == "Assign":
            val = self.eval(node.value, env)
            if isinstance(node.target, Name):
                env.assign(node.target.name, val)
            else:
                target = self.eval(node.target.target, env)
                idx = self.eval(node.target.index, env)
                self._setindex(target, idx, val, node.line)
            return
        if k == "IfS":
            if truthy(self.eval(node.cond, env)):
                self.exec_block(node.then, env)
            elif node.els is not None:
                if isinstance(node.els, Block):
                    self.exec_block(node.els, env)
                else:
                    self.exec(node.els, env)
            return
        if k == "WhileS":
            guard = 0
            while truthy(self.eval(node.cond, env)):
                self.exec_block(node.body, env)
                guard += 1
                if guard > 10_000_000:
                    raise AmkError("loop ran too long (possible infinite loop)")
            return
        if k == "ForS":
            coll = self.eval(node.iterable, env)
            if not isinstance(coll, (list, str)):
                raise AmkError("'for ... in ...' needs a list or text", node.line)
            for item in coll:
                env.assign(node.var, item)
                self.exec_block(node.body, env)
            return
        if k == "ReturnS":
            val = self.eval(node.value, env) if node.value is not None else None
            raise ReturnSignal(val)
        raise AmkError("cannot run node %s" % k)

    def exec_block(self, block, env):
        for s in block.stmts:
            self.exec(s, env)

    # ---- expressions ----
    def eval(self, node, env):
        k = node.__class__.__name__
        if k == "Num":  return node.v
        if k == "Str":  return node.v
        if k == "Bool": return node.v
        if k == "Null": return None
        if k == "ListLit": return [self.eval(e, env) for e in node.items]
        if k == "Name": return env.get(node.name, node.line)
        if k == "Unary":
            v = self.eval(node.node, env)
            if node.op == "not":
                return not truthy(v)
            if not is_num(v):
                raise AmkError("minus works only on a number", node.line)
            return -v
        if k == "Logic":
            left = self.eval(node.a, env)
            if node.op == "and":
                return truthy(self.eval(node.b, env)) if truthy(left) else False
            else:
                return True if truthy(left) else truthy(self.eval(node.b, env))
        if k == "Bin":
            return self._binop(node, env)
        if k == "Index":
            target = self.eval(node.target, env); idx = self.eval(node.index, env)
            return self._getindex(target, idx, node.line)
        if k == "Call":
            callee = self.eval(node.callee, env)
            args = [self.eval(a, env) for a in node.args]
            return self.call(callee, args, node.line)
        raise AmkError("cannot evaluate %s" % k, getattr(node, "line", None))

    def _binop(self, node, env):
        op = node.op; line = node.line
        a = self.eval(node.a, env); b = self.eval(node.b, env)
        if op == "+":
            if isinstance(a, str) or isinstance(b, str):
                return to_text(a) + to_text(b)
            if isinstance(a, list) and isinstance(b, list):
                return a + b
            _numck(a, b, line, "+"); return a + b
        if op == "-": _numck(a, b, line, "-"); return a - b
        if op == "*":
            if isinstance(a, str) and isinstance(b, int) and not isinstance(b, bool): return a * b
            if isinstance(b, str) and isinstance(a, int) and not isinstance(a, bool): return b * a
            _numck(a, b, line, "*"); return a * b
        if op == "/":
            _numck(a, b, line, "/")
            if b == 0: raise AmkError("division by zero", line)
            if isinstance(a, int) and isinstance(b, int) and a % b == 0: return a // b
            return a / b
        if op == "%":
            _numck(a, b, line, "%")
            if b == 0: raise AmkError("division by zero", line)
            return a % b
        if op == "==": return equals(a, b)
        if op == "!=": return not equals(a, b)
        # < > <= >=
        ok = (is_num(a) and is_num(b)) or (isinstance(a, str) and isinstance(b, str))
        if not ok:
            raise AmkError("cannot compare %s and %s" % (typename(a), typename(b)), line)
        if op == "<":  return a < b
        if op == ">":  return a > b
        if op == "<=": return a <= b
        return a >= b

    def call(self, callee, args, line):
        if isinstance(callee, Function):
            decl = callee.decl
            if len(args) != len(decl.params):
                raise AmkError("function '%s' wants %d argument(s), got %d"
                               % (decl.name, len(decl.params), len(args)), line)
            local = Env(callee.env)
            for p, a in zip(decl.params, args):
                local.define(p, a)
            try:
                self.exec_block(decl.body, local)
            except ReturnSignal as r:
                return r.value
            return None
        if callable(callee):
            try:
                return callee(*args)
            except AmkError:
                raise
            except TypeError as e:
                raise AmkError("built-in call error: %s" % e, line)
        raise AmkError("this is not a function, cannot call it with ()", line)

    def _getindex(self, target, idx, line):
        if isinstance(target, (list, str)):
            if not isinstance(idx, int) or isinstance(idx, bool):
                raise AmkError("index must be a whole number", line)
            try:
                return target[idx]
            except IndexError:
                raise AmkError("index %d is out of range" % idx, line)
        raise AmkError("only a list or text can be indexed", line)

    def _setindex(self, target, idx, val, line):
        if isinstance(target, list):
            if not isinstance(idx, int) or isinstance(idx, bool):
                raise AmkError("index must be a whole number", line)
            try:
                target[idx] = val
            except IndexError:
                raise AmkError("index %d is out of range" % idx, line)
            return
        raise AmkError("only a list can be changed by index", line)

    # ---- built-ins ----
    def _install_builtins(self):
        interp = self
        g = self.globals

        def _nya(*a):
            print(" ".join(to_text(x) for x in a)); return None
        def _len(x):
            if isinstance(x, (list, str)): return len(x)
            raise AmkError("len() needs a list or text")
        def _num(x):
            if is_num(x): return x
            if isinstance(x, bool): return 1 if x else 0
            if isinstance(x, str):
                s = x.strip()
                try:
                    return float(s) if "." in s else int(s)
                except ValueError:
                    raise AmkError("cannot turn %r into a number" % x)
            raise AmkError("num() does not understand this value")
        def _str(x):
            return to_text(x)
        def _ask(prompt=""):
            return input(to_text(prompt))
        def _range(a, b=None, step=1):
            a = int(a); step = int(step)
            if b is None:
                return list(range(a))
            return list(range(a, int(b), step))
        def _push(lst, v):
            if not isinstance(lst, list):
                raise AmkError("push() needs a list")
            lst.append(v); return None

        g.define("nya", _nya)     # print
        g.define("len", _len)
        g.define("num", _num)
        g.define("str", _str)
        g.define("ask", _ask)     # input
        g.define("range", _range)
        g.define("push", _push)   # append to list

        # ---- Discord (own tiny library, no discord.py) ----
        def _bot(token):
            import amk_discord
            amk_discord.set_token(to_text(token)); return None
        def _on_message(fn):
            import amk_discord
            def bridge(text, channel, author):
                try:
                    interp.call(fn, [text, channel, author], None)
                except AmkError as e:
                    print("[bot] " + str(e))
            amk_discord.set_handler(bridge); return None
        def _say(channel, text):
            import amk_discord
            amk_discord.send_message(to_text(channel), to_text(text)); return None
        def _run():
            import amk_discord
            amk_discord.run()  # blocks

        g.define("bot", _bot)
        g.define("on_message", _on_message)
        g.define("say", _say)
        g.define("run", _run)


# ============================================================
#  CLI
# ============================================================
def run_source(src):
    toks = lex(src)
    prog = Parser(toks).parse()
    Interp().run(prog)

def main():
    if len(sys.argv) < 2:
        print("usage: python amkawa.py file.amkawa")
        sys.exit(1)
    path = sys.argv[1]
    try:
        with open(path, encoding="utf-8") as f:
            src = f.read()
    except OSError as e:
        print("cannot open file: %s" % e); sys.exit(1)
    try:
        run_source(src)
    except AmkError as e:
        print("amkawa error: %s" % e); sys.exit(1)

if __name__ == "__main__":
    main()
