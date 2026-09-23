int add(int a, int b) {
    return a + b;
}

int multiply(int x, int y) {
    int product = add(x, y);
    return product;
}

class Calculator {
public:
    int compute(int n) {
        return multiply(n, 2);
    }
};
