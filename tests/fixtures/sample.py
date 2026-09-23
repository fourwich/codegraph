def add(a: int, b: int) -> int:
    return a + b


def multiply(x: int, y: int) -> int:
    product = add(x, y)
    return product


class Calculator:
    def compute(self, n: int) -> int:
        return multiply(n, 2)
