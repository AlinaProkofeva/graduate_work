import random
from unittest.mock import patch
import pytest
from django.contrib.auth.hashers import check_password
from django.urls import reverse
from django_rest_passwordreset.models import ResetPasswordToken
from model_bakery import baker

from backend.models import Shop, User, ConfirmEmailToken
from backend.tasks import task_send_email
from tests.backend.conftest import make_productinfo
from backend.utils.error_text import Error


# noinspection PyUnresolvedReferences
@pytest.mark.django_db
@pytest.mark.parametrize(
    ['name', 'url', 'state', 'exp_code', 'length'],
    (
            ('Евросеть', 'http://ev.ru', True, 200, 1),
            ('Евросеть', '111', False, 200, 0))
)
def test_get_shops(client_pytest, name, url, state, exp_code, length):
    """Проверяем, что показывает только магазины со статусом приема заявок True"""
    Shop.objects.create(name=name, url=url, state=state)
    res = client_pytest.get(reverse('shops'))
    assert res.status_code == exp_code
    data = res.json()
    assert length == len(data)
    if len(data) > 0:
        assert data[0]['name'] == name
        assert data[0]['url'] == url
        assert data[0]['state'] == state


@pytest.mark.parametrize(
    ['shop_1', 'quantity_1', 'shop_2', 'quantity_2'],
    (
            ('Связной', 2, 'Евросеть', 3),
    )
)
@pytest.mark.django_db
def test_productinfo_get(client_pytest, shop_1, quantity_1, shop_2, quantity_2):
    """Проверяем, что get отображает все товары во всех магазинах"""

    make_productinfo(quantity_1, shop_1)
    make_productinfo(quantity_2, shop_2)

    res = client_pytest.get(reverse('products'))
    data = res.json()

    assert res.status_code == 200
    assert len(data) == quantity_1 + quantity_2

    # Проверяем, что товаров созданы именно в заданных магазинах в заданном количестве
    counter_shop_1 = 0
    counter_shop_2 = 0
    for i in data:
        if i['shop'] == shop_1:
            counter_shop_1 += 1
        elif i['shop'] == shop_2:
            counter_shop_2 += 1

    assert counter_shop_1 == quantity_1
    assert counter_shop_2 == quantity_2


@pytest.mark.parametrize(
    ['shop_1', 'quantity_1', 'shop_2', 'quantity_2', 'filter_name', 'filter_value', 'exp_res', 'extra_arg'],
    (
            ('Связной', 5, 'Евросеть', 4, 'shop_id', None, 5, None),             # фильтр по id магазина
            ('Связной', 5, 'Евросеть', 4, 'shop_id', 99999, 1, None),         # несуществующий id магазина, сообщение
                                                                              # об ошибке в данных FK
            ('Связной', 5, 'Евросеть', 4, 'shop_name', 'евро', 4, None),         # фильтр по названию магазина
            ('Связной', 5, 'Евросеть', 4, 'shop_name', 'билайн', 0, None),       # несуществующий магазин
            ('Связной', 6, 'Евросеть', 4, 'price_less', 5000, 6, None),          # фильтр по цене МЕНЬШЕ
            ('Связной', 7, 'Евросеть', 4, 'price_more', 7000, 4, None),          # фильтр по цене БОЛЬШЕ
            ('Связной', 5, 'Евросеть', 3, 'category_id', None, 5, None),         # фильтр по id категории товара
            ('Связной', 5, 'Евросеть', 3, 'category_id', 8888, 0, None),         # несуществующий id категории товара
            ('Связной', 8, 'Евросеть', 6, 'category', 'смарт', 8, 'Смартфон'),   # фильтр по id категории товара
            ('Связной', 8, 'Евросеть', 6, 'category', 'аксес', 0, 'Смартфон'),   # нет категории с таким названием
    )
)
@pytest.mark.django_db
def test_productinfo_get_filters(client_pytest, shop_1, quantity_1, shop_2, quantity_2, filter_name, filter_value,
                                 exp_res, extra_arg):
    """Проверяем, что get корректно отображает заданные фильтры"""

    # Добавляем критерии создания товара на складе при необходимости
    add_opt_1 = {}
    add_opt_2 = {}
    if filter_name in ('price_more', 'price_less'):
        add_opt_1.update(price_start=1, price_max=(filter_value - 1))
        add_opt_2.update(price_start=filter_value, price_max=999999)
    elif filter_name == 'category':
        add_opt_1.update(category_name=extra_arg)

    goods_1 = make_productinfo(quantity_1, shop_1, **add_opt_1)
    make_productinfo(quantity_2, shop_2, **add_opt_2)

    # Переопределяем значения фильтров id (не задаются напрямую и могут меняться при изменении файла)
    if filter_name == 'shop_id' and filter_value is None:
        filter_value = goods_1[0].shop.id
    elif filter_name == 'category_id' and filter_value is None:
        filter_value = goods_1[0].product.category.id

    res = client_pytest.get(reverse('products'), {filter_name: filter_value})
    data = res.json()

    assert len(data) == exp_res


