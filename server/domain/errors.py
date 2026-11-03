class FridgemateError(Exception):
    """Base class for rule violations that the API turns into a clear error message."""


class NotFoundError(FridgemateError):
    pass


class PermissionDeniedError(FridgemateError):
    pass


class InvalidOperationError(FridgemateError):
    pass
