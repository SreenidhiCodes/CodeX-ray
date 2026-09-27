def minimum(numbers):
    smallest = numbers[0]

    for value in numbers:
        if value < smallest:
            smallest = value

    return smallest