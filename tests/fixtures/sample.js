function add(a, b) {
  return a + b;
}

function multiply(x, y) {
  const product = add(x, y);
  return product;
}

const calc = {
  compute(n) {
    return multiply(n, 2);
  }
};
