fn add(a: i32, b: i32) -> i32 {
    a + b
}

fn multiply(x: i32, y: i32) -> i32 {
    let product = add(x, y);
    product
}

struct Calculator;

impl Calculator {
    fn compute(&self, n: i32) -> i32 {
        multiply(n, 2)
    }
}