@pytest.mark.parametrize(
    ['shop_1', 'quantity_1', 'filter_name', 'filter_value', 'exp_res', 'model', 'prod_name', 'param'],
    (
            ('Связной', 4, 'search', 'appl', 4, 'apple-iphone-13-mini-blue',
             'Смартфон iPhone 13 mini Blue', 'камера'),  # search по названию модели
            ('Связной', 4, 'search', 'samsunger', 0, 'apple-iphone-13-mini-blue',
             'Смартфон iPhone 13 mini Blue', 'камера'),  # search по несуществующему названию модели
            ('Связной', 3, 'search', 'Смартфон iPho', 3, 'apple-iphone-13-mini-blue',
             'Смартфон iPhone 13 mini Blue', 'камера'),  # search по названию продукта
            ('Связной', 2, 'search', 'Кабель Olmio', 0, 'apple-iphone-13-mini-blue',
             'Смартфон iPhone 13 mini Blue', 'камера'),  # search по несуществующему названию продукта
            ('Связной', 3, 'search', 'гироск', 3, 'apple-iphone-13-mini-blue',
             'Смартфон iPhone 13 mini Blue', 'гироскоп'),  # search по названию параметра товара
            ('Связной', 4, 'search', 'гироск', 0, 'apple-iphone-13-mini-blue',
             'Смартфон iPhone 13 mini Blue', 'камера'),  # search по несуществующему названию параметра товара
    )
)
@pytest.mark.django_db
def test_productinfo_get_search_filter(client_pytest, shop_1, quantity_1, filter_name, filter_value, exp_res, model,
                                       prod_name, param):
    """Проверяем, что get корректно отображает заданные search-фильтры"""

    make_productinfo(quantity_1, shop_name=shop_1, model=model, prod_name=prod_name, param=param)
    make_productinfo(random.randint(1, 5))
    make_productinfo(random.randint(1, 5))

    res = client_pytest.get(reverse('products'), {filter_name: filter_value})
    assert res.status_code == 200
    data = res.json()

    assert len(data) == exp_res


@pytest.mark.parametrize(
    ['shop_name', 'category_name'],
    (
            ('Связной', 'ПО'),
            ('Беталинк', 'Аксессуары')
    )
)
@pytest.mark.django_db
def test_productinfo_detail(client_pytest, shop_name, category_name):
    """Проверка корректного получения get данных по id productinfo"""

    good = make_productinfo(1, shop_name=shop_name, category_name=category_name)
    make_productinfo(2)

    res = client_pytest.get(reverse('product_detail', args=[good[0].id]))
    assert res.status_code == 200

    data = res.json()
    assert data['id'] == good[0].id
    assert data['shop'] == shop_name
    assert data['product']['category'] == category_name


