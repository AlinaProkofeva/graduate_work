import random

import pytest
from django.urls import reverse

from backend.models import Shop
from tests.backend.conftest import make_productinfo


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

    goods_1 = make_productinfo(quantity_1, shop_1)
    goods_2 = make_productinfo(quantity_2, shop_2)

    for i in goods_1:
        print('---', i.id, i.shop.name, i.shop.id)

    for i in goods_2:
        print('+++', i.id, i.shop.name, i.shop.id)

    res = client_pytest.get(reverse('products'))
    data = res.json()
    assert res.status_code == 200

    assert len(data) == quantity_1 + quantity_2

    print('***', data)


@pytest.mark.parametrize(
    ['shop_1', 'quantity_1', 'shop_2', 'quantity_2'],
    (
            ('Связной', 2, 'Евросеть', 3),
    )
)
@pytest.mark.django_db
def test_productinfo_get(client_pytest, shop_1, quantity_1, shop_2, quantity_2):
    """Проверяем, что get отображает все товары во всех магазинах"""

    goods_1 = make_productinfo(quantity_1, shop_1)
    goods_2 = make_productinfo(quantity_2, shop_2)

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
    goods_2 = make_productinfo(quantity_2, shop_2, **add_opt_2)

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
def test_productinfo_get_search_filter(client_pytest, shop_1, quantity_1, filter_name, filter_value,
                                 exp_res, model, prod_name, param):
    """Проверяем, что get корректно отображает заданные search-фильтры"""

    goods_1 = make_productinfo(quantity_1, shop_name=shop_1, model=model, prod_name=prod_name, param=param)
    make_productinfo(random.randint(1, 5))
    make_productinfo(random.randint(1, 5))

    res = client_pytest.get(reverse('products'), {filter_name: filter_value})
    data = res.json()

    assert len(data) == exp_res
