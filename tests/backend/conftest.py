import pytest
from rest_framework.test import APIClient
from model_bakery import baker

from backend.models import Category, Product, Shop, ProductInfo


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


def make_productinfo(shop_name: str, quantity: int) -> list:
    """Генерация товаров в магазине по заданному названию магазина и количеству товаров"""
    shop = baker.make(Shop, shop__name=shop_name)
    category = baker.make(Category)
    product = baker.make(Product, category=category)
    goods = baker.make(ProductInfo, product=product, shop=shop, external_id=baker.seq(1), _quantity=quantity)
    return goods
