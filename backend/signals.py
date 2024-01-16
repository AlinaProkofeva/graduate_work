from datetime import timedelta
from django.dispatch import receiver, Signal
from django.template.loader import get_template
from django_rest_passwordreset.models import ResetPasswordToken
from django_rest_passwordreset.signals import reset_password_token_created

from backend.models import ConfirmEmailToken, Order, ORDER_STATE_CHOICES, DELIVERY_TIME_CHOICES
from shop_site import settings
from .tasks import task_send_email


new_account_registered = Signal('user_id')
new_order_state = Signal('order_id')
new_order_created = Signal('order_id')


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
