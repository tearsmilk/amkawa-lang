// Aminakawa interpreter — Rust port (core language).
// Build:  rustc -O amkawa.rs
// Run:    ./amkawa yourfile.amkawa
//
// NOTE: This port was written carefully but could NOT be compiled/tested in the
// build sandbox (no Rust toolchain there). Build it with `rustc amkawa.rs` and
// report any errors. The JS/Python/Java/C ports are all tested.

use std::cell::{Cell, RefCell};
use std::collections::HashMap;
use std::io::Write;
use std::rc::Rc;

// ===== control flow (errors and return) =====
enum Ctrl {
    Err(String),
    Ret(Value),
}
type R = Result<Value, Ctrl>;
fn err(line: usize, msg: &str) -> Ctrl {
    Ctrl::Err(if line > 0 { format!("line {}: {}", line, msg) } else { msg.to_string() })
}
fn perr(line: usize, msg: &str) -> String {
    if line > 0 { format!("line {}: {}", line, msg) } else { msg.to_string() }
}

// ===== values =====
#[derive(Clone)]
enum Value {
    Num(f64),
    Str(String),
    Bool(bool),
    Nil,
    List(Rc<RefCell<Vec<Value>>>),
    Func(Rc<FuncVal>),
    Builtin(fn(&[Value]) -> R),
}
struct FuncVal {
    decl: Rc<FuncDecl>,
    env: Rc<RefCell<Env>>,
}
struct FuncDecl {
    name: String,
    params: Vec<String>,
    body: Vec<Node>,
    line: usize,
}

fn truthy(v: &Value) -> bool {
    match v {
        Value::Nil => false,
        Value::Bool(b) => *b,
        Value::Num(n) => *n != 0.0,
        Value::Str(s) => !s.is_empty(),
        Value::List(l) => !l.borrow().is_empty(),
        _ => true,
    }
}
fn type_name(v: &Value) -> &'static str {
    match v {
        Value::Bool(_) => "bool",
        Value::Nil => "mu",
        Value::Num(_) => "number",
        Value::Str(_) => "text",
        Value::List(_) => "list",
        _ => "value",
    }
}
fn fmt_num(d: f64) -> String {
    if d.is_finite() && d == d.trunc() && d.abs() < 9e15 {
        format!("{}", d as i64)
    } else {
        format!("{}", d)
    }
}
fn to_text(v: &Value) -> String {
    match v {
        Value::Bool(b) => (if *b { "hai" } else { "iie" }).to_string(),
        Value::Nil => "mu".to_string(),
        Value::Num(n) => fmt_num(*n),
        Value::Str(s) => s.clone(),
        Value::List(l) => {
            let parts: Vec<String> = l.borrow().iter().map(|x| to_text(x)).collect();
            format!("[{}]", parts.join(", "))
        }
        _ => "<function>".to_string(),
    }
}
fn deep_eq(a: &Value, b: &Value) -> bool {
    match (a, b) {
        (Value::List(la), Value::List(lb)) => {
            let la = la.borrow();
            let lb = lb.borrow();
            if la.len() != lb.len() {
                return false;
            }
            la.iter().zip(lb.iter()).all(|(x, y)| deep_eq(x, y))
        }
        (Value::Num(x), Value::Num(y)) => x == y,
        (Value::Str(x), Value::Str(y)) => x == y,
        (Value::Bool(x), Value::Bool(y)) => x == y,
        (Value::Nil, Value::Nil) => true,
        _ => false,
    }
}

// ===== tokens =====
#[derive(Clone)]
enum Tk {
    Nl,
    Str(String),
    Num(f64),
    Name(String),
    Kw(&'static str),
    Op(String),
    Eof,
}
#[derive(Clone)]
struct Token {
    kind: Tk,
    line: usize,
}
const KEYWORDS: &[&str] = &[
    "tyan", "back", "moshi", "else", "while", "for", "in", "and", "or", "not", "hai", "iie", "mu",
];
fn keyword(w: &str) -> Option<&'static str> {
    KEYWORDS.iter().find(|k| **k == w).copied()
}

