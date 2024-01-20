import random

import pytest
from rest_framework.test import APIClient
from model_bakery import baker

from backend.models import Category, Product, Shop, ProductInfo, Parameter, ProductParameter


# @pytest.fixture
# def start():
#     print('Начало тестирования!')
#     yield
#     print('Конец теста!')


@pytest.fixture
def client_pytest():
    return APIClient()


@pytest.fixture()
def make_category():
    """Создание категории"""
    return baker.make(Category)


@pytest.fixture()
def make_product():
    """Создание продукта"""
    category = baker.make(Category)
    return baker.make(Product, category=category)


@pytest.fixture()
def make_shop():
    """Создание магазина"""
    return baker.make(Shop)


def make_productinfo(quantity: int, shop_name: str = None, price_start: int = None, price_max: int = None,
                     category_name: str = None, model: str = None, prod_name: str = None, param: str = None) -> list:
    """Генерация товаров в магазине по заданным критериям"""

    if shop_name:
        shop = baker.make(Shop, name=shop_name)
    else:
        shop = baker.make(Shop)

    if category_name:
        category = baker.make(Category, name=category_name)
    else:
        category = baker.make(Category)

    if prod_name:
        product = baker.make(Product, category=category, name=prod_name)
    else:
        product = baker.make(Product, category=category)

    if price_start and price_max:
        goods = baker.make(ProductInfo, product=product, shop=shop, external_id=baker.seq(1),
                           price=random.randint(price_start, price_max), _quantity=quantity)
    elif model:
        goods = baker.make(ProductInfo, product=product, shop=shop, external_id=baker.seq(1), _quantity=quantity,
                           model=model)
    else:
        goods = baker.make(ProductInfo, product=product, shop=shop, external_id=baker.seq(1), _quantity=quantity)

    if param:
        parameter = baker.make(Parameter, name=param)
        for i in goods:
            baker.make(ProductParameter, product=i, parameter=parameter)

    return goods
