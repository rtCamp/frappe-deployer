class SpinnerColumn:
    def __init__(self, *args, **kwargs):
        pass


class TextColumn:
    def __init__(self, *args, **kwargs):
        pass


class Progress:
    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add_task(self, *args, **kwargs):
        return 0

    def update(self, *args, **kwargs):
        pass