fn lex(src: &str) -> Result<Vec<Token>, String> {
    let chars: Vec<char> = src.chars().collect();
    let n = chars.len();
    let mut i = 0usize;
    let mut line = 1usize;
    let mut out: Vec<Token> = Vec::new();
    while i < n {
        let c = chars[i];
        if c == '\n' {
            out.push(Token { kind: Tk::Nl, line });
            line += 1;
            i += 1;
            continue;
        }
        if c == ' ' || c == '\t' || c == '\r' {
            i += 1;
            continue;
        }
        if c == '#' {
            while i < n && chars[i] != '\n' {
                i += 1;
            }
            continue;
        }
        if c == '"' || c == '\'' {
            let q = c;
            i += 1;
            let mut s = String::new();
            while i < n && chars[i] != q {
                if chars[i] == '\\' && i + 1 < n {
                    let nx = chars[i + 1];
                    s.push(match nx {
                        'n' => '\n',
                        't' => '\t',
                        other => other,
                    });
                    i += 2;
                    continue;
                }
                if chars[i] == '\n' {
                    line += 1;
                }
                s.push(chars[i]);
                i += 1;
            }
            if i >= n {
                return Err(perr(line, "string is missing a closing quote"));
            }
            i += 1;
            out.push(Token { kind: Tk::Str(s), line });
            continue;
        }
        if c.is_ascii_digit() || (c == '.' && i + 1 < n && chars[i + 1].is_ascii_digit()) {
            let start = i;
            let mut dot = false;
            while i < n && (chars[i].is_ascii_digit() || chars[i] == '.') {
                if chars[i] == '.' {
                    if dot {
                        break;
                    }
                    dot = true;
                }
                i += 1;
            }
            let text: String = chars[start..i].iter().collect();
            match text.parse::<f64>() {
                Ok(v) => out.push(Token { kind: Tk::Num(v), line }),
                Err(_) => return Err(perr(line, "bad number")),
            }
            continue;
        }
        if c.is_alphabetic() || c == '_' {
            let start = i;
            while i < n && (chars[i].is_alphanumeric() || chars[i] == '_') {
                i += 1;
            }
            let w: String = chars[start..i].iter().collect();
            match keyword(&w) {
                Some(k) => out.push(Token { kind: Tk::Kw(k), line }),
                None => out.push(Token { kind: Tk::Name(w), line }),
            }
            continue;
        }
        if i + 1 < n {
            let two: String = [chars[i], chars[i + 1]].iter().collect();
            if two == "==" || two == "!=" || two == "<=" || two == ">=" {
                out.push(Token { kind: Tk::Op(two), line });
                i += 2;
                continue;
            }
        }
        if "+-*/%()<>{}[],=".contains(c) {
            out.push(Token { kind: Tk::Op(c.to_string()), line });
            i += 1;
            continue;
        }
        return Err(perr(line, &format!("unexpected character '{}'", c)));
    }
    out.push(Token { kind: Tk::Eof, line });
    Ok(out)
}

// ===== AST =====
enum Node {
    Num(f64),
    Str(String),
    Bool(bool),
    Nil,
    List(Vec<Node>),
    Name(String, usize),
    Unary(String, Box<Node>, usize),
    Bin(String, Box<Node>, Box<Node>, usize),
    Logic(String, Box<Node>, Box<Node>),
    Index(Box<Node>, Box<Node>, usize),
    Call(Box<Node>, Vec<Node>, usize),
    Assign(Box<Node>, Box<Node>, usize),
    If(Box<Node>, Vec<Node>, Option<Box<Node>>),
    While(Box<Node>, Vec<Node>),
    For(String, Box<Node>, Vec<Node>, usize),
    Func(Rc<FuncDecl>),
    Return(Option<Box<Node>>, usize),
    Expr(Box<Node>),
    Block(Vec<Node>),
}

