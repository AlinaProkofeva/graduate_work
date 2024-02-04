import re
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from backend.models import Order, Product, ProductParameter, Shop, ProductInfo, OrderItem, Category, Contact, User, \
    Address, RatingProduct, ProductInfoPhoto
from backend.utils import reg_patterns
from .utils.error_text import ValidateError as Error
from .utils import media


class AddressSerializer(serializers.ModelSerializer):
    """Адрес в контакте"""

    class Meta:
        model = Address
        fields = ['id', 'region', 'district', 'settlement', 'street', 'house', 'structure', 'building', 'apartment']

    def validate(self, attrs):
        # условия if добавлены, чтобы срабатывать при patch-запросах

        # валидация названия города
        if attrs.get('region'):
            validated_city = re.search(reg_patterns.re_city_street, attrs['region'])
            if not validated_city:
                raise ValidationError(Error.CITY_IS_INCORRECT.value)

        # валидация названия улицы
        if attrs.get('street'):
            validated_street = re.search(reg_patterns.re_city_street, attrs['street'])
            if not validated_street:
                raise ValidationError(Error.STREET_IS_INCORRECT.value)

        return attrs


class ContactSerializer(serializers.ModelSerializer):
    """Работа с контактами клиента"""

    # user = serializers.StringRelatedField(read_only=True)
    addresses = AddressSerializer(many=True, read_only=True)

    class Meta:
        model = Contact
        fields = ['phone', 'addresses']
        read_only_field = ['user', 'id']

    def validate(self, attrs):

        # условия if добавлены, чтобы срабатывать при patch-запросах
        # валидация номера телефона
        if attrs.get('phone'):
            validated_phone = re.search(reg_patterns.re_phone, attrs['phone'])
            if not validated_phone:
                raise ValidationError(Error.PHONE_IS_INCORRECT.value)

        return attrs


class UserBuyerSerializer(serializers.ModelSerializer):
    """Информация о пользователе с ролью покупателя"""

    contacts = ContactSerializer(read_only=True)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'avatar_thumbnail', 'contacts']
        read_only_fields = ['id']


class UserSerializer(UserBuyerSerializer):
    """Информация о пользователе с ролью менеджера"""

    first_name = serializers.CharField(min_length=1)
    last_name = serializers.CharField(min_length=1)

    class Meta:
        model = User
        fields = ['id', 'first_name', 'last_name', 'email', 'avatar_thumbnail', 'company', 'position', 'type',
                  'contacts']
        read_only_fields = ['id']


class CategorySerializer(serializers.ModelSerializer):
    """Просмотр категорий товаров"""

    class Meta:
        model = Category
        fields = ['id', 'name']
        read_only_fields = ['id']


class ShopSerializer(serializers.ModelSerializer):
    """Просмотр информации о магазинах (без остатков)"""

    class Meta:
        model = Shop
        fields = ['id', 'name', 'url', 'state']
        read_only_fields = ['id']


class ProductSerializer(serializers.ModelSerializer):
    """Наименование продукта + категория"""

    class Meta:
        model = Product
        fields = ['name', 'category']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['category'] = instance.category.name
        return result


class InnerProductParameterSerializer(serializers.ModelSerializer):
    """Инлайн с характеристиками товара"""

    parameter = serializers.ReadOnlyField(source='parameter.name')

    class Meta:
        model = ProductParameter
        fields = ['parameter', 'value']


# noinspection PyUnresolvedReferences
class ProductParameterSerializer(serializers.ModelSerializer):
    """Информация о товаре с характеристиками на складах"""

    # product_parameters = InnerProductParameterSerializer(many=True, read_only=True)

    class Meta:
        model = ProductInfo
        fields = ['model', 'product', 'shop', 'price', 'quantity']
        # fields = ['model', 'product', 'shop', 'price', 'quantity', 'product_parameters']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['product'] = ProductSerializer(instance.product).data
        all_rates = list(instance.ratings.all().values_list('rating', flat=True))
        if all_rates:
            rating = round(sum([int(i) for i in all_rates]) / len(all_rates), 1)
            result['total_rating'] = rating
        else:
            result['total_rating'] = ''
        result['shop'] = instance.shop.name

        # добавляем в вывод иконку изображения
        if instance.photos.filter(is_main=True).exists():
            icon = ProductInfoPhoto.objects.filter(product=instance).first()
            result['photo'] = icon.photo_small.url
        else:
            result['photo'] = media.default_photo_icon  # заглушка для вывода, если не подгружена иконка

        return result


class ReviewSerializer(serializers.ModelSerializer):
    """Информация об оценке с отзывом от клиента"""

    buyer = serializers.StringRelatedField(source='user')

    class Meta:
        model = RatingProduct
        fields = ['buyer', 'rating', 'review']


