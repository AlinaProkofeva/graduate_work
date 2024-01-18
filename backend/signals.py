import datetime
from datetime import timedelta
import csv

from django.core.mail import EmailMultiAlternatives
from django.dispatch import receiver, Signal
from django.template.loader import get_template
from django_rest_passwordreset.models import ResetPasswordToken
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, Order, ORDER_STATE_CHOICES, DELIVERY_TIME_CHOICES, User
from shop_site import settings
from .tasks import task_send_email


new_account_registered = Signal('user_id')
new_order_state = Signal('order_id')
new_order_created = Signal('order_id')
backup_shop = Signal('user_id')
new_report = Signal('signal_kwargs')


# noinspection PyUnusedLocal
# noinspection PyUnresolvedReferences
@receiver(new_account_registered)
def register_account_signal(user_id: int, **kwargs) -> None:
    """
    Создание токена пользователя и отправка его в письме на email

    :param user_id: id пользователя
    """

    # генерим токен пользователю с указанным user_id
    token_user, _ = ConfirmEmailToken.objects.get_or_create(user_id=user_id)

    subject = f'Токен для подтверждения регистрации {token_user.user.email}'
    from_email = settings.EMAIL_HOST_USER
    to = [token_user.user.email]
    body = token_user.token

    # формируем и отправляем письмо через селери
    task_send_email.delay(subject, from_email, to, body)


# noinspection PyUnusedLocal
# noinspection PyUnresolvedReferences
@receiver(new_order_state)
def update_order_state_signal(order_id: int, **kwargs) -> None:
    """
    Отправка клиенту письма с информацией о новом статусе заказа

    :param order_id: id заказа
    """
    order = Order.objects.get(id=order_id)
    shop = order.ordered_items.first().product_info.shop.name
    order_created = order.datetime + timedelta(hours=settings.TIMEDELTA_FOR_ORDER_EMAIL)
    order_created = order_created.strftime("%Y-%m-%d %H:%M:%S")
    total_sum = [i for i in order.total_sum().values()][0]
    delivery_date = order.delivery_date
    delivery_time = tuple(filter(lambda x: order.delivery_time in x, DELIVERY_TIME_CHOICES))[0][1]
    address = order.contact
    new_address = f'{address.region},{address.district} {address.settlement} ул.: {address.street}, дом: ' \
                  f'{address.house}, корп.: {address.structure} стр.: {address.building} кв.: {address.apartment}'
    phone = order.contact.contact.phone
    new_phone = f'+7({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]} '

    # достаем русифицированное название статуса
    ru_state = tuple(filter(lambda item: order.state in item, ORDER_STATE_CHOICES))[0][1]

    context = {'order': order,
               'order_created': order_created,
               'ru_state': ru_state,
               'total_sum': total_sum,
               'delivery_date': delivery_date,
               'delivery_time': delivery_time,
               'phone': new_phone,
               'address': new_address
               }
    # формируем и отправляем письмо
    subject = f'{shop} - cтатус вашего заказа №{order_id} от {order_created} изменен на "{ru_state}"'
    from_email = settings.EMAIL_HOST_USER
    to = [order.user.email]
    body = f'Ваш заказ №{order_id} от {order_created} {ru_state}'
    html = get_template('backend/message_new_state.html').render(context)

    task_send_email.delay(subject, from_email, to, body, html)


