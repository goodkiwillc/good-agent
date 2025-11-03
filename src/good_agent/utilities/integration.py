from contextlib import contextmanager


@contextmanager
def patch_method(cls, method_name, new_method):
    original = getattr(cls, method_name)
    setattr(cls, method_name, new_method)
    try:
        yield
    finally:
        setattr(cls, method_name, original)
