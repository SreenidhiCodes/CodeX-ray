def maximum(numbers):
    largest = numbers[0]

    for value in numbers:
        if value > largest:
            largest = value

    return largest