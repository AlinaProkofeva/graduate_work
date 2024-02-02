import os

from django.forms import ModelForm, BaseInlineFormSet, TextInput
from django.core.exceptions import ValidationError

from backend.models import User, Order, ProductInfoPhoto
from backend.utils.error_text import ValidateError as Error
from shop_site import settings


# noinspection PyUnresolvedReferences
class ShopForm(ModelForm):
    """
    Переопределяем метод clean при создании магазина.

    Проверяем, что у менеджера магазина user.type == 'shop', пользователь активен и не привязан к другому магазину
    """

    def clean(self):
        """
        Проверка, что у менеджера магазина user.type == 'shop', пользователь активен и не привязан к другому магазину
        """
        if self.cleaned_data['user']:
            if self.cleaned_data['user'].type != 'shop':
                raise ValidationError(Error.USER_WRONG_TYPE.value)

            if not self.cleaned_data['user'].is_active:
                raise ValidationError(Error.USER_INACTIVE.value)

            try:
                if self.cleaned_data['user'].shop:
                    # доп проверка, что это не тот же магазин при редактировании
                    if self.cleaned_data['user'].shop.name != self.cleaned_data['name']:
                        raise ValidationError(Error.USER_HAS_ANOTHER_SHOP.value)
            except User.shop.RelatedObjectDoesNotExist:
                pass

        return self.cleaned_data


class OrderItemInLineFormset(BaseInlineFormSet):
    """
    Переопределяем метод clean при создании заказа.

    Настраиваем запрет на добавление в один заказ товаров из разных магазинов.
    """

    def clean(self):
        """
        Настраиваем запрет на добавление в один заказ товаров из разных магазинов
        """
        shop = None
        for form in self.forms:
            one_row = form.cleaned_data
            if not shop:
                # на первой итерации устанавливаем магазин
                shop = one_row.get('product_info').shop.name
            else:
                try:
                    shop_other_row = one_row.get('product_info').shop.name
                    # на остальных итерациях сравниваем магазин
                    if shop_other_row != shop:
                        raise ValidationError(Error.DIFFERENT_SHOPS.value)
                except AttributeError:  # обрабатываем пустое поле
                    pass

        return super().clean()


class OrderForm(ModelForm):
    """
    Переопределяем метод clean при создании/редактировании заказа.

    Настраиваем запрет на наличие у одного пользователя более чем одной корзины, сохранение пустой корзины +
    проверяем, чтобы контакт доставки принадлежал пользователю, были указаны корректная дата + время доставки,
    ФИО получателя.
    """

    def clean(self):
        """
        Настраиваем запрет на наличие у одного пользователя более чем одной корзины, сохранение пустой корзины +
        проверяем, чтобы контакт доставки принадлежал пользователю, были указаны корректная дата + время доставки,
        ФИО получателя.
        """

        if self.cleaned_data['state'] == 'basket':
            user = self.cleaned_data['user']

            # проверяем, есть ли уже у пользователя корзина с id заказа
            has_basket = user.orders.filter(state='basket')
            if has_basket:
                # id существующей корзины не совпадает с id корзины, которую мы сейчас сохраняем? --> Ошибка
                # Это позволит редактировать первую корзину без проблем, но не даст сохранить вторую
                if self.data['ordered_items-__prefix__-order'] == '' or \
                        has_basket.first().id != int(self.data['ordered_items-__prefix__-order']):
                    raise ValidationError(Error.DUPLICATE_BASKET.value)

        # ограничения для заказов НЕ в статусе 'корзина'
        else:
            # запрет на контакт другого пользователя и None для отправленных заказов
            if self.cleaned_data['contact'] not in self.cleaned_data['user'].contacts.addresses.all():
                raise ValidationError(Error.ANOTHER_USER_CONTACT.value)

            # запрет на отсутствие даты доставки для отправленных заказов
            if not self.cleaned_data['delivery_date']:
                raise ValidationError(Error.DELIVERY_DATE_WRONG.value)

            # запрет на отсутствие времени доставки для отправленных заказов
            if not self.cleaned_data['delivery_time']:
                raise ValidationError(Error.DELIVERY_TIME_WRONG.value)

            # запрет на отсутствие ФИО получателя для отправленных заказов
            if not self.cleaned_data['recipient_full_name']:
                raise ValidationError(Error.RECIPIENT_IS_EMPTY.value)

        # ограничения для заказов с ЛЮБЫМ статусом
        # ставим запрет на сохранение пустого заказа при создании или при удалении товаров
        if self.data['ordered_items-TOTAL_FORMS'] == '0':
            raise ValidationError(Error.ORDER_IS_EMPTY.value)

        goods_in_order = int(self.data['ordered_items-TOTAL_FORMS'])
        delete_mark_counter = 0
        for value in range(goods_in_order):
            if self.data.get(f'ordered_items-{value}-DELETE') == 'on':
                delete_mark_counter += 1
        if goods_in_order == delete_mark_counter:
            raise ValidationError(Error.ORDER_IS_EMPTY.value)

        return self.cleaned_data


