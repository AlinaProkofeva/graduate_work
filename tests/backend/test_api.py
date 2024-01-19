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
            ('Связной', 2, 'Евросеть', 2),
    )
)
@pytest.mark.django_db
def test_productinfo_get(client_pytest, shop_1, quantity_1, shop_2, quantity_2):
    """Проверяем, что get отображает все товары во всех магазинах"""

    make_productinfo(shop_1, quantity_1)
    make_productinfo(shop_2, quantity_2)

    res = client_pytest.get(reverse('products'))
    assert res.status_code == 200

    data = res.json()
    assert len(data) == quantity_1 + quantity_2
