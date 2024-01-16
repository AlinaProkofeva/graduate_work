from celery.result import AsyncResult
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.db import IntegrityError

from backend.models import Category, Shop, Product, ProductInfo, Parameter, ProductParameter
from shop_site.celery import app


# Параметры товара в yaml-файле, имеющие простую структуру и переносимые в словарь по одной логике
simple_in_structure = {
    '- id:': 'id',
    'category:': 'category',
    'model:': 'model',
    'name:': 'name',
    'price:': 'price',
    'price_rrc:': 'price_rrc',
    'quantity:': 'quantity'
}


def get_data_from_yaml_file(file: InMemoryUploadedFile) -> dict:
    """
    Получение данных из yaml-файла и возврат их в формате dict

    :param file: файл-вложение из запроса в формате .yaml
    :return: data_from_yaml_file - словарь данных из yaml-файла
    """
    data_from_yaml_file = {}
    exit_ind = None  # индекс для смещения читаемой строки при многострочном description

    raw_data = [i.decode('utf-8').strip() for i in file.readlines()]
    raw_data = [i for i in raw_data if len(i) > 0]
    raw_data = [i for i in raw_data if '#' != i[0]]

    for row in raw_data:
        if 'shop:' in row:
            data_from_yaml_file['shop'] = row.split(':')[1].strip()

    for ind, row in enumerate(raw_data):
        if 'categories:' in row:
            cat_list = []
            data_from_yaml_file['categories'] = cat_list
            cat_dict = {}
            for ind_ in range(ind + 1, len(raw_data)):
                if '- id:' in raw_data[ind_]:
                    cat_dict.update(id=int(raw_data[ind_].split(':')[1].strip()))
                elif 'name:' in raw_data[ind_]:
                    cat_dict.update(name=raw_data[ind_].split(':')[1].strip())
                    cat_list.append(cat_dict.copy())
                    cat_dict.clear()
                else:
                    break
        elif 'goods:' in row:
            goods_list = []
            data_from_yaml_file['goods'] = goods_list
            good_dict = {}
            for ind_ in range(ind + 1, len(raw_data)):

                # заполняем данные с простой логикой
                for key, value_ in simple_in_structure.items():
                    if key in raw_data[ind_]:
                        val = raw_data[ind_].split(':')[1].strip()
                        if val.isdigit():
                            val = int(val)
                        good_dict[value_] = val
                    else:
                        continue

                if 'description:' in raw_data[ind_]:
                    description = ''
                    for ind_1 in range(ind_, len(raw_data)):
                        if raw_data[ind_1].split()[0] == 'description:':
                            raw_data[ind_1].split(':')
                            description += raw_data[ind_1].split(':')[1].strip()
                        elif ':' in raw_data[ind_1].split()[0]:
                            good_dict.update(description=description)
                            exit_ind = ind_1
                            break
                        else:
                            description = description + ' ' + raw_data[ind_1]

                elif 'parameters:' in raw_data[ind_]:
                    param_dict = {}
                    good_dict.update(parameters=param_dict)
                    for ind_1 in range(exit_ind + 1, len(raw_data)):
                        if '- id:' not in raw_data[ind_1]:
                            value = raw_data[ind_1].split(':')[1].strip()
                            value = int(value) if value.isdigit() else str(value)
                            param_dict[raw_data[ind_1].split(':')[0].strip('""')] = value
                        else:
                            break
                    goods_list.append(good_dict.copy())
                    good_dict.clear()

                else:
                    continue

    return data_from_yaml_file


# noinspection PyUnresolvedReferences
def create_categories(new_categories: list[dict], shop: Shop, category_failed: int, errors_list: list, errors: dict) ->\
        None | tuple:
    """
    Создание новых категорий в БД на основе данных из yaml-файла

    :param new_categories: список словарей с данными новых категорий
    :param shop: объект Shop, остатками которого идет управление
    :param category_failed: счетчик не созданных вследствие ошибки категорий
    :param errors_list: список всех ошибок
    :param errors: итоговый словарь со списком ошибок, передаваемый в Response
    :return: category_failed, errors_list, errors - информация об ошибках при создании категорий
    """
    for cat in new_categories:
        try:
            # запрещено изменять/удалять, чтобы не влиять на остатки других магазинов-партнеров!!!
            category, _ = Category.objects.get_or_create(id=cat['id'], name=cat['name'])
            category, _ = Category.objects.get_or_create(id=cat['id'], name=cat['name'])
            category.shops.add(shop.id)
        except IntegrityError as e:
            category_failed += 1
            category_errors_dict = {}
            category_errors_dict['category_creation_failed'] = (cat['id'], cat['name'], str(e))
            errors_list.append(category_errors_dict)
            errors['Errors'] = errors_list
            errors['Не удалось создать категорий'] = category_failed
            continue

    return category_failed, errors_list, errors


