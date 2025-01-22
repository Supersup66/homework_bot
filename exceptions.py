class NoTokenError(Exception):
    """Отсутствует необходимый токен."""


class ResponseError(Exception):
    """Ошибка запроса на сервер."""


class ResponseStatusError(Exception):
    """Сервер вернул статус отличный от 200."""