// ===== parser =====
struct Parser {
    t: Vec<Token>,
    i: usize,
}
impl Parser {
    fn peek(&self) -> &Token {
        &self.t[self.i]
    }
    fn adv(&mut self) -> Token {
        let tok = self.t[self.i].clone();
        self.i += 1;
        tok
    }
    fn line(&self) -> usize {
        self.t[self.i].line
    }
    fn is_kw(&self, k: &str) -> bool {
        matches!(&self.peek().kind, Tk::Kw(x) if *x == k)
    }
    fn is_eof(&self) -> bool {
        matches!(&self.peek().kind, Tk::Eof)
    }
    fn is_nl(&self) -> bool {
        matches!(&self.peek().kind, Tk::Nl)
    }
    fn is_op(&self, v: &str) -> bool {
        matches!(&self.peek().kind, Tk::Op(o) if o == v)
    }
    fn eat_op(&mut self, v: &str) -> Result<(), String> {
        if self.is_op(v) {
            self.adv();
            Ok(())
        } else {
            Err(perr(self.line(), &format!("expected '{}'", v)))
        }
    }
    fn expect_name(&mut self, what: &str) -> Result<String, String> {
        if let Tk::Name(s) = &self.peek().kind {
            let s = s.clone();
            self.adv();
            Ok(s)
        } else {
            Err(perr(self.line(), &format!("expected {}", what)))
        }
    }
    fn skip_nl(&mut self) {
        while self.is_nl() {
            self.adv();
        }
    }