@patch.object(task_send_email, 'delay')  # мокаем таску
@pytest.mark.parametrize(
    ['first_name', 'last_name', 'email', 'password', 'exp_res', 'error_text'],
    (
            ('Клиент', 'Тестовый', 'customer@m.ru', '1234Qwerty!!!', 201, None),     # все ОК
            ('Клиент2', 'Тестовый', None, '1234Qwerty!!!', 400,
             'Это поле не может быть пустым.'),                                      # нет почты
            ('Клиент2', 'Тестовый', 'customer', '1234Qwerty!!!', 400,
             'Введите правильный адрес электронной почты.'),                         # некорректная почта
            ('Клиент2', None, 'customer@m.ru', '1234Qwerty!!!', 400,
             'Это поле не может быть пустым.'),                                      # нет фамилии
            (None, 'Тестовый', 'customer@m.ru', '1234Qwerty!!!', 400,
             'Это поле не может быть пустым.'),                                      # нет имени
            ('Клиент2', 'Тестовый', 'customer@m.ru', '1234', 400,
             'Введённый пароль слишком короткий.'),                                  # некорректный пароль
    )
)
@pytest.mark.django_db
def test_register_user_buyer(mock_delay, client_pytest, first_name, last_name, email, password, exp_res, error_text):
    """Проверяем регистрацию нового пользователя в неактивном статусе и с корректным типом, корректную отработку
    валидации и возврат ошибок в response"""

    post_data = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'password': password
    }
    res = client_pytest.post(reverse('user_register'), data=post_data)
    assert res.status_code == exp_res

    # проверяем сообщения об ошибке в response
    data = res.json()
    if res.status_code != 201:
        if len(data) == 1:
            assert error_text in list(data.values())[0][0]
        else:
            assert True in list(map(lambda x: error_text in x, list(data.values())[1]))

    if res.status_code == 201:
        user = User.objects.get(email=email)
        assert user.is_active is False
        assert user.first_name == first_name
        assert user.last_name == last_name
        assert user.type == 'buyer'


# noinspection PyUnresolvedReferences
@patch.object(task_send_email, 'delay')
@pytest.mark.parametrize(
    ['first_name', 'last_name', 'email', 'password', 'company', 'position', 'type_user', 'exp_res'],
    (
            ('Менеджер', 'Тестовый', 'manager@m.ru', '1234Qwerty!!!',
             'Связной', 'manager', 'shop', 201),                            # все ОК
            ('Менеджер', 'Тестовый', 'manager@m.ru', '1234Qwerty!!!',
             'Связной', 'manager', 'False', 400),                           # некорректный тип пользователя
    )
)
@pytest.mark.django_db
def test_register_user_manager(mock_delay, client_pytest, first_name, last_name, email, password, company, position,
                               type_user, exp_res):
    """Проверяем регистрацию нового менеджера магазина в неактивном статусе и с корректным типом, создание токена
    для активации аккаунта"""

    post_data = {
        'first_name': first_name,
        'last_name': last_name,
        'email': email,
        'password': password,
        'company': company,
        'position': position,
        'type': type_user
    }
    res = client_pytest.post(reverse('user_register'), data=post_data)
    assert res.status_code == exp_res

    if res.status_code == 201:
        user = User.objects.get(email=email)
        assert user.is_active is False
        assert user.first_name == first_name
        assert user.last_name == last_name
        assert user.company == company
        assert user.position == position
        assert user.type == type_user

        # Проверяем, что пользователю был выписан токен активации
        activate_token = ConfirmEmailToken.objects.get(user=user)
        assert user.confirm_email_token.first().token == activate_token.token


