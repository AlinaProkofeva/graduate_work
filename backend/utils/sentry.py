# проверка работоспособности sentry

# 1. Функция, вызывающая ошибку при обращении по url
# 2. При получении изображений партнером (GET   partner/images/), если у пользователя нет привязанного магазина
# вызывается sentry_sdk.capture_message('count RelatedObjectDoesNotExist exceptions') - просто для статистики
# частоты ошибки и отслеживания смысла проверять исключение


from rest_framework.decorators import api_view


@api_view(['GET'])
def sentry_test_trigger_error(request):
    """
    Быстрая проверка работоспособности sentry в проекте для вызова в url

    Вызывает ошибку при отправке запроса.
    """

    raise Exception('test sentry')