    fn parse(&mut self) -> Result<Vec<Node>, String> {
        let mut stmts = Vec::new();
        self.skip_nl();
        while !self.is_eof() {
            stmts.push(self.statement()?);
            self.skip_nl();
        }
        Ok(stmts)
    }
    fn block(&mut self) -> Result<Vec<Node>, String> {
        self.eat_op("{")?;
        self.skip_nl();
        let mut stmts = Vec::new();
        while !self.is_op("}") && !self.is_eof() {
            stmts.push(self.statement()?);
            self.skip_nl();
        }
        self.eat_op("}")?;
        Ok(stmts)
    }
    fn statement(&mut self) -> Result<Node, String> {
        if self.is_kw("tyan") {
            return self.funcdef();
        }
        if self.is_kw("moshi") {
            return self.if_stmt();
        }
        if self.is_kw("while") {
            self.adv();
            let cond = self.expression()?;
            let body = self.block()?;
            return Ok(Node::While(Box::new(cond), body));
        }
        if self.is_kw("for") {
            let line = self.adv().line;
            let var = self.expect_name("loop variable")?;
            if !self.is_kw("in") {
                return Err(perr(self.line(), "expected 'in'"));
            }
            self.adv();
            let it = self.expression()?;
            let body = self.block()?;
            return Ok(Node::For(var, Box::new(it), body, line));
        }
        if self.is_kw("back") {
            let line = self.adv().line;
            if self.is_nl() || self.is_op("}") || self.is_eof() {
                return Ok(Node::Return(None, line));
            }
            let e = self.expression()?;
            return Ok(Node::Return(Some(Box::new(e)), line));
        }
        let e = self.expression()?;
        if self.is_op("=") {
            let line = self.adv().line;
            let val = self.expression()?;
            match &e {
                Node::Name(_, _) | Node::Index(_, _, _) => {}
                _ => return Err(perr(line, "left of '=' must be a variable name")),
            }
            return Ok(Node::Assign(Box::new(e), Box::new(val), line));
        }
        Ok(Node::Expr(Box::new(e)))
    }
    fn funcdef(&mut self) -> Result<Node, String> {
        let line = self.adv().line;
        let name = self.expect_name("function name")?;
        self.eat_op("(")?;
        self.skip_nl();
        let mut params = Vec::new();
        if !self.is_op(")") {
            params.push(self.expect_name("parameter name")?);
            self.skip_nl();
            while self.is_op(",") {
                self.adv();
                self.skip_nl();
                params.push(self.expect_name("parameter name")?);
                self.skip_nl();
            }
        }
        self.eat_op(")")?;
        let body = self.block()?;
        Ok(Node::Func(Rc::new(FuncDecl { name, params, body, line })))
    }
    fn if_stmt(&mut self) -> Result<Node, String> {
        self.adv();
        let cond = self.expression()?;
        let then = self.block()?;
        self.skip_nl();
        let mut els: Option<Box<Node>> = None;
        if self.is_kw("else") {
            self.adv();
            self.skip_nl();
            if self.is_kw("moshi") {
                els = Some(Box::new(self.if_stmt()?));
            } else {
                let b = self.block()?;
                els = Some(Box::new(Node::Block(b)));
            }
        }
        Ok(Node::If(Box::new(cond), then, els))
    }
    fn expression(&mut self) -> Result<Node, String> {
        self.logic_or()
    }
    fn logic_or(&mut self) -> Result<Node, String> {
        let mut a = self.logic_and()?;
        while self.is_kw("or") {
            self.adv();
            let b = self.logic_and()?;
            a = Node::Logic("or".to_string(), Box::new(a), Box::new(b));
        }
        Ok(a)
    }
    fn logic_and(&mut self) -> Result<Node, String> {
        let mut a = self.equality()?;
        while self.is_kw("and") {
            self.adv();
            let b = self.equality()?;
            a = Node::Logic("and".to_string(), Box::new(a), Box::new(b));
        }
        Ok(a)
    }
    fn equality(&mut self) -> Result<Node, String> {
        let mut a = self.comparison()?;
        while self.is_op("==") || self.is_op("!=") {
            let t = self.adv();
            let op = if let Tk::Op(o) = t.kind { o } else { unreachable!() };
            let b = self.comparison()?;
            a = Node::Bin(op, Box::new(a), Box::new(b), t.line);
        }
        Ok(a)
    }
    fn comparison(&mut self) -> Result<Node, String> {
        let mut a = self.term()?;
        while self.is_op("<") || self.is_op(">") || self.is_op("<=") || self.is_op(">=") {
            let t = self.adv();
            let op = if let Tk::Op(o) = t.kind { o } else { unreachable!() };
            let b = self.term()?;
            a = Node::Bin(op, Box::new(a), Box::new(b), t.line);
        }
        Ok(a)
    }
    fn term(&mut self) -> Result<Node, String> {
        let mut a = self.factor()?;
        while self.is_op("+") || self.is_op("-") {
            let t = self.adv();
            let op = if let Tk::Op(o) = t.kind { o } else { unreachable!() };
            let b = self.factor()?;
            a = Node::Bin(op, Box::new(a), Box::new(b), t.line);
        }
        Ok(a)
    }
    fn factor(&mut self) -> Result<Node, String> {
        let mut a = self.unary()?;
        while self.is_op("*") || self.is_op("/") || self.is_op("%") {
            let t = self.adv();
            let op = if let Tk::Op(o) = t.kind { o } else { unreachable!() };
            let b = self.unary()?;
            a = Node::Bin(op, Box::new(a), Box::new(b), t.line);
        }
        Ok(a)
    }
    fn unary(&mut self) -> Result<Node, String> {
        if self.is_kw("not") {
            let line = self.adv().line;
            let e = self.unary()?;
            return Ok(Node::Unary("not".to_string(), Box::new(e), line));
        }
        if self.is_op("-") {
            let line = self.adv().line;
            let e = self.unary()?;
            return Ok(Node::Unary("-".to_string(), Box::new(e), line));
        }
        self.postfix()
    }
    fn postfix(&mut self) -> Result<Node, String> {
        let mut node = self.primary()?;
        loop {
            if self.is_op("(") {
                let line = self.adv().line;
                self.skip_nl();
                let mut args = Vec::new();
                if !self.is_op(")") {
                    args.push(self.expression()?);
                    self.skip_nl();
                    while self.is_op(",") {
                        self.adv();
                        self.skip_nl();
                        if self.is_op(")") {
                            break;
                        }
                        args.push(self.expression()?);
                        self.skip_nl();
                    }
                }
                self.eat_op(")")?;
                node = Node::Call(Box::new(node), args, line);
            } else if self.is_op("[") {
                let line = self.adv().line;
                let idx = self.expression()?;
                self.eat_op("]")?;
                node = Node::Index(Box::new(node), Box::new(idx), line);
            } else {
                break;
            }
        }
        Ok(node)
    }
    fn primary(&mut self) -> Result<Node, String> {
        let line = self.line();
        let kind = self.peek().kind.clone();
        match kind {
            Tk::Num(n) => {
                let v = n;
                self.adv();
                Ok(Node::Num(v))
            }
            Tk::Str(s) => {
                let v = s.clone();
                self.adv();
                Ok(Node::Str(v))
            }
            Tk::Kw("hai") => {
                self.adv();
                Ok(Node::Bool(true))
            }
            Tk::Kw("iie") => {
                self.adv();
                Ok(Node::Bool(false))
            }
            Tk::Kw("mu") => {
                self.adv();
                Ok(Node::Nil)
            }
            Tk::Name(nm) => {
                let v = nm.clone();
                self.adv();
                Ok(Node::Name(v, line))
            }
            Tk::Op(o) if o == "(" => {
                self.adv();
                self.skip_nl();
                let e = self.expression()?;
                self.skip_nl();
                self.eat_op(")")?;
                Ok(e)
            }
            Tk::Op(o) if o == "[" => {
                self.adv();
                self.skip_nl();
                let mut items = Vec::new();
                if !self.is_op("]") {
                    items.push(self.expression()?);
                    self.skip_nl();
                    while self.is_op(",") {
                        self.adv();
                        self.skip_nl();
                        if self.is_op("]") {
                            break;
                        }
                        items.push(self.expression()?);
                        self.skip_nl();
                    }
                }
                self.eat_op("]")?;
                Ok(Node::List(items))
            }
            _ => Err(perr(line, "unexpected token")),
        }
    }
}