# noinspection PyUnresolvedReferences
def get_or_greate_product_object(good: dict, errors_list: list, errors: dict) -> tuple:
    """
    Создание или получение Продукта на основе данных из yaml-файла

    :param good: словарь с данными нового товара
    :param errors_list: список всех ошибок
    :param errors: итоговый словарь со списком ошибок, передаваемый в Response
    :return: product, shop_product_failed, errors_list, errors - созданный/полученный продукт + информация об ошибках
    при создании
    """
    product = None

    # Находим FK продукта в базе, при отсутствии создаем продукт
    try:
        product, _ = Product.objects.get_or_create(name=good['name'], category_id=good['category'])
    except IntegrityError as e:
        # продукт на остатках не получится создать при ошибке создания Product
        product_info_errors_dict = {}
        product_info_errors_dict['product_info_creation_failed'] = (good['id'], good['name'], str(e))
        errors_list.append(product_info_errors_dict)
        errors['Errors'] = errors_list

    return product, errors_list, errors


# noinspection PyUnresolvedReferences
def update_or_create_product_info(good: dict, product: Product, shop: Shop, quantity: int, counter: int,
                                  errors_list: list, errors: dict) -> tuple:
    """
    Создание новой записи о товаре на складе или изменение данных товара на складе

    :param good: словарь с данными нового товара
    :param product: продукт из таблицы Product
    :param shop: объект Shop, остатками которого идет управление
    :param quantity: итоговое количество товара для установления на остатки
    :param counter: счетчик успешных обновлений данных/созданий товаров
    :param errors_list: список всех ошибок
    :param errors: итоговый словарь со списком ошибок, передаваемый в Response
    :return: shop_product, counter, shop_product_failed, errors_list, errors - запись в таблице остатков ProductInfo,
    счетчик успешных обновлений данных/созданий товаров, информация об ошибках при создании
    """
    shop_product = None
    try:
        shop_product, _ = ProductInfo.objects.update_or_create(
            product=product, shop=shop, external_id=good['id'], defaults={
                'model': good['model'],
                'quantity': quantity,  # переменная, т.к. разные данные при POST/PATCH
                'price': good['price'],
                'price_rrc': good['price_rrc'],
                'description': good['description']
            })
        if shop_product:
            counter += 1
    except IntegrityError as e:
        product_info_errors_dict = {}
        product_info_errors_dict['product_info_creation_failed'] = (good['id'], good['name'], str(e))
        errors_list.append(product_info_errors_dict)
        errors['Errors'] = errors_list

    return shop_product, counter, errors_list, errors


# noinspection PyUnresolvedReferences
def create_parameter_for_product(parameters: dict, shop_product: ProductInfo) -> None:
    """
    Заполнение характеристик при создании/обновлении товара на остатках магазина

    :param parameters: словарь с параметрами товара
    :param shop_product: товар, запись в таблице остатков ProductInfo
    :return: None
    """

    # Проверяем, существует ли параметр в базе, если нет - создаем
    for parameter_name, parameter_value in parameters.items():
        parameter, _ = Parameter.objects.get_or_create(name=parameter_name)

        # и на каждой итерации заполняем промежуточную таблицу, обновляем/добавляем характеристики продукта
        ProductParameter.objects.update_or_create(
            product=shop_product,
            parameter=parameter,
            defaults={
                'value': parameter_value
            }
        )


def get_data_from_all_tasks(all_tasks: list[str], counter: int, shop_product_failed: int, errors: dict) -> tuple:
    """
    Функция принимает список id task-задач в селери, проверяет их исполнение, при исполнении забирает из task данные

    :param all_tasks: список с id task-задач
    :param counter: счетчик успешных загрузок
    :param shop_product_failed: счетчик ошибок при загрузках
    :param errors: словарь с детализацией ошибок
    :return: counter, shop_product_failed, errors - счетчик успешных загрузок, счетчик ошибок + детализация ошибок
    """
    while len(all_tasks) > 0:
        for task in all_tasks:
            res = AsyncResult(task, app=app)

            if res.state == 'SUCCESS':  # если task выполнена, забираем результат
                counter_t, errors_t = res.get()
                counter += counter_t

                if errors_t:  # если произошли ошибки при загрузке товара
                    shop_product_failed += 1
                    if 'Errors' not in errors:
                        errors['Errors'] = []
                    errors['Errors'].append(errors_t['Errors'][0])
                    errors['Не удалось добавить товаров на остатки/обновить'] = shop_product_failed
                all_tasks.remove(task)  # удаляем id из списка обрабатываемых task
            else:
                continue

    return counter, shop_product_failed, errors
