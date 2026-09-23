package main

func add(a int, b int) int {
	return a + b
}

func multiply(x int, y int) int {
	product := add(x, y)
	return product
}

func compute(n int) int {
	return multiply(n, 2)
}
