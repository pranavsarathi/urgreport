"""
Robust tokenizer for Verilog and SystemVerilog HDL.
Preserves line numbers, columns, and categorizes tokens accurately.
"""

import re
from typing import List, Optional, NamedTuple


class Token(NamedTuple):
    type: str  # 'KEYWORD', 'IDENTIFIER', 'NUMBER', 'STRING', 'OPERATOR', 'DIRECTIVE', 'COMMENT', 'EOF'
    value: str
    line: int
    col: int

    def __repr__(self):
        return f"Token({self.type}, {self.value!r}, L{self.line}:{self.col})"


KEYWORDS = {
    "module", "endmodule", "input", "output", "inout",
    "wire", "reg", "logic", "bit", "int", "integer", "byte", "shortint", "longint",
    "parameter", "localparam", "const", "var", "automatic", "static", "string", "real",
    "assign", "always", "always_ff", "always_comb", "always_latch",
    "initial", "begin", "end", "if", "else", "case", "casex", "casez",
    "unique", "priority", "inside",
    "endcase", "default", "posedge", "negedge", "or", "and",
    "for", "while", "repeat", "forever", "foreach", "task", "endtask",
    "function", "endfunction", "return", "break", "continue",
    "assert", "generate", "endgenerate",
    "typedef", "enum", "struct", "union", "package", "endpackage",
    "interface", "endinterface", "import", "export"
}

# Multi-character operators and symbols sorted by length descending
MULTI_OPS = [
    "===", "!==", "<<<", ">>>", "**",
    "==", "!=", "<=", ">=", "&&", "||",
    "<<", ">>", "~&", "~|", "~^", "^~",
    "+:", "-:", "->", "::"
]

SINGLE_OPS = set("+-*/%&|^~!<>?:=@#;,().[]{}")