// ===== environment =====
struct Env {
    vars: HashMap<String, Value>,
    parent: Option<Rc<RefCell<Env>>>,
}
fn env_get(env: &Rc<RefCell<Env>>, name: &str, line: usize) -> R {
    let mut cur = env.clone();
    loop {
        if let Some(v) = cur.borrow().vars.get(name) {
            return Ok(v.clone());
        }
        let parent = cur.borrow().parent.clone();
        match parent {
            Some(p) => cur = p,
            None => return Err(err(line, &format!("unknown name '{}'", name))),
        }
    }
}
fn env_assign(env: &Rc<RefCell<Env>>, name: &str, val: Value) {
    let mut cur = env.clone();
    loop {
        let has = cur.borrow().vars.contains_key(name);
        if has {
            cur.borrow_mut().vars.insert(name.to_string(), val);
            return;
        }
        let parent = cur.borrow().parent.clone();
        match parent {
            Some(p) => cur = p,
            None => {
                cur.borrow_mut().vars.insert(name.to_string(), val);
                return;
            }
        }
    }
}
fn env_define(env: &Rc<RefCell<Env>>, name: &str, val: Value) {
    env.borrow_mut().vars.insert(name.to_string(), val);
}

// ===== interpreter =====
fn exec_block(stmts: &[Node], env: &Rc<RefCell<Env>>) -> Result<(), Ctrl> {
    for s in stmts {
        exec(s, env)?;
    }
    Ok(())
}

fn exec(node: &Node, env: &Rc<RefCell<Env>>) -> R {
    match node {
        Node::Expr(e) => {
            eval(e, env)?;
            Ok(Value::Nil)
        }
        Node::Func(decl) => {
            let f = Value::Func(Rc::new(FuncVal { decl: decl.clone(), env: env.clone() }));
            env_define(env, &decl.name, f);
            Ok(Value::Nil)
        }
        Node::Assign(target, value, line) => {
            let val = eval(value, env)?;
            match &**target {
                Node::Name(nm, _) => env_assign(env, nm, val),
                Node::Index(t, idx, iline) => {
                    let tg = eval(t, env)?;
                    let ix = eval(idx, env)?;
                    set_index(&tg, &ix, val, *iline)?;
                }
                _ => return Err(err(*line, "left of '=' must be a variable name")),
            }
            Ok(Value::Nil)
        }
        Node::If(cond, then, els) => {
            if truthy(&eval(cond, env)?) {
                exec_block(then, env)?;
            } else if let Some(e) = els {
                match &**e {
                    Node::Block(stmts) => exec_block(stmts, env)?,
                    other => {
                        exec(other, env)?;
                    }
                }
            }
            Ok(Value::Nil)
        }
        Node::While(cond, body) => {
            let mut guard: u64 = 0;
            while truthy(&eval(cond, env)?) {
                exec_block(body, env)?;
                guard += 1;
                if guard > 100_000_000 {
                    return Err(err(0, "loop ran too long (possible infinite loop)"));
                }
            }
            Ok(Value::Nil)
        }
        Node::For(var, iterable, body, line) => {
            let coll = eval(iterable, env)?;
            match coll {
                Value::List(l) => {
                    let items = l.borrow().clone();
                    for item in items {
                        env_assign(env, var, item);
                        exec_block(body, env)?;
                    }
                }
                Value::Str(s) => {
                    for ch in s.chars() {
                        env_assign(env, var, Value::Str(ch.to_string()));
                        exec_block(body, env)?;
                    }
                }
                _ => return Err(err(*line, "'for ... in ...' needs a list or text")),
            }
            Ok(Value::Nil)
        }
        Node::Return(val, _) => {
            let v = match val {
                Some(e) => eval(e, env)?,
                None => Value::Nil,
            };
            Err(Ctrl::Ret(v))
        }
        _ => Err(err(0, "cannot run this node")),
    }
}

