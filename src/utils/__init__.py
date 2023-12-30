def search(source: str, target: str):
    """
    Use a smart search to compare two strings.
    """
    for word in target.split():
        if word.lower() not in source.lower():
            return False
    return True