class UserForm(ModelForm):
    """
    Переопределяем метод clean при создании/редактировании пользователя.

    Добавляем проверку уникальности email, указания имени и фамилии, запрет дублей аватара.
    """

    def clean(self):
        """
        Проверка уникальности email, указания имени и фамилии, запрет дублей аватара.
        """
        user_with_the_specified_email = User.objects.filter(email=self.cleaned_data['email'])

        # контроль удаления старого аватара при замене, кроме дефолта
        avatar_new = str(self.cleaned_data.get('avatar_thumbnail'))
        current_avatar = str(user_with_the_specified_email.first().avatar_thumbnail)
        if current_avatar != avatar_new:
            if current_avatar != 'ava_thumbnails/default.jpg':
                filepath = os.path.join(settings.MEDIA_ROOT, current_avatar.split('/')[0], current_avatar.split('/')[1])
                os.remove(filepath)  # если смена аватара, удаляем из базы старое фото, кроме дефолтного

        # при создании нового пользователя проверяем уникальность email
        if self.instance.id is None:
            if user_with_the_specified_email.exists():
                raise ValidationError(Error.EMAIL_NOT_UNIQUE.value)
        else:
            # защита права на редактирование записи
            # защита, чтобы при редактировании нельзя было задублировать email
            if user_with_the_specified_email.exists():
                if self.instance.id != user_with_the_specified_email.first().id:
                    raise ValidationError(Error.EMAIL_NOT_UNIQUE.value)

        # проверяем указание имени и фамилии
        if not self.cleaned_data['first_name'] or not self.cleaned_data['last_name']:
            raise ValidationError(Error.NAME_REQUIRED.value)

        return self.cleaned_data


class ContactForm(ModelForm):
    """
    Переопределяем метод clean при создании/редактировании контакта.

    У пользователя может быть одновременно не более 5 записей контактов.
    """

    def clean(self):
        """
        У пользователя может быть одновременно не более 5 записей контактных адресов.
        """
        if int(self.data.get('addresses-TOTAL_FORMS')) > 5:
            raise ValidationError(Error.CONTACTS_EXCEEDING.value)
        return self.cleaned_data


class AddressForm(ModelForm):
    """Переопределение ширины столбцов в инлайне с адресами контактов"""
    class Meta:
        widgets = {
            'region': TextInput(attrs={'size': 20}),
            'district': TextInput(attrs={'size': 20}),
            'settlement': TextInput(attrs={'size': 20}),
            'street': TextInput(attrs={'size': 20}),
            'house': TextInput(attrs={'size': 5}),
            'structure': TextInput(attrs={'size': 5}),
            'building': TextInput(attrs={'size': 5}),
            'apartment': TextInput(attrs={'size': 5})
        }


# noinspection PyUnresolvedReferences
class RatingForm(ModelForm):
    """
    Переопределяем метод clean при создании/редактировании формы рейтинга.

    Оставлять оценку и отзыв может только клиент, приобретавший товар
    """

    def clean(self):
        """
        Оставлять оценку и отзыв может только клиент, приобретавший товар
        """
        is_buyer = Order.objects.exclude(state='basket').\
            filter(user=self.cleaned_data['user'], ordered_items__product_info=self.cleaned_data['product'])

        if not is_buyer:
            raise ValidationError(Error.USER_NOT_BUYER.value)
        return self.cleaned_data


class ProductPhotoInLineFormset(BaseInlineFormSet):
    """Настройка строго 1 основной иконки товара при наличии изображений, удаления изображения из медиа при удалении
    строки"""
    def clean(self):
        """Настройка строго 1 основной иконки товара при наличии изображений, удаления изображения из медиа при
        удалении строки"""

        if int(self.data['photos-TOTAL_FORMS']) > 0 :
            counter = 0
            for form in self.forms:
                one_row = form.cleaned_data
                if one_row['is_main']:
                    counter += 1

            if not counter:
                raise ValidationError(Error.ICON_IS_EMPTY.value)
            elif counter > 1:
                raise ValidationError(Error.ICON_EXCEEDING.value)

        # удаляем из базы старое фото при отметке удаления строки в админке
        for i in self.data:
            if 'photos' and 'DELETE' in i:  # 'photos-1-DELETE': ['on'], 'photos-1-id': ['67']
                for_delete = ProductInfoPhoto.objects.get(id=self.data[f'photos-{i.split("-")[1]}-id']).photo.url
                for_delete = for_delete.split('/')
                filepath = os.path.join(settings.MEDIA_ROOT, for_delete[2], for_delete[3], for_delete[4])
                os.remove(filepath)

        return super().clean()
