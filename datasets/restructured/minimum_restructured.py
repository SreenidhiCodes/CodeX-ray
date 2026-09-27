def minimum(arr):
    if not arr:
        return None

    result = arr[0]
    index = 1

    while index < len(arr):
        if arr[index] < result:
            result = arr[index]

        index += 1

    return result