@pytest.mark.django_db
@pytest.mark.parametrize(
    ['email', 'correctness', 'exp_res', 'exp_active', 'arg_1', 'value_1', 'arg_2', 'value_2', 'error_text'],
    (
            ('any@m.ru', True, 200, True, None, None, None, None, None),            # все ОК
            ('any@m.ru', False, 400, False, 'email', 'any@m.ru', 'None', 'None',
             Error.NOT_REQUIRED_ARGS.value),                                        # нет токена в data
            ('any@m.ru', False, 400, False, 'token', '1234rf', 'None', 'None',
             Error.NOT_REQUIRED_ARGS.value),                                        # нет почты в data
            ('any@m.ru', False, 400, False, 'email', 'any', 'token', '1234rf',
             Error.EMAIL_WRONG.value),                                              # некорректная почта
            ('any@m.ru', False, 400, False, 'email', 'any@m.ru', 'token', '1234rf',
             Error.EMAIL_OR_TOKEN_WRONG.value),                                     # некорректный токен
    )
)
def test_confirm_account(client_pytest, email, correctness, exp_res, exp_active, arg_1, value_1, arg_2, value_2,
                         error_text):
    """Проверяем активацию пользователя при подтверждении регистрации, валидацию данных и корректность response при
    ошибках"""

    user = baker.make(User, email=email)
    assert user.is_active is False
    activate_token = baker.make(ConfirmEmailToken, user=user)

    post_data = {}
    if correctness:
        post_data.update(email=email, token=activate_token.token)
    else:
        kw = {arg_1: value_1, arg_2: value_2}
        post_data.update(**kw)

    res = client_pytest.post(reverse('user_register_confirm'), post_data)
    assert res.status_code == exp_res
    assert User.objects.filter(email=email).first().is_active == exp_active

    data = res.json()
    if exp_res != 200:
        assert data == error_text


# noinspection PyUnresolvedReferences
@patch.object(task_send_email, 'delay')
@pytest.mark.parametrize(
    ['email', 'arg', 'value', 'exp_res'],
    (
            ('any@m.ru', 'email', 'any@m.ru', 200),         # все ОК
            ('any@m.ru', 'not_email', 'any@m.ru', 400)      # нет почты в data
    )
)
@pytest.mark.django_db
def test_reset_password_request(mock_delay, client_pytest, email, arg, value, exp_res):
    """Проверяем запрос сброса пароля, что создается токен на сброс"""

    user = User.objects.create(is_active=True, email=email, password='1234Qwerty!!!')
    post_data = {arg: value}
    res = client_pytest.post(reverse('password_reset'), post_data)
    assert res.status_code == exp_res

    if res.status_code == 200:
        assert ResetPasswordToken.objects.filter(user=user).exists() is True


# noinspection PyUnresolvedReferences
@patch.object(task_send_email, 'delay')
@pytest.mark.parametrize(
    ['email', 'arg_1', 'value_1', 'arg_2', 'value_2', 'exp_res'],
    (
            ('any@m.ru', 'password', 'newpass1234!!!', 'token', 'TO_UPD', 200),    # все ОК (переопределить токен!)
            ('any@m.ru', 'password', 'newpass1234!!!', 'token', 'qwe345', 404),    # неверный токен
            ('any@m.ru', 'passwor', 'newpass1234!!!', 'token', 'TO_UPD', 400),     # нет пароля
            ('any@m.ru', 'password', 'newpass1234!!!', 'toke', 'qqq111', 400),     # нет токена
            ('any@m.ru', 'password', '1234', 'token', 'TO_UPD', 400)               # некорректный пароль
    )
)
@pytest.mark.django_db
def test_reset_password_confirm(mock_delay, client_pytest, email, arg_1, value_1, arg_2, value_2, exp_res):
    """Проверяем сброс и смену пароля по токену"""

    user = User.objects.create(is_active=True, email=email, password='1234Qwerty!!!')
    client_pytest.post(reverse('password_reset'), {'email': email})

    if value_2 == 'TO_UPD':
        value_2 = ResetPasswordToken.objects.get(user=user).key
    post_data = {arg_1: value_1, arg_2: value_2}

    res = client_pytest.post(reverse('password_reset_confirm'), post_data)
    assert res.status_code == exp_res

    # проверяем смену пароля на новый
    if exp_res == 200:
        passw = User.objects.get(email=email).password
        check = check_password(value_1, passw)
        assert check is True
