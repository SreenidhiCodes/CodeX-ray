def maximum(arr):
    max_value = arr[0]

    for x in arr:
        if x > max_value:
            max_value = x

    return max_value