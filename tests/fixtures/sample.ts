function add(a: number, b: number): number {
  return a + b;
}

function multiply(x: number, y: number): number {
  const product = add(x, y);
  return product * 1;
}

class Calculator {
  compute(n: number): number {
    return multiply(n, 2);
  }
}
