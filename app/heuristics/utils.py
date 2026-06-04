def _count_digits(val: str) -> int:
    count = 0
    for ch in val:
        if ch.isdigit():
            count += 1
    return count