class ProductInfoDetailSerializer(serializers.ModelSerializer):
    """Детализация информации по конкретному товару в магазине"""

    product = ProductSerializer()
    product_parameters = InnerProductParameterSerializer(many=True, read_only=True)
    shop = serializers.ReadOnlyField(source='shop.name')
    ratings = ReviewSerializer(many=True, read_only=True)

    class Meta:
        model = ProductInfo
        fields = ['id', 'product', 'description', 'product_parameters', 'price', 'external_id', 'shop', 'quantity',
                  'ratings']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        all_rates = list(instance.ratings.all().values_list('rating', flat=True))
        if all_rates:
            rating = round(sum([int(i) for i in all_rates]) / len(all_rates), 1)
            result['total_rating'] = rating
        else:
            result['total_rating'] = ''

        # основное изображение в высоком качестве для описания товара
        if instance.photos.all().exists():
            image = instance.photos.filter(is_main=True).first().photo_large.url
            result['main_image'] = image
        else:
            result['main_image'] = media.default_photo_large

        # все изображения отображаются ниже иконками, при клике отображаются в высоком качестве во всплывающем окне
        if instance.photos.all().exists():
            images = [i.photo_small.url for i in instance.photos.all()]
        else:
            images = []
        result['icons'] = images

        # все изображения в высоком разрешении для вывода на страницу при клике на иконку
        if instance.photos.all().exists():
            images = [i.photo_large.url for i in instance.photos.all()]
        else:
            images = []
        result['images_large'] = images

        return result


class InnerProdInfoInOrderSerializer(serializers.ModelSerializer):
    """Инлайн с информацией о товаре в заказе"""

    class Meta:
        model = ProductInfo
        fields = ['product', 'price']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['product'] = instance.product.name
        return result


class InnerOrderItemCustomerSerializer(serializers.ModelSerializer):
    """Инлайн OrderItem: продукт + количество в заказе для отображения в Заказах"""

    class Meta:
        model = OrderItem
        fields = ['product_info', 'quantity']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['product_info'] = InnerProdInfoInOrderSerializer(instance.product_info).data
        return result


class BasketSerializer(serializers.ModelSerializer):
    """Корзина клиента"""

    ordered_items = InnerOrderItemCustomerSerializer(many=True)
    total_sum = serializers.IntegerField(read_only=True)
    shop = serializers.ReadOnlyField()

    class Meta:
        model = Order
        fields = ['shop', 'total_sum', 'ordered_items']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['shop'] = instance.ordered_items.all().first().product_info.shop.name
        return result


class OrderItemCreateSerializer(serializers.ModelSerializer):
    """Создание строки заказа в ордере"""

    class Meta:
        model = OrderItem
        fields = ['product_info', 'order', 'quantity']


class OrderCustomerSerializer(BasketSerializer):
    """Ордер с итоговой суммой + информация о заказе"""

    class Meta:
        model = Order
        fields = ['id', 'datetime', 'state', 'total_sum', 'shop']


class OrderDetailSerializer(serializers.ModelSerializer):
    """Детализация клиентского заказа"""

    contact = AddressSerializer()
    ordered_items = InnerOrderItemCustomerSerializer(many=True)

    class Meta:
        model = Order
        fields = ['id', 'state', 'datetime', 'total_sum', 'ordered_items', 'delivery_date', 'delivery_time',
                  'recipient_full_name', 'contact']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['shop'] = instance.ordered_items.all().first().product_info.shop.name
        return result


'''Сериализаторы длы просмотра созданных заказов Партнером'''


class InnerProductPartnerSerializer(serializers.ModelSerializer):
    """Инлайн с детализацией продукта со склада для просмотра в ордере Партнером.
    Без параметров, с внутренними кодами"""

    class Meta:
        model = ProductInfo
        fields = ['id', 'model', 'external_id', 'product', 'price', 'price_rrc']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['product'] = ProductSerializer(instance.product).data
        return result


class InnerOrderItemPartnerSerializer(serializers.ModelSerializer):
    """Инлайн с информацией о заказанных товарах/их количестве для просмотра в ордере Партнером"""

    class Meta:
        model = OrderItem
        fields = ['product_info', 'quantity']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['product_info'] = InnerProductPartnerSerializer(instance.product_info).data
        return result


class OrderPartnerSerializer(OrderCustomerSerializer):
    """Ордер с итоговой суммой и информацией о заказе/клиенте для обработки партнером"""

    ordered_items = InnerOrderItemPartnerSerializer(many=True)
    user = serializers.StringRelatedField(read_only=True)
    contact_phone = serializers.ReadOnlyField(source='contact.contact.phone')

    class Meta:
        model = Order
        fields = ['id', 'datetime', 'delivery_date', 'delivery_time', 'total_sum', 'user',
                  'recipient_full_name', 'state', 'ordered_items', 'contact', 'contact_phone']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['contact'] = AddressSerializer(instance.contact).data
        return result


class ProductPhotoSerializer(serializers.ModelSerializer):
    """Вывод информации об изображении товара"""

    class Meta:
        model = ProductInfoPhoto
        fields = ['id', 'photo', 'is_main']


class ShopProductPhotoSerializer(serializers.ModelSerializer):
    """Товар + все его изображения"""

    photos = ProductPhotoSerializer(many=True, read_only=True)

    class Meta:
        model = ProductInfo
        fields = ['id', 'external_id', 'product', 'shop', 'photos']

    def to_representation(self, instance):
        result = super().to_representation(instance)
        result['shop'] = instance.shop.name
        result['product'] = instance.product.name
        return result
