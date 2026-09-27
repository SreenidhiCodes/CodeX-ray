def is_prime(n):
    if n < 2:
        return False

    divisor = 2

    while divisor < n:
        if n % divisor == 0:
            return False

        divisor += 1

    return True