fn eval(node: &Node, env: &Rc<RefCell<Env>>) -> R {
    match node {
        Node::Num(n) => Ok(Value::Num(*n)),
        Node::Str(s) => Ok(Value::Str(s.clone())),
        Node::Bool(b) => Ok(Value::Bool(*b)),
        Node::Nil => Ok(Value::Nil),
        Node::List(items) => {
            let mut v = Vec::with_capacity(items.len());
            for it in items {
                v.push(eval(it, env)?);
            }
            Ok(Value::List(Rc::new(RefCell::new(v))))
        }
        Node::Name(name, line) => env_get(env, name, *line),
        Node::Unary(op, e, line) => {
            let v = eval(e, env)?;
            if op == "not" {
                Ok(Value::Bool(!truthy(&v)))
            } else {
                match v {
                    Value::Num(n) => Ok(Value::Num(-n)),
                    _ => Err(err(*line, "minus works only on a number")),
                }
            }
        }
        Node::Logic(op, a, b) => {
            let left = eval(a, env)?;
            if op == "and" {
                if truthy(&left) {
                    Ok(Value::Bool(truthy(&eval(b, env)?)))
                } else {
                    Ok(Value::Bool(false))
                }
            } else {
                if truthy(&left) {
                    Ok(Value::Bool(true))
                } else {
                    Ok(Value::Bool(truthy(&eval(b, env)?)))
                }
            }
        }
        Node::Bin(op, a, b, line) => {
            let av = eval(a, env)?;
            let bv = eval(b, env)?;
            binop(op, av, bv, *line)
        }
        Node::Index(t, idx, line) => {
            let tg = eval(t, env)?;
            let ix = eval(idx, env)?;
            get_index(&tg, &ix, *line)
        }
        Node::Call(callee, args, line) => {
            let c = eval(callee, env)?;
            let mut av = Vec::with_capacity(args.len());
            for a in args {
                av.push(eval(a, env)?);
            }
            call_value(c, av, *line)
        }
        _ => Err(err(0, "cannot evaluate this node")),
    }
}

fn binop(op: &str, a: Value, b: Value, line: usize) -> R {
    match op {
        "+" => {
            if matches!(a, Value::Str(_)) || matches!(b, Value::Str(_)) {
                return Ok(Value::Str(format!("{}{}", to_text(&a), to_text(&b))));
            }
            if let (Value::List(la), Value::List(lb)) = (&a, &b) {
                let mut v = la.borrow().clone();
                v.extend(lb.borrow().iter().cloned());
                return Ok(Value::List(Rc::new(RefCell::new(v))));
            }
            let (x, y) = nums(&a, &b, line, "+")?;
            Ok(Value::Num(x + y))
        }
        "-" => {
            let (x, y) = nums(&a, &b, line, "-")?;
            Ok(Value::Num(x - y))
        }
        "*" => {
            let (x, y) = nums(&a, &b, line, "*")?;
            Ok(Value::Num(x * y))
        }
        "/" => {
            let (x, y) = nums(&a, &b, line, "/")?;
            if y == 0.0 {
                return Err(err(line, "division by zero"));
            }
            Ok(Value::Num(x / y))
        }
        "%" => {
            let (x, y) = nums(&a, &b, line, "%")?;
            if y == 0.0 {
                return Err(err(line, "division by zero"));
            }
            Ok(Value::Num(x % y))
        }
        "==" => Ok(Value::Bool(deep_eq(&a, &b))),
        "!=" => Ok(Value::Bool(!deep_eq(&a, &b))),
        _ => {
            let cmp = match (&a, &b) {
                (Value::Num(x), Value::Num(y)) => {
                    if x < y {
                        -1
                    } else if x > y {
                        1
                    } else {
                        0
                    }
                }
                (Value::Str(x), Value::Str(y)) => x.cmp(y) as i32,
                _ => {
                    return Err(err(
                        line,
                        &format!("cannot compare {} and {}", type_name(&a), type_name(&b)),
                    ))
                }
            };
            let res = match op {
                "<" => cmp < 0,
                ">" => cmp > 0,
                "<=" => cmp <= 0,
                _ => cmp >= 0,
            };
            Ok(Value::Bool(res))
        }
    }
}
fn nums(a: &Value, b: &Value, line: usize, op: &str) -> Result<(f64, f64), Ctrl> {
    match (a, b) {
        (Value::Num(x), Value::Num(y)) => Ok((*x, *y)),
        _ => Err(err(
            line,
            &format!("'{}' needs two numbers, got {} and {}", op, type_name(a), type_name(b)),
        )),
    }
}

