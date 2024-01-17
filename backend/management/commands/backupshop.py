from django.core.management.base import BaseCommand
from backend.models import ProductInfo


class Command(BaseCommand):
    """
    Команда для создания бэкапа. Экспорт в yaml-файл всех остатков магазина.
    """

    def add_arguments(self, parser):
        parser.add_argument('shop_id', nargs='+', type=int)

    def handle(self, *args, **options):  # python manage.py testing <shop_id: int>
        all_goods_in_shop = None
        shop_name = None
        cats = None

        if options['shop_id']:
            for i in options['shop_id']:
                all_goods_in_shop = ProductInfo.objects.filter(shop_id=i)   # все товары в магазине
            shop_name = all_goods_in_shop.first().shop.name                 # название магазина
            cats = all_goods_in_shop.first().shop.categories.all()          # категории магазина

        with open(f'{shop_name}.yaml', 'w', encoding='utf-8') as f:
            f.write(f'shop: {shop_name}\n\n')           # записываем название магазина
            if cats:
                f.write(f'categories:\n')
                for i in cats:                          # записываем категории
                    f.write(f'  - id: {i.id}\n')
                    f.write(f'    name: {i.name}\n')
                f.write('\n')
            if all_goods_in_shop:
                f.write('goods:\n')
                for i in all_goods_in_shop:             # записываем товары
                    f.write(f'  - id: {i.external_id}\n')
                    f.write(f'    category: {i.product.category.id}\n')
                    f.write(f'    model: {i.model}\n')
                    f.write(f'    name: {i.product.name}\n')
                    f.write(f'    price: {i.price}\n')
                    f.write(f'    price_rrc: {i.price_rrc}\n')
                    f.write(f'    quantity: {i.quantity}\n')
                    f.write(f'    description: {i.description}\n')
                    f.write(f'    parameters:\n')
                    params = i.product_parameters.all()
                    if params:
                        for param in params:
                            f.write(f'      "{param.parameter.name}": {param.value}\n')
