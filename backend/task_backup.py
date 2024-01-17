from celery import shared_task

from backend.models import User, ProductInfo
from backend.signals import backup_shop


# noinspection PyUnresolvedReferences
@shared_task
def backup_shop_base(shop_name: str) -> None:
    """
    Таск для создания yaml-файла с полными остатками магазина

    :param shop_name: название магазина для формирования файла с остатками
    """
    user = User.objects.get(shop__name=shop_name)
    all_goods_in_shop = ProductInfo.objects.filter(shop=user.shop)
    cats = all_goods_in_shop.first().shop.categories.all()

    # делаем бэкап базы магазина
    with open(f'{shop_name}.yaml', 'w', encoding='utf-8') as f:
        f.write(f'shop: {shop_name}\n\n')  # записываем название магазина
        if cats:
            f.write(f'categories:\n')
            for i in cats:  # записываем категории
                f.write(f'  - id: {i.id}\n')
                f.write(f'    name: {i.name}\n')
            f.write('\n')
        if all_goods_in_shop:
            f.write('goods:\n')
            for i in all_goods_in_shop:  # записываем товары
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

    backup_shop.send(sender=User, user_id=user.id)
