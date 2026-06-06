def safe_divide(a, b):
    if b == 0:
        raise ValueError("divisor cannot be zero")
    return a / b
