def minimum(arr):
    min_value=arr[0]
    for x in arr:
        if x<min_value:
            min_value=x
    return min_value