# noinspection PyUnusedLocal
# noinspection PyUnresolvedReferences
@receiver(new_order_created)
def new_order_created_signal(order_id: int, **kwargs) -> None:
    """
    Отправка письма на почту покупателя о размещении заказа

    :param order_id: id заказа
    """
    order = Order.objects.get(id=order_id)
    shop = order.ordered_items.all().first().product_info.shop.name
    created_at = order.datetime + timedelta(hours=settings.TIMEDELTA_FOR_ORDER_EMAIL)
    created_at = created_at.strftime("%Y-%m-%d %H:%M:%S")
    total_sum = [i for i in order.total_sum().values()][0]
    delivery_date = order.delivery_date
    delivery_time = tuple(filter(lambda x: order.delivery_time in x, DELIVERY_TIME_CHOICES))[0][1]
    customer = order.user
    phone = order.contact.contact.phone
    new_phone = f'+7({phone[0:3]}) {phone[3:6]}-{phone[6:8]}-{phone[8:10]} '
    address = order.contact
    new_address = f'{address.region},{address.district} {address.settlement} ул.: {address.street}, дом: ' \
                  f'{address.house}, корп.: {address.structure} стр.: {address.building} кв.: {address.apartment}'

    context = {'order': order,
               'order_created': created_at,
               'shop': shop,
               'total_sum': total_sum,
               'delivery_date': delivery_date,
               'delivery_time': delivery_time,
               'customer': customer,
               'phone': new_phone,
               'address': new_address}

    # отправка письма о размещении покупателю
    subject = f'{shop} - Создан новый заказ №{order_id} от {created_at}'
    body = f'Вы создали новый заказ №{order_id} в магазине {shop}'
    from_email = settings.EMAIL_HOST_USER
    to = [order.user.email]
    html = get_template('backend/message_new_order.html').render(context)

    task_send_email.delay(subject, from_email, to, body, html)

    # отправка письма о размещении заказа магазину
    subject_partner = f'Создан новый заказ №{order_id} от {created_at}'
    body_partner = f'Получен новый заказ №{order_id}'
    from_email = settings.EMAIL_HOST_USER
    to_partner = [order.ordered_items.all().first().product_info.shop.user.email]
    html_partner = get_template('backend/message_new_state_partner.html').render(context)

    task_send_email.delay(subject_partner, from_email, to_partner, body_partner, html_partner)


# noinspection PyUnusedLocal
@receiver(reset_password_token_created)
def reset_password_token_signal(sender, instance, reset_password_token: ResetPasswordToken, **kwargs) -> None:
    """
    Отправка письма с токеном для сброса пароля

    :param reset_password_token: токен для подтверждения сброса и замены пароля
    """
    subject = f'Токен для сброса пароля пользователя {reset_password_token.user}'
    body = reset_password_token.key
    from_email = settings.EMAIL_HOST_USER
    to = [reset_password_token.user.email]

    task_send_email.delay(subject, from_email, to, body)


# noinspection PyUnusedLocal
@receiver(backup_shop)
def backup_shop_signal(user_id: int, **kwargs) -> None:
    """
    Отправка письма менеджеру магазина с резервной копией остатков склада

    :param user_id: id менеджера магазина
    """

    user = User.objects.get(id=user_id)
    filename = f'{user.shop.name}.yaml'

    subject = f'Остатки товаров на складе {user.shop.name}'
    body = f'Остатки товаров на складе {user.shop.name} на {datetime.datetime.now()}'
    from_email = settings.EMAIL_HOST_USER
    to = [user.email]

    # task_send_email.delay(subject, from_email, to, body, filename=filename)  # не видит файл FileNotFoundError(2, 'No
    # such file or directory')  No such file or directory: 'Связной.yaml' (??????)

    msg = EmailMultiAlternatives(
        subject=subject,
        from_email=from_email,
        to=to,
        body=body
    )
    content = open(filename, 'rb')
    msg.attach(filename, content.read(), 'text/yaml')
    msg.send()


@receiver(new_report)
def send_report(signal_kwargs: dict, **kwargs) -> None:
    """
    Отправка письма менеджеру с отчетом в теле письма и csv-вложением.

    :param signal_kwargs: словарь с данными для формирования вложения и html-отчета
    :return: None
    """

    data = signal_kwargs
    data['from_date'] = data['from_date'][8:] + '.' + data['from_date'][5:7] + '.' + data['from_date'][0:4]
    data['before_date'] = data['before_date'][8:] + '.' + data['before_date'][5:7] + '.' + data['before_date'][0:4]

    subject = f'Отчет заказов {data["shop"]} за период {data["from_date"]} - {data["before_date"]}'
    body = subject
    from_email = settings.EMAIL_HOST_USER
    to = [data["email"]]
    html = get_template('backend/message_report_partner.html').render(data)

    table_headers = ['Артикул', 'Наименование товара', 'Цена', 'Кол-во', 'Сумма']
    filename = f'отчет_{data["shop"]}_{data["from_date"]}_{data["before_date"]}.csv'

    # создаем файл с отчетом для вложения под открытие Excel Windows
    with open(filename, 'w', newline='', encoding='cp1251') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(table_headers)
        writer.writerows(data['data_structure'])

    msg = EmailMultiAlternatives(
        subject=subject,
        from_email=from_email,
        to=to,
        body=body
    )
    msg.attach_alternative(html, "text/html")
    content = open(filename, 'rb')
    msg.attach(filename, content.read(), 'text/csv')

    msg.send()
