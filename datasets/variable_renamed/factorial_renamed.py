def factorial(number):
    answer = 1

    for value in range(1, number + 1):
        answer = answer * value

    return answer