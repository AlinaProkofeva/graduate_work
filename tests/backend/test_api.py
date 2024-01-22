import random
from unittest.mock import patch

import oauth2_provider
import pytest
from django.contrib.auth.hashers import check_password
from django.urls import reverse
from django_rest_passwordreset.models import ResetPasswordToken
from model_bakery import baker
from rest_framework.authtoken.models import Token

from backend.models import Shop, User, ConfirmEmailToken, Category, Order, OrderItem
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


# noinspection PyUnresolvedReferences
@pytest.mark.django_db
@pytest.mark.parametrize(
    ['email', 'password', 'arg_1', 'value_1', 'arg_2', 'value_2', 'exp_res', 'exp_error'],
    (
            ('any@m.ru', '1234Qwerty!', 'email', 'any@m.ru', 'password', '1234Qwerty!',
             201, None),                                                                 # все ОК
            ('any@m.ru', '1234Qwerty!', 'email', 'none@m.ru', 'password', '1234Qwerty!',
             400, Error.AUTH_FAILED.value),                                              # неверная почта
            ('any@m.ru', '1234Qwerty!', 'emai', 'none@m.ru', 'password', '1234Qwerty!',
             400, Error.NOT_REQUIRED_ARGS.value),                                        # нет почты в data
            ('any@m.ru', '1234Qwerty!', 'email', 'none@m.ru', 'passwor', '1234Qwerty!',
             400, Error.NOT_REQUIRED_ARGS.value),                                        # нет пароля в data
            ('any@m.ru', '1234Qwerty!', 'email', 'None', 'password', '1234Qwerty!',
             400, Error.EMAIL_WRONG.value),                                              # неверный формат почты
    )
)
def test_login_account_not_vk(client_pytest, email, password, arg_1, value_1, arg_2, value_2, exp_res, exp_error):
    """Проверяем авторизацию пользователя и корректность возвращаемых ошибок в response, НЕ через VK"""

    user = User.objects.create_user(email=email, password=password, is_active=True)
    # baker.make(User, email=email, password=password, is_active=True)  # не хэширует пароль при создании О_о

    post_data = {arg_1: value_1, arg_2: value_2}
    res = client_pytest.post(reverse('user_login'), post_data)
    data = res.json()

    assert res.status_code == exp_res

    if res.status_code == 201:
        assert data['Token'] == Token.objects.get(user=user).key
    else:
        assert data == exp_error


# noinspection PyUnresolvedReferences
@pytest.mark.django_db
@pytest.mark.parametrize(
    ['email', 'password', 'arg_1', 'value_1', 'exp_res'],
    (
            ('any@m.ru', '1234Qwerty!', 'email', 'TO_UPD', 201),         # все ОК
            ('any@m.ru', '1234Qwerty!', 'email', '1234r', 400),          # несуществующий access token

    )
)
def test_login_account_vk(client_pytest, email, password, arg_1, value_1, exp_res):
    """Проверяем авторизацию при регистрации через VK (по VK access token)"""

    user = User.objects.create_user(email=email, password=password, is_active=True)
    vk_token = baker.make(oauth2_provider.models.AccessToken, user=user)
    if value_1 == 'TO_UPD':
        value_1 = vk_token.token

    post_data = {arg_1: value_1}
    res = client_pytest.post(reverse('user_login'), post_data)
    data = res.json()

    assert res.status_code == exp_res
    if res.status_code == 201:
        assert data['Token'] == Token.objects.get(user=user).key


# noinspection PyUnresolvedReferences
@pytest.mark.django_db
@pytest.mark.parametrize(
    ['email', 'test_token', 'exp_res', 'exp_res_text', 'exp_check_token'],
    (
            ('any@m.ru', 'TO_UPD',  200, {'Status': True}, False),                            # все ОК
            ('any@m.ru', 'random_token',  401, {'detail': 'Недопустимый токен.'}, True),      # неверный токен
            ('any@m.ru', None,  403, Error.USER_NOT_AUTHENTICATED.value, True),               # нет токена в headers

    )
)
def test_logout(client_pytest, test_token, email, exp_res, exp_res_text, exp_check_token):
    """Проверяем выход из системы, удаление auth-токена"""

    user = User.objects.create_user(email=email, is_active=True)
    auth_token = Token.objects.create(user=user)

    user_token = None
    if test_token == 'TO_UPD':
        user_token = auth_token.key
    elif test_token == 'random_token':
        user_token = test_token
    elif test_token is None:
        pass

    if user_token:
        client_pytest.credentials(HTTP_AUTHORIZATION=f'Token {user_token}')

    res = client_pytest.post(reverse('user_logout'))
    data = res.json()
    check_auth_token = Token.objects.filter(user=user).exists()

    assert res.status_code == exp_res
    assert data == exp_res_text
    assert check_auth_token == exp_check_token


