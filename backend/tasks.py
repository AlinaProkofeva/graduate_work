from celery import shared_task
from django.core.mail import EmailMultiAlternatives
from django.utils.safestring import SafeString

from backend.models import ProductInfo, Shop
from backend.utils.get_data_from_yaml import get_or_greate_product_object, update_or_create_product_info, \
    create_parameter_for_product


@shared_task
def task_send_email(subject: str, from_email: str, to: list, body: str, html: SafeString = None,
                    filename: str = None) -> None:
    """
    Task для формирования и отправки письма

    :param subject: тема письма
    :param from_email: отправитель письма
    :param to: список адресов доставки письма
    :param body: тело письма
    :param html: шаблон с контекстом
    :param filename: наименование файла-вложения
    :return: None
    """
    msg = EmailMultiAlternatives(
        subject=subject,
        from_email=from_email,
        to=to,
        body=body
    )
    if html:
        msg.attach_alternative(html, "text/html")

    # if filename:  # не видит (?)...
    #     content = open(filename, 'rb')
    #     msg.attach(filename, content.read(), 'text/yaml')

    msg.send()


# noinspection PyUnresolvedReferences
@shared_task
def task_load_good_from_yaml(method: str, good: dict, shop_name: str, errors_list: list, errors: dict, counter: int) \
        -> tuple:
    """
    Task для PATCH-загрузки информации о товаре из накладной в БД (добавление товаров на остатки)

    :param method: http-метод запроса
    :param good: информация о товаре
    :param shop_name: наименование магазина
    :param errors_list: список ошибок
    :param errors: словарь со всеми данными ошибок
    :param counter: счетчик успешных загрузок
    :return: counter, errors  - кортеж из счетчика загрузок и словаря с ошибками
    """
    product = get_or_greate_product_object(good, errors_list, errors)[0]
    shop = Shop.objects.filter(name=shop_name).first()

    # определяем количество для товара, исходя из метода запроса
    new_quantity = None
    if method == 'PATCH':
        # суммируем кол-во товара для остатков или устанавливаем из накладной для нового товара
        shop_product = ProductInfo.objects.filter(shop=shop, external_id=good['id']).first()
        if shop_product:
            quantity_now = shop_product.quantity
            new_quantity = quantity_now + good['quantity']  # суммируем текущее кол-во с накладной
        else:
            new_quantity = good['quantity']  # устанавливаем кол-во из накладной

    elif method == 'POST':
        # определяем количество
        new_quantity = good['quantity']

    # обновляем количество товара на остатках или добавляем товар на остатки
    result = update_or_create_product_info(
        good, product, shop, new_quantity, counter, errors_list, errors)
    shop_product, counter = result[0], result[1]

    # Переходим к заполнению/обновлению параметров модели
    if shop_product:
        parameters = good['parameters']
        create_parameter_for_product(parameters, shop_product)

    return counter, errors
