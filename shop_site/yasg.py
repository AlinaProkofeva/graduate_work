from django.urls import path
from rest_framework import permissions, serializers
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from drf_yasg.openapi import IN_QUERY, TYPE_INTEGER, Parameter as Param, TYPE_STRING, TYPE_FILE, IN_FORM

from backend.models import Order, OrderItem, User

schema_view = get_schema_view(
   openapi.Info(
      title="Интернет-магазин",
      default_version='v1',
      description="Тестирование с аутентификацией по токенам пользователей",
      license=openapi.License(name="BSD License"),
   ),
   public=True,
   permission_classes=[permissions.AllowAny]
)

# noinspection PyUnresolvedReferences
urlpatterns = [
   # path(r'swagger(?P<format>\.json|\.yaml)', schema_view.without_ui(cache_timeout=0), name='schema-json'),
   path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
   path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
]

# query_params для работы с заказами пользователя: фильтрация и поиск
manual_parameters_orderview_get = [
   Param('id', IN_QUERY, type=TYPE_INTEGER),
   Param('shop', IN_QUERY, type=TYPE_STRING),
   Param('product', IN_QUERY, type=TYPE_STRING),
   Param('state', IN_QUERY, type=TYPE_STRING),
   Param('date_before', IN_QUERY, type=TYPE_STRING),
   Param('date_after', IN_QUERY, type=TYPE_STRING),
]

# query_params для работы с заказами магазина: фильтрация и поиск
manual_parameters_orderpartner_get = [
   Param('id', IN_QUERY, type=TYPE_INTEGER),
   Param('product', IN_QUERY, type=TYPE_STRING),
   Param('state', IN_QUERY, type=TYPE_STRING),
   Param('date', IN_QUERY, type=TYPE_STRING),
   Param('date_before', IN_QUERY, type=TYPE_STRING),
   Param('date_after', IN_QUERY, type=TYPE_STRING),
   Param('sum_more', IN_QUERY, type=TYPE_INTEGER),
   Param('sum_less', IN_QUERY, type=TYPE_INTEGER),
   Param('delivery_date_before', IN_QUERY, type=TYPE_STRING),
   Param('delivery_date_after', IN_QUERY, type=TYPE_STRING),
]

# загрузка файла
manual_parameters_partnerupdate = [
   Param(name="file", in_=IN_FORM, type=TYPE_FILE, required=True, description="Файл")
]

# Вспомогательные сериализаторы для тест-драйва swagger


class OrderPostSerializer(serializers.Serializer):
    """Размещение заказа пользователя из корзины"""

    contact = serializers.IntegerField(min_value=1)
    delivery_date = serializers.CharField(min_length=10, max_length=10)
    delivery_time = serializers.CharField(min_length=5, max_length=20)
    recipient_full_name = serializers.CharField(min_length=3, max_length=50)


class BasketDeleteSerializer(serializers.Serializer):
    """Удаление товаров из корзины по переданному списку с id"""

    ids = serializers.ListSerializer(child=serializers.IntegerField(), min_length=1)


class ProdInfoQuantSerializer(serializers.ModelSerializer):
    """Информация о строке в заказе, id товара + количество в заказе"""

    class Meta:
        model = OrderItem
        fields = ['product_info', 'quantity']


class BasketPostSerializer(serializers.ModelSerializer):
    """Информация о заказанных позициях. Включает вложенный список из id товара + количества в заказе"""

    ordered_items = ProdInfoQuantSerializer(many=True)

    class Meta:
        model = Order
        fields = ['ordered_items']


class PartnerOrderPostSerializer(serializers.ModelSerializer):
    """Изменение статуса заказа партнером"""

    id = serializers.IntegerField(min_value=1)

    class Meta:
        model = Order
        fields = ['id', 'state', 'delivery_date', 'delivery_time']


class PartnerStatePostSerializer(serializers.Serializer):
    """Изменение статуса приема заказов магазином"""

    state = serializers.CharField(min_length=1)


class PartnerUpdatePostSerializer(serializers.Serializer):
    """Передача url для создания магазина"""

    url = serializers.URLField()


class ContactPostSerializer(serializers.Serializer):
    """Добавление нового контакта пользователя/новых адресов к существующему контакту"""

    phone = serializers.CharField(min_length=10, max_length=10)
    region = serializers.CharField(min_length=2, max_length=50)
    district = serializers.CharField(max_length=50)
    settlement = serializers.CharField(max_length=50)
    street = serializers.CharField(min_length=2, max_length=50)
    house = serializers.CharField(max_length=50)
    structure = serializers.CharField(max_length=50)
    building = serializers.CharField(max_length=50)
    apartment = serializers.CharField(max_length=50)


class ContactPatchSerializer(ContactPostSerializer):
    """Редактирование контакта пользователя"""

    id = serializers.IntegerField(min_value=1)


class ContactDeleteSerializer(serializers.Serializer):
    """Удаление контакта/контактов пользователя"""

    ids = serializers.CharField(min_length=1)
    delete_contact = serializers.CharField(min_length=4, max_length=4)


class AccountCreatePatchSerializer(serializers.ModelSerializer):
    """Регистрация/редактирование данных аккаунта пользователя"""

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'password', 'company', 'position', 'type']


class ConfirmAccountSerializer(serializers.Serializer):
    """Активация пользователя после регистрации/смены email"""

    email = serializers.EmailField()
    token = serializers.CharField(min_length=1)


class LoginAccountSerializer(serializers.Serializer):
    """Аутентификация пользователя в системе и получение auth токена"""

    email = serializers.EmailField()
    password = serializers.CharField()


class RateProductSerializer(serializers.Serializer):
    """Отправка оценки и отзыва на приобретенный товар"""

    product_id = serializers.IntegerField(min_value=1)
    rating = serializers.IntegerField(min_value=1, max_value=5)
    review = serializers.CharField(max_length=250)


class CreateReportSerializer(serializers.Serializer):
    """Формирование отчета по товарам в заказах магазина за указанный период"""

    from_date = serializers.DateField()
    before_date = serializers.DateField()