# noinspection PyUnresolvedReferences
@pytest.mark.django_db
@pytest.mark.parametrize(
    ['email', 'first_name', 'last_name',  'company', 'position', 'user_type', 'test_token', 'exp_res', 'exp_res_text'],
    (
            ('any@m.ru', 'Покупатель', 'Тестовый', None, None, None,
             'TO_UPD', 200, None),                                          # покупатель ОК
            ('any@m.ru', 'Покупатель', 'Тестовый', None, None, None,
             None, 403, Error.USER_NOT_AUTHENTICATED.value),                # нет авторизации
            ('any@m.ru', 'Покупатель', 'Тестовый', None, None, None,
             'random_token', 401, {'detail': 'Недопустимый токен.'}),       # нет авторизации
            ('any@m.ru', 'Менеджер', 'Тестовый', 'Евросеть', 'ТД', 'shop',
             'TO_UPD', 200, None),                                          # менеджер ОК

    )
)
def test_get_account_details(client_pytest, email, first_name, last_name, company, position, user_type, test_token,
                             exp_res, exp_res_text):
    """Проверяем отображение основной информации об аккаунте, корректное отображение информации об ошибках в
    response, корректность сериалайзера для менеджера"""

    user_data = {'email': email, 'first_name': first_name, 'last_name': last_name}
    if company or position or user_type:
        user_data.update(company=company, position=position, type=user_type)

    user = User.objects.create_user(is_active=True, **user_data)
    auth_token = Token.objects.create(user=user)

    user_token = None
    if test_token == 'TO_UPD':
        user_token = auth_token.key
    elif test_token == 'random_token':
        user_token = test_token
    elif test_token is None:
        pass

    if user_token:
        client_pytest.credentials(HTTP_AUTHORIZATION=f'Token {user_token}')

    res = client_pytest.get(reverse('user_details'))
    data = res.json()

    assert res.status_code == exp_res

    if res.status_code == 200:
        assert data['first_name'] == first_name
        assert data['last_name'] == last_name
        assert data['email'] == email

        if user.type == 'shop':
            assert data['company'] == company
            assert data['position'] == position
            assert data['type'] == user_type

    else:
        assert data == exp_res_text


# noinspection PyUnresolvedReferences
@patch.object(task_send_email, 'delay')
@pytest.mark.django_db
@pytest.mark.parametrize(
    ['email', 'arg_1', 'value_1',  'test_token', 'exp_res', 'exp_res_text'],
    (
            ('any@m.ru', '', '', None, 403, Error.USER_NOT_AUTHENTICATED.value),     # нет токена в data
            ('any@m.ru', '', '', 'TO_UPD', 400, Error.NOT_REQUIRED_ARGS.value),      # нет новых данных
            ('any@m.ru', 'password', '1234', 'TO_UPD', 400, None),                   # некорректный новый пароль
            ('any@m.ru', 'email', '1234', 'TO_UPD', 400, Error.EMAIL_WRONG.value),   # некорректная новая почта
            ('any@m.ru', 'first_name', 'НовоеИмя', 'TO_UPD', 200, None),             # ОК, новое имя
            ('any@m.ru', 'last_name', 'НоваяФамилия', 'TO_UPD', 200, None),          # ОК, новая фамилия
            ('any@m.ru', 'company', 'НоваяКомпания', 'TO_UPD', 200, None),           # ОК, новая компания
            ('any@m.ru', 'position', 'НоваяДолжность', 'TO_UPD', 200, None),         # ОК, новая должность
            ('any@m.ru', 'type', 'shop', 'TO_UPD', 200, None),                       # ОК, новый тип
            ('any@m.ru', 'type', 'shopqqw', 'TO_UPD', 400, None),                    # неверный тип пользователя
            ('any@m.ru', 'password', 'Qwerty1234!', 'TO_UPD', 200, None),            # ОК, новый пароль
            ('any@m.ru', 'email', 'new@m.ru', 'TO_UPD', 200, None),                  # ОК, новая почта

    )
)
def test_patch_account_details(mock_delay, client_pytest, email, arg_1, value_1, test_token, exp_res, exp_res_text):
    """Проверяем редактирование данных аккаунта пользователя, корректность response, детализацию ошибок"""

    # создаем пользователя и auth-token для него
    user = baker.make(User, email=email, is_active=True)
    auth_token = Token.objects.create(user=user)

    # определяем токен для headers в запросе
    user_token = None
    if test_token == 'TO_UPD':
        user_token = auth_token.key
    elif test_token == 'random_token':
        user_token = test_token
    elif test_token is None:
        pass

    # устанавливаем токен в headers
    if user_token:
        client_pytest.credentials(HTTP_AUTHORIZATION=f'Token {user_token}')

    # определяем data для запроса и отправляем запрос
    post_data = {}
    if arg_1:
        post_data = {arg_1: value_1}
    res = client_pytest.patch(reverse('user_details'), data=post_data)
    data = res.json()

    assert res.status_code == exp_res

    if res.status_code != 200:
        if arg_1 == 'password':
            assert 'Введённый пароль слишком короткий.' in data['Errors'][0]
        elif arg_1 == 'type':
            assert f'Значения {value_1} нет среди допустимых вариантов.' in list(data['Error'].values())[0]
        else:
            assert data == exp_res_text
    else:
        if arg_1 == 'password':
            user = User.objects.get(email=email)
            assert user.check_password(value_1) is True
        else:
            assert data[arg_1] == value_1