fn get_index(target: &Value, idx: &Value, line: usize) -> R {
    let i = match idx {
        Value::Num(n) if *n == n.trunc() => *n as i64,
        _ => return Err(err(line, "index must be a whole number")),
    };
    match target {
        Value::List(l) => {
            let l = l.borrow();
            let mut k = i;
            if k < 0 {
                k += l.len() as i64;
            }
            if k < 0 || k as usize >= l.len() {
                return Err(err(line, "index out of range"));
            }
            Ok(l[k as usize].clone())
        }
        Value::Str(s) => {
            let chars: Vec<char> = s.chars().collect();
            let mut k = i;
            if k < 0 {
                k += chars.len() as i64;
            }
            if k < 0 || k as usize >= chars.len() {
                return Err(err(line, "index out of range"));
            }
            Ok(Value::Str(chars[k as usize].to_string()))
        }
        _ => Err(err(line, "only a list or text can be indexed")),
    }
}
fn set_index(target: &Value, idx: &Value, val: Value, line: usize) -> Result<(), Ctrl> {
    let i = match idx {
        Value::Num(n) if *n == n.trunc() => *n as i64,
        _ => return Err(err(line, "index must be a whole number")),
    };
    match target {
        Value::List(l) => {
            let mut l = l.borrow_mut();
            let mut k = i;
            if k < 0 {
                k += l.len() as i64;
            }
            if k < 0 || k as usize >= l.len() {
                return Err(err(line, "index out of range"));
            }
            l[k as usize] = val;
            Ok(())
        }
        _ => Err(err(line, "only a list can be changed by index")),
    }
}

fn call_value(callee: Value, args: Vec<Value>, line: usize) -> R {
    match callee {
        Value::Func(f) => {
            if args.len() != f.decl.params.len() {
                return Err(err(
                    line,
                    &format!(
                        "function '{}' wants {} argument(s), got {}",
                        f.decl.name,
                        f.decl.params.len(),
                        args.len()
                    ),
                ));
            }
            let local = Rc::new(RefCell::new(Env {
                vars: HashMap::new(),
                parent: Some(f.env.clone()),
            }));
            for (p, a) in f.decl.params.iter().zip(args.into_iter()) {
                local.borrow_mut().vars.insert(p.clone(), a);
            }
            match exec_block(&f.decl.body, &local) {
                Ok(()) => Ok(Value::Nil),
                Err(Ctrl::Ret(v)) => Ok(v),
                Err(e) => Err(e),
            }
        }
        Value::Builtin(b) => b(&args),
        _ => Err(err(line, "this is not a function, cannot call it with ()")),
    }
}

