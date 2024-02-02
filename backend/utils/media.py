# переменные и вспомогательные функции для работы с изображениями

import uuid
from django.template.defaultfilters import slugify as django_slugify


def slugify(s):
    """Для корректной слагификации кириллицы - pytils не работает с 3.11, поэтому так"""

    alphabet = {'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo', 'ж': 'zh', 'з': 'z', 'и': 'i',
                'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't',
                'у': 'u', 'ф': 'f', 'х': 'kh', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch', 'ы': 'i', 'э': 'e',
                'ю': 'yu', 'я': 'ya'}
    return django_slugify(''.join(alphabet.get(w, w) for w in s.lower()))


def upload_ava_thumbnail_location(instance, filename: str) -> str:
    """Определение пути для сохранения миниатюры аватарки пользователя по имени почты пользователя.
    Для удобства навигации и логики

    :param instance: объект модели User
    :param filename: наименование файла с аватаркой
    """

    extension = filename.split('.')[-1]
    name = instance.email.split("@")[0] + '_' + instance.email.split("@")[1].split(".")[0]
    return f'ava_thumbnails/{name}.{extension}'


def upload_icon_location(instance, filename: str) -> str:
    """Определение пути для сохранения изображений к товарам для удобной и логичной навигации

    :param instance: объект модели ProductInfoPhoto
    :param filename: наименование файла с изображением товара"""

    extension = filename.split('.')[-1]
    new_filename = slugify(instance.product.product.name) + '_' + slugify(instance.product.shop.name)

    return f'images/{new_filename}/{uuid.uuid4()}.{extension}'


# заглушка вывода основного изображения товара, путь
default_photo_large = '/media/images/phone_default_large.png'

# заглушка вывода иконки с изображением, путь
default_photo_icon = '/media/images/phone_default_icon.jpg'

# допустимые форматы изображений
image_extensions = ('jpg', 'jpeg', 'png', 'gif', 'raw', 'svg', 'bmp', 'ico', 'tiff', 'webp')
