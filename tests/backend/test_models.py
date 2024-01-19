import pytest
from django.db import transaction, IntegrityError
from django.urls import reverse
from model_bakery import baker

from backend.models import Shop, Category, Product, ProductInfo


# noinspection PyUnresolvedReferences
@pytest.mark.django_db
@pytest.mark.parametrize(
    ['name', 'url', 'state', 'exp_code', 'length'],
    (
            ('Евросеть', 'http://ev.ru', True, 200, 1),
    )
)
def test_not_duplicate_shop(client_pytest, name, url, state, exp_code, length):
    """Проверяем, что не дает создать неуникальное название магазина"""
    check = False
    Shop.objects.create(name=name, url=url, state=state)
    try:
        with transaction.atomic():
            Shop.objects.create(name=name, url=url, state=state)
    except IntegrityError:
        check = True
    assert check is True
    res = client_pytest.get(reverse('shops'))
    data = res.json()
    assert length == len(data)


# noinspection PyUnresolvedReferences
@pytest.mark.django_db
@pytest.mark.parametrize(
    ['name', 'exp_code', 'length'],
    (
        ('Смартфон', 200, 1),
    )
)
def test_not_duplicate_categories(client_pytest, name, exp_code, length):
    """Проверяем, что не дает создать неуникальное название категории"""
    check = False
    Category.objects.create(name=name)
    try:
        with transaction.atomic():
            Category.objects.create(name=name)
    except IntegrityError:
        check = True
    assert check is True
    res = client_pytest.get(reverse('categories'))
    data = res.json()
    assert length == len(data)
    if len(data) > 0:
        assert data[0]['name'] == name


@pytest.mark.django_db
@pytest.mark.parametrize(
    ['name'],
    (
        ('Смартфон Samsung EDGE', ),
    )
)
def test_not_duplicate_product(make_category, name):
    """Проверяем, что не дает создать неуникальное название+категорию Продукта"""
    check = False
    baker.make(Product, name=name, category=make_category)
    try:
        with transaction.atomic():
            baker.make(Product, name=name, category=make_category)
    except IntegrityError:
        check = True
    assert check is True


@pytest.mark.django_db
@pytest.mark.parametrize(
    ['shop', 'external_id'],
    (
        ('Связной', 92388),
    )
)
def test_not_duplicate_productinfo(make_product, shop, external_id):
    """Проверяем, что не дает создать в магазине неуникальный артикул товара"""
    check = False
    baker.make(ProductInfo, shop__name=shop, external_id=external_id, product=make_product)
    try:
        with transaction.atomic():
            baker.make(ProductInfo, shop__name=shop, external_id=external_id, product=make_product)
    except IntegrityError:
        check = True
    assert check is True


@pytest.mark.parametrize(
    ['quantity', 'external_id', 'price', 'price_rrc', 'correctness'],
    (
        (1, 92388, 10990, 11990, 'correct'),
        (-1, 92388, 10990, 11990, 'wrong'),         # неверное количество
        (1, '92388qqq', 10990, 11990, 'wrong'),     # неверный артикул
        (1, 92388, -10990, 11990, 'wrong'),         # неверная цена
        (1, 92388, 'errrre', 11990, 'wrong'),       # неверная цена
        (1, 92388, 10990, -11990, 'wrong'),         # неверная цена rrc
        (1, 92388, 10990, 'errrre', 'wrong'),       # неверная цена rrc
    )
)
@pytest.mark.django_db
def test_productinfo(make_product, make_shop, quantity, external_id, price, price_rrc, correctness):
    """Проверяем создание товаров на складах с корректными и некорректными параметрами"""
    check = False
    if correctness == 'correct':
        prod = baker.make(ProductInfo, product=make_product, shop=make_shop, quantity=quantity,
                          external_id=external_id, price=price, price_rrc=price_rrc)
        if prod:
            check = True
    else:
        try:
            with transaction.atomic():
                baker.make(ProductInfo, product=make_product, shop=make_shop, quantity=quantity,
                           external_id=external_id, price=price, price_rrc=price_rrc)
        except (IntegrityError, ValueError):
            check = True

    assert check is True
