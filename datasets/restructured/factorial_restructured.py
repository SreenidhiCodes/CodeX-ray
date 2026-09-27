def factorial(n):
    if n < 0:
        return None

    result = 1
    counter = n

    while counter > 1:
        result = result * counter
        counter -= 1

    return result