@pytest.mark.django_db
@pytest.mark.parametrize(
    ['exp_res_1', 'quantity'],
    (
            (200, 10),
    )
)
def test_get_categories(client_pytest, exp_res_1, quantity):
    """Проверяем получение категорий товара, что отображает все и названию соответствуют имеющимся в базе"""

    cats = baker.make(Category, _quantity=quantity)

    res = client_pytest.get(reverse('categories'))
    data = res.json()

    assert res.status_code == exp_res_1
    assert len(data) == quantity

    # упорядочиваем по id, т.к. сортировка по наименованию по умолчанию
    data.sort(key=lambda x: x['id'])
    for index, i in enumerate(data):
        assert i['name'] == cats[index].name


# noinspection PyUnresolvedReferences
@pytest.mark.django_db
@pytest.mark.parametrize(
    ['email', 'test_token', 'is_buyer', 'arg_1', 'value_1', 'arg_2', 'value_2', 'arg_3', 'value_3', 'exp_res',
     'exp_error_text'],
    (
        ('any@m.ru', None, False, None, None, None, None, None, None,
         403, Error.USER_NOT_AUTHENTICATED.value),                                  # нет токена в headers
        ('any@m.ru', 'TO_UPD', False, None, None, None, None, None, None,
         400, Error.NOT_REQUIRED_ARGS.value),                                       # нет product_id & rating в data
        ('any@m.ru', 'TO_UPD', False, 'product_id', 1, None, None, None, None,
         400, Error.NOT_REQUIRED_ARGS.value),                                       # нет rating в data
        ('any@m.ru', 'TO_UPD', False, None, None, 'rating', 4, None, None,
         400, Error.NOT_REQUIRED_ARGS.value),                                       # нет product_id  в data
        ('any@m.ru', 'TO_UPD', False, 'product_id', 'qwe', 'rating', 4, None, None,
         400, Error.PRODUCT_ID_WRONG_TYPE.value),                                   # некорректный id товара
        ('any@m.ru', 'TO_UPD', False, 'product_id', 1, 'rating', 'qw', None, None,
         400, Error.RATING_WRONG_TYPE_OR_VALUE.value),                              # некорректный rating товара
        ('any@m.ru', 'TO_UPD', False, 'product_id', 1, 'rating', '4', None, None,
         400, Error.BUYER_ONLY.value),                                              # не покупал товар
        ('any@m.ru', 'TO_UPD', True, 'product_id', 1, 'rating', '4', None, None,
         201, None),                                                                # ОК, без отзыва
        ('any@m.ru', 'TO_UPD', True, 'product_id', 1, 'rating', '5', 'review', 'Огонь',
         201, None),                                                                # ОК, с отзывом
    )
)
def test_rate_product(client_pytest, email, test_token, is_buyer, arg_1, value_1, arg_2, value_2, arg_3, value_3,
                      exp_res, exp_error_text):
    """Проверяем выставление оценки и отправку отзыва покупателем на товар, корректность отображения response и
    детализации ошибок, отображение выставленной оценки в детализации товара"""

    # создаем пользователя и auth-token для него
    user = User.objects.create_user(email=email, is_active=True)
    auth_token = Token.objects.create(user=user)

    goods = make_productinfo(5)

    # если покупатель, создаем пользователю заказ с оцениваемым продуктом
    if is_buyer:
        order = baker.make(Order, user=user)
        value_1 = goods[0].id
        baker.make(OrderItem, product_info_id=value_1, order=order)

    # определяем токен для headers в запросе
    user_token = None
    if test_token == 'TO_UPD':
        user_token = auth_token.key
    elif test_token == 'random_token':
        user_token = test_token
    elif test_token is None:
        pass

    # устанавливаем токен в headers
    if user_token:
        client_pytest.credentials(HTTP_AUTHORIZATION=f'Token {user_token}')

    # определяем data для запроса и отправляем запрос
    post_data_1 = {}
    post_data_2 = {}
    post_data_3 = {}
    if arg_1:
        post_data_1 = {arg_1: value_1}
    if arg_2:
        post_data_2 = {arg_2: value_2}
    if arg_3:
        post_data_3 = {arg_3: value_3}
    post_data = {**post_data_1, **post_data_2, **post_data_3}

    res = client_pytest.post(reverse('rate_product'), data=post_data)
    data = res.json()

    assert res.status_code == exp_res

    if res.status_code != 201:
        assert data == exp_error_text
    else:
        assert data == {'Status': 'Success', 'Добавлена оценка': {'buyer': ' ', 'rating': f'{value_2}',
                                                                  'review': value_3}}
        # проверяем, что выставленная оценка отобразилась в описании товара
        res_2 = client_pytest.get(reverse('product_detail', args=[value_1]))
        data_2 = res_2.json()
        assert data_2['ratings'][0]['rating'] == value_2


# noinspection PyUnresolvedReferences
@pytest.mark.django_db
@pytest.mark.parametrize(
    ['email', 'arg_1', 'value_1', 'arg_2', 'value_2', 'arg_3', 'value_3', 'exp_res_1', 'exp_res_2', 'exp_error_text',
     'exp_total_rating', 'check'],
    (
        ('any@m.ru', 'product_id', 1, 'rating', '4', 'rating', '5', 201, 201,
         None, 4.5, 'sum'),                                                     # Все ОК-1
        ('any@m.ru', 'product_id', 1, 'rating', '5', 'rating', '1', 201, 400,
         Error.RATING_DUPLICATE.value, None, 'duplicate'),                      # Дубликат оценки клиентом
        ('any@m.ru', 'product_id', 1, 'rating', '1', 'rating', '5', 201, 201,
         None, 3, 'sum'),                                                       # Все ОК-2
    )
)
def test_rate_product_sum(client_pytest, email, arg_1, value_1, arg_2, value_2, arg_3, value_3, exp_res_1, exp_res_2,
                          exp_error_text, exp_total_rating, check):
    """Проверяем многократную оценку: запрет повторной оценки тем же пользователем + корректная детализация ошибки
    в response, корректный расчет средней оценки при ее отображении в детализации товара"""

    # создаем 1-го пользователя и auth-token для него
    user = User.objects.create_user(email=email, is_active=True)
    auth_token = Token.objects.create(user=user)
    user_token = auth_token.key

    # создаем пользователю заказ с оцениваемым продуктом
    goods = make_productinfo(5)
    order = baker.make(Order, user=user)
    value_1 = goods[0].id
    baker.make(OrderItem, product_info_id=value_1, order=order)

    # определяем data для запроса и отправляем запрос
    post_data = {arg_1: value_1, arg_2: value_2}
    client_pytest.credentials(HTTP_AUTHORIZATION=f'Token {user_token}')
    res = client_pytest.post(reverse('rate_product'), data=post_data)
    assert res.status_code == exp_res_1

    # Проверяем, что нельзя повторно оставить оценку на товар
    if check == 'duplicate':
        post_data = {arg_1: value_1, arg_3: value_3}
        res = client_pytest.post(reverse('rate_product'), data=post_data)
        data = res.json()

        assert res.status_code == exp_res_2
        assert data == exp_error_text

    # Проверяем, что рейтинг товара рассчитывается корректно при отправке второй оценки
    elif check == 'sum':
        # создаем 2-го пользователя, токен и заказ с товаром
        user = User.objects.create_user(email='new@m.ru', is_active=True)
        auth_token = Token.objects.create(user=user)
        user_token = auth_token.key
        order = baker.make(Order, user=user)
        value_1 = goods[0].id
        baker.make(OrderItem, product_info_id=value_1, order=order)

        # определяем data для запроса и отправляем запрос
        post_data = {arg_1: value_1, arg_3: value_3}
        client_pytest.credentials(HTTP_AUTHORIZATION=f'Token {user_token}')
        res = client_pytest.post(reverse('rate_product'), data=post_data)
        data = res.json()

        assert res.status_code == exp_res_2
        assert data['Добавлена оценка']['rating'] == value_3

        # проверяем, что выставленные оценки корректно просуммировались в детализации товара
        res_2 = client_pytest.get(reverse('product_detail', args=[value_1]))
        data_2 = res_2.json()

        assert data_2['total_rating'] == exp_total_rating