// ===== builtins =====
fn bi_nya(args: &[Value]) -> R {
    let parts: Vec<String> = args.iter().map(|v| to_text(v)).collect();
    println!("{}", parts.join(" "));
    Ok(Value::Nil)
}
fn bi_len(args: &[Value]) -> R {
    match &args[0] {
        Value::List(l) => Ok(Value::Num(l.borrow().len() as f64)),
        Value::Str(s) => Ok(Value::Num(s.chars().count() as f64)),
        _ => Err(Ctrl::Err("len() needs a list or text".to_string())),
    }
}
fn bi_num(args: &[Value]) -> R {
    match &args[0] {
        Value::Num(n) => Ok(Value::Num(*n)),
        Value::Bool(b) => Ok(Value::Num(if *b { 1.0 } else { 0.0 })),
        Value::Str(s) => s
            .trim()
            .parse::<f64>()
            .map(Value::Num)
            .map_err(|_| Ctrl::Err(format!("cannot turn '{}' into a number", s))),
        _ => Err(Ctrl::Err("num() does not understand this value".to_string())),
    }
}
fn bi_str(args: &[Value]) -> R {
    Ok(Value::Str(to_text(&args[0])))
}
fn bi_ask(args: &[Value]) -> R {
    if let Some(p) = args.get(0) {
        print!("{}", to_text(p));
        let _ = std::io::stdout().flush();
    }
    let mut line = String::new();
    let _ = std::io::stdin().read_line(&mut line);
    if line.ends_with('\n') {
        line.pop();
        if line.ends_with('\r') {
            line.pop();
        }
    }
    Ok(Value::Str(line))
}
fn as_i64(v: &Value) -> i64 {
    match v {
        Value::Num(n) => *n as i64,
        _ => 0,
    }
}
fn bi_range(args: &[Value]) -> R {
    let (start, end, step) = if args.len() == 1 {
        (0i64, as_i64(&args[0]), 1i64)
    } else {
        let s = as_i64(&args[0]);
        let e = as_i64(&args[1]);
        let st = if args.len() >= 3 { as_i64(&args[2]) } else { 1 };
        (s, e, st)
    };
    if step == 0 {
        return Err(Ctrl::Err("range step cannot be 0".to_string()));
    }
    let mut v = Vec::new();
    let mut k = start;
    if step > 0 {
        while k < end {
            v.push(Value::Num(k as f64));
            k += step;
        }
    } else {
        while k > end {
            v.push(Value::Num(k as f64));
            k += step;
        }
    }
    Ok(Value::List(Rc::new(RefCell::new(v))))
}
fn bi_push(args: &[Value]) -> R {
    match &args[0] {
        Value::List(l) => {
            l.borrow_mut().push(args[1].clone());
            Ok(Value::Nil)
        }
        _ => Err(Ctrl::Err("push() needs a list".to_string())),
    }
}
thread_local!(static SEED: Cell<u64> = Cell::new(0x2545F4914F6CDD1D));
fn rng_next() -> u64 {
    SEED.with(|s| {
        let mut x = s.get();
        x ^= x << 13;
        x ^= x >> 7;
        x ^= x << 17;
        s.set(x);
        x
    })
}
fn bi_random(args: &[Value]) -> R {
    let mut lo = as_i64(&args[0]);
    let mut hi = as_i64(&args[1]);
    if hi < lo {
        std::mem::swap(&mut lo, &mut hi);
    }
    let span = (hi - lo + 1) as u64;
    Ok(Value::Num((lo + (rng_next() % span) as i64) as f64))
}

// ===== main =====
fn main() {
    let argv: Vec<String> = std::env::args().collect();
    if argv.len() < 2 {
        eprintln!("usage: {} file.amkawa", argv[0]);
        std::process::exit(1);
    }
    // seed the RNG
    if let Ok(d) = std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH) {
        SEED.with(|s| s.set((d.as_nanos() as u64) | 1));
    }
    let src = match std::fs::read_to_string(&argv[1]) {
        Ok(s) => s,
        Err(_) => {
            eprintln!("cannot open file: {}", argv[1]);
            std::process::exit(1);
        }
    };
    let toks = match lex(&src) {
        Ok(t) => t,
        Err(e) => {
            println!("amkawa error: {}", e);
            std::process::exit(1);
        }
    };
    let mut parser = Parser { t: toks, i: 0 };
    let prog = match parser.parse() {
        Ok(p) => p,
        Err(e) => {
            println!("amkawa error: {}", e);
            std::process::exit(1);
        }
    };
    let globals = Rc::new(RefCell::new(Env {
        vars: HashMap::new(),
        parent: None,
    }));
    env_define(&globals, "nya", Value::Builtin(bi_nya));
    env_define(&globals, "len", Value::Builtin(bi_len));
    env_define(&globals, "num", Value::Builtin(bi_num));
    env_define(&globals, "str", Value::Builtin(bi_str));
    env_define(&globals, "ask", Value::Builtin(bi_ask));
    env_define(&globals, "range", Value::Builtin(bi_range));
    env_define(&globals, "push", Value::Builtin(bi_push));
    env_define(&globals, "random", Value::Builtin(bi_random));

    for stmt in &prog {
        match exec(stmt, &globals) {
            Ok(_) => {}
            Err(Ctrl::Err(e)) => {
                println!("amkawa error: {}", e);
                std::process::exit(1);
            }
            Err(Ctrl::Ret(_)) => {
                println!("amkawa error: 'back' can only be used inside a function (tyan)");
                std::process::exit(1);
            }
        }
    }
}
