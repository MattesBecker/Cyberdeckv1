import math
import re
from typing import List, Tuple


TOKEN_PATTERN = re.compile(r"\s*(?:(\d+(?:\.\d*)?|\.\d+)|([+\-*/%^()]))")


class CalculatorError(ValueError):
    pass


class Calculator:
    """Tiny arithmetic parser; it never evaluates Python source."""

    def calculate(self, expression: str) -> float:
        if not isinstance(expression, str) or not expression.strip():
            raise CalculatorError("Enter an expression")
        if len(expression) > 200:
            raise CalculatorError("Expression too long")
        parser = _Parser(self._tokenize(expression.strip()))
        value = parser.parse_expression()
        if not parser.at_end:
            raise CalculatorError("Unexpected input")
        if not math.isfinite(value) or abs(value) > 1e100:
            raise CalculatorError("Result is too large")
        return value

    @staticmethod
    def format_result(value: float) -> str:
        if value == 0:
            return "0"
        if value.is_integer() and abs(value) < 1e16:
            return str(int(value))
        return "{0:.12g}".format(value)

    @staticmethod
    def _tokenize(expression: str) -> List[Tuple[str, str]]:
        tokens = []
        position = 0
        while position < len(expression):
            match = TOKEN_PATTERN.match(expression, position)
            if match is None:
                raise CalculatorError("Invalid character")
            if match.group(1) is not None:
                tokens.append(("number", match.group(1)))
            else:
                tokens.append(("operator", match.group(2)))
            position = match.end()
        return tokens


class _Parser:
    def __init__(self, tokens: List[Tuple[str, str]]) -> None:
        self.tokens = tokens
        self.position = 0

    @property
    def at_end(self) -> bool:
        return self.position == len(self.tokens)

    def parse_expression(self) -> float:
        value = self._parse_term()
        while self._peek("+", "-"):
            operator = self._take()[1]
            right = self._parse_term()
            value = value + right if operator == "+" else value - right
            self._check(value)
        return value

    def _parse_term(self) -> float:
        value = self._parse_unary()
        while self._peek("*", "/", "%"):
            operator = self._take()[1]
            right = self._parse_unary()
            try:
                if operator == "*":
                    value *= right
                elif operator == "/":
                    value /= right
                else:
                    value %= right
            except ZeroDivisionError as exc:
                raise CalculatorError("Division by zero") from exc
            self._check(value)
        return value

    def _parse_unary(self) -> float:
        if self._peek("+", "-"):
            operator = self._take()[1]
            value = self._parse_unary()
            return value if operator == "+" else -value
        return self._parse_power()

    def _parse_power(self) -> float:
        value = self._parse_primary()
        if self._peek("^"):
            self._take()
            exponent = self._parse_unary()
            if abs(exponent) > 1000:
                raise CalculatorError("Exponent is too large")
            try:
                value = value ** exponent
            except (OverflowError, ValueError, ZeroDivisionError) as exc:
                raise CalculatorError("Invalid power") from exc
            if isinstance(value, complex):
                raise CalculatorError("Complex results are not supported")
            self._check(value)
        return value

    def _parse_primary(self) -> float:
        if self.position >= len(self.tokens):
            raise CalculatorError("Expression is incomplete")
        kind, value = self._take()
        if kind == "number":
            try:
                return float(value)
            except ValueError as exc:
                raise CalculatorError("Invalid number") from exc
        if value == "(":
            result = self.parse_expression()
            if not self._peek(")"):
                raise CalculatorError("Missing closing bracket")
            self._take()
            return result
        raise CalculatorError("Unexpected input")

    def _peek(self, *operators: str) -> bool:
        return (
            self.position < len(self.tokens)
            and self.tokens[self.position][0] == "operator"
            and self.tokens[self.position][1] in operators
        )

    def _take(self) -> Tuple[str, str]:
        token = self.tokens[self.position]
        self.position += 1
        return token

    @staticmethod
    def _check(value: float) -> None:
        if not math.isfinite(value) or abs(value) > 1e100:
            raise CalculatorError("Result is too large")