class VerilogLexer:
    def __init__(self, text: str):
        self.text = text
        self.pos = 0
        self.length = len(text)
        self.line = 1
        self.col = 1
        self.tokens: List[Token] = []

    def tokenize(self, include_comments: bool = False) -> List[Token]:
        self.tokens = []
        self.pos = 0
        self.line = 1
        self.col = 1

        while self.pos < self.length:
            ch = self.text[self.pos]

            # Whitespace
            if ch == '\n':
                self.pos += 1
                self.line += 1
                self.col = 1
                continue
            if ch.isspace():
                self.pos += 1
                self.col += 1
                continue

            # Comments
            if ch == '/' and self.pos + 1 < self.length:
                next_ch = self.text[self.pos + 1]
                if next_ch == '/':
                    # Single-line comment
                    start_line = self.line
                    start_col = self.col
                    start_pos = self.pos
                    while self.pos < self.length and self.text[self.pos] != '\n':
                        self.pos += 1
                    comment_val = self.text[start_pos:self.pos]
                    if include_comments:
                        self.tokens.append(Token("COMMENT", comment_val, start_line, start_col))
                    continue
                elif next_ch == '*':
                    # Multi-line comment
                    start_line = self.line
                    start_col = self.col
                    start_pos = self.pos
                    self.pos += 2
                    self.col += 2
                    while self.pos + 1 < self.length and not (self.text[self.pos] == '*' and self.text[self.pos + 1] == '/'):
                        if self.text[self.pos] == '\n':
                            self.line += 1
                            self.col = 1
                        else:
                            self.col += 1
                        self.pos += 1
                    if self.pos + 1 < self.length:
                        self.pos += 2
                        self.col += 2
                    else:
                        self.pos = self.length
                    comment_val = self.text[start_pos:self.pos]
                    if include_comments:
                        self.tokens.append(Token("COMMENT", comment_val, start_line, start_col))
                    continue

            # Compiler directive (e.g. `timescale, `define)
            if ch == '`':
                start_line = self.line
                start_col = self.col
                self.pos += 1
                self.col += 1
                ident_start = self.pos
                while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] == '_'):
                    self.pos += 1
                    self.col += 1
                directive_name = self.text[ident_start:self.pos]
                # Consume rest of directive line if timescale/include/define
                rest_start = self.pos
                while self.pos < self.length and self.text[self.pos] != '\n':
                    self.pos += 1
                directive_full = "`" + directive_name + self.text[rest_start:self.pos]
                self.tokens.append(Token("DIRECTIVE", directive_full.strip(), start_line, start_col))
                continue

            # String literal
            if ch == '"':
                start_line = self.line
                start_col = self.col
                self.pos += 1
                self.col += 1
                val = []
                while self.pos < self.length and self.text[self.pos] != '"':
                    if self.text[self.pos] == '\\' and self.pos + 1 < self.length:
                        val.append(self.text[self.pos:self.pos + 2])
                        self.pos += 2
                        self.col += 2
                    elif self.text[self.pos] == '\n':
                        self.line += 1
                        self.col = 1
                        val.append('\n')
                        self.pos += 1
                    else:
                        val.append(self.text[self.pos])
                        self.pos += 1
                        self.col += 1
                if self.pos < self.length and self.text[self.pos] == '"':
                    self.pos += 1
                    self.col += 1
                self.tokens.append(Token("STRING", "".join(val), start_line, start_col))
                continue

            # Numbers (sized: 8'hFF, 8'b1010, 8'd255, 1'b0, '0, '1, unsized decimal: 123)
            # Check for Verilog sized literals: [0-9]*'[bB][01_xXzZ]+ or '[hH][0-9a-fA-F_]+ or '[dD][0-9_]+
            if ch.isdigit() or (ch == "'" and self.pos + 1 < self.length and self.text[self.pos + 1].lower() in 'bhdso01'):
                num_token = self._read_number()
                if num_token:
                    self.tokens.append(num_token)
                    continue

            # Multi-char operator
            matched_multi = False
            for op in MULTI_OPS:
                if self.text.startswith(op, self.pos):
                    self.tokens.append(Token("OPERATOR", op, self.line, self.col))
                    self.pos += len(op)
                    self.col += len(op)
                    matched_multi = True
                    break
            if matched_multi:
                continue

            # Single char operators/punctuation
            if ch in SINGLE_OPS:
                self.tokens.append(Token("OPERATOR", ch, self.line, self.col))
                self.pos += 1
                self.col += 1
                continue

            # Identifiers and System tasks ($display, $finish, etc.)
            if ch.isalpha() or ch == '_' or ch == '$':
                start_line = self.line
                start_col = self.col
                start_pos = self.pos
                self.pos += 1
                self.col += 1
                while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] in '_$'):
                    self.pos += 1
                    self.col += 1
                ident = self.text[start_pos:self.pos]
                if ident in KEYWORDS:
                    self.tokens.append(Token("KEYWORD", ident, start_line, start_col))
                else:
                    self.tokens.append(Token("IDENTIFIER", ident, start_line, start_col))
                continue

            # Unknown character, emit as operator/symbol
            self.tokens.append(Token("OPERATOR", ch, self.line, self.col))
            self.pos += 1
            self.col += 1

        self.tokens.append(Token("EOF", "", self.line, self.col))
        return self.tokens

    def _read_number(self) -> Optional[Token]:
        start_line = self.line
        start_col = self.col
        start_pos = self.pos

        # Read optional prefix digits (width)
        while self.pos < self.length and self.text[self.pos].isdigit():
            self.pos += 1
            self.col += 1

        # Check for base specifier: '[sS]?[bBoOdDhH]
        if self.pos < self.length and self.text[self.pos] == "'":
            self.pos += 1
            self.col += 1
            # optional signed 's'
            if self.pos < self.length and self.text[self.pos].lower() == 's':
                self.pos += 1
                self.col += 1
            # base: b, o, d, h
            if self.pos < self.length and self.text[self.pos].lower() in 'bodh':
                self.pos += 1
                self.col += 1
                # value digits
                while self.pos < self.length and (self.text[self.pos].isalnum() or self.text[self.pos] in '_?xXzZ'):
                    self.pos += 1
                    self.col += 1
                return Token("NUMBER", self.text[start_pos:self.pos], start_line, start_col)
            elif self.pos < self.length and self.text[self.pos] in '01':
                # e.g. '0 or '1
                self.pos += 1
                self.col += 1
                return Token("NUMBER", self.text[start_pos:self.pos], start_line, start_col)
            else:
                # Malformed base, rollback or return what we have
                return Token("NUMBER", self.text[start_pos:self.pos], start_line, start_col)

        # Unsized decimal, or float
        if self.pos < self.length and self.text[self.pos] == '.' and self.pos + 1 < self.length and self.text[self.pos + 1].isdigit():
            self.pos += 1
            self.col += 1
            while self.pos < self.length and self.text[self.pos].isdigit():
                self.pos += 1
                self.col += 1

        return Token("NUMBER", self.text[start_pos:self.pos], start_line, start_col)


class TokenStream:
    """Helper for recursive-descent parsing with lookahead and recovery."""
    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.idx = 0
        self.length = len(tokens)

    def current(self) -> Token:
        if self.idx < self.length:
            return self.tokens[self.idx]
        return self.tokens[-1] if self.tokens else Token("EOF", "", 1, 1)

    def peek(self, offset: int = 1) -> Token:
        p = self.idx + offset
        if 0 <= p < self.length:
            return self.tokens[p]
        return self.tokens[-1] if self.tokens else Token("EOF", "", 1, 1)

    def advance(self) -> Token:
        tok = self.current()
        if self.idx < self.length - 1:
            self.idx += 1
        return tok

    def match(self, *values: str) -> bool:
        c = self.current()
        return c.value in values or c.type in values

    def consume(self, expected_value: Optional[str] = None) -> Token:
        tok = self.current()
        if expected_value and tok.value != expected_value:
            # We don't necessarily raise here to allow recovery, but we advance
            pass
        self.advance()
        return tok

    def has_next(self) -> bool:
        return self.idx < self.length and self.current().type != "EOF"
