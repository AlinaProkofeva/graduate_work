import datetime
import re
from smtplib import SMTPRecipientsRefused
import oauth2_provider.models
from django_rest_passwordreset.views import ResetPasswordRequestToken, ResetPasswordConfirm
# from yaml import load as load_yaml, Loader, safe_load
from distutils.util import strtobool
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.db.models import Sum, F, Q
from django.core.validators import URLValidator
from django.core.exceptions import ValidationError
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.models import Token
from rest_framework.parsers import MultiPartParser
from drf_yasg.utils import swagger_auto_schema

import backend.models
from backend.models import Order, Shop, OrderItem, ProductInfo, Category, Contact, ConfirmEmailToken, Address, \
    RatingProduct
from .filters import ProductsFilter, query_filter_maker
from .serializers import ShopSerializer, OrderCustomerSerializer, ProductParameterSerializer, CategorySerializer, \
    OrderPartnerSerializer, ContactSerializer, BasketSerializer, OrderItemCreateSerializer, UserSerializer, \
    UserBuyerSerializer, AddressSerializer, ProductInfoDetailSerializer, OrderDetailSerializer, ReviewSerializer
from shop_site.yasg import OrderPostSerializer, BasketDeleteSerializer, BasketPostSerializer, \
    manual_parameters_orderview_get, manual_parameters_orderpartner_get, PartnerOrderPostSerializer, \
    PartnerStatePostSerializer, PartnerUpdatePostSerializer, manual_parameters_partnerupdate, \
    ContactPatchSerializer, ContactDeleteSerializer, ContactPostSerializer, \
    AccountCreatePatchSerializer, ConfirmAccountSerializer, LoginAccountSerializer, RateProductSerializer, \
    CreateReportSerializer
from .signals import new_account_registered, new_order_state, new_order_created, new_report
from .utils.error_text import Error, ValidateError
from .utils import reg_patterns
from .utils.get_data_from_yaml import get_data_from_yaml_file, create_categories, get_data_from_all_tasks
from .tasks import task_load_good_from_yaml
from .task_backup import backup_shop_base, send_report_task


'''==================Сторона клиента========================='''


# noinspection PyUnusedLocal
class RegisterAccount(APIView):
    """
    Класс для регистрации нового пользователя (клиента, менеджера) в неактивном статусе
    """

    @swagger_auto_schema(request_body=AccountCreatePatchSerializer)
    def post(self, request, *args, **kwargs):
        """
        Зарегистрировать нового пользователя (клиента, менеджера) в неактивном статусе.

        Для регистрации в data необходимо передать обязательные данные.

        для клиента:

        {
            "first_name": "клиент",
            "last_name": "фамилия",
            "email": "test2@mail.ru",
            "password": "test"
        }

        для менеджера магазина:

        {
            "first_name": "менеджер",
            "last_name": "фамилия",
            "email": "test3@mail.ru",
            "password": "test",
            "company": "Билайн",
            "position": "РГО",
            "type": "shop"
        }
        """

        # проверка, что в data указаны все минимально необходимые параметры
        if not {'first_name', 'last_name', 'password'}.issubset(request.data):
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

        # валидация пароля
        try:
            validate_password(request.data['password'])
        except ValidationError as e:
            return Response({'Status': False, 'Error': [str(item) for item in e]}, status=400)

        # создание пользователя через сериализатор
        serializer = UserSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.set_password(request.data.get('password'))
            user.save()

            # отправляем письмо на email с токеном для дальнейшей активации
            new_account_registered.send(sender=self.__class__, user_id=user.id)
            return Response(serializer.data)

        else:
            return Response(serializer.errors)


# noinspection PyUnusedLocal
# noinspection PyUnresolvedReferences
class ConfirmAccount(APIView):
    """
    Класс для подтверждения почтового адреса и активации пользователя после регистрации/смены email
    """

    @swagger_auto_schema(request_body=ConfirmAccountSerializer)
    def post(self, request, *args, **kwargs):
        """
        Активировать нового зарегистрированного пользователя (подтверждение почты по токену из письма)

        В data необходимо передать обязательные аргументы. Token приходит на почту пользователя в письме,
        автоматически отправляющемся после регистрации нового аккаунта

        {
        "email": "ve4nayavesna@mail.ru",
        "token": "a43ff4a030153f267fd250bd833c7cc94"
        }
        """

        # проверяем, что все необходимые данные переданы в data
        if not {'email', 'token'}.issubset(request.data):
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

        # делаем валидацию email в data
        if not re.fullmatch(reg_patterns.re_email, request.data['email']):
            return Response(Error.EMAIL_WRONG.value, status=400)

        # проверяем корректность указанных в data данных пользователя
        user_token = ConfirmEmailToken.objects.filter(token=request.data['token'],
                                                      user__email=request.data['email']).first()
        if not user_token:
            return Response(Error.EMAIL_OR_TOKEN_WRONG.value, status=400)

        user_token.user.is_active = True
        user_token.user.save()
        user_token.delete()  # чистим таблицу после активации user
        return Response({'Status': True, 'is_active': True})


class MyResetPasswordRequestToken(ResetPasswordRequestToken):
    """
    Класс для запроса сброса пароля пользователя.

    В data необходимо передать email для получения токена на сброс:

    {
        "email": "yourmail@gmail.com"
    }
    """
    pass


class MyResetPasswordConfirm(ResetPasswordConfirm):
    """
    Класс для подтверждения сброса старого пароля пользователя и установки нового пароля.

    В data необходимо передать полученный на email токен на сброс и новый пароль:

    {
        "password": "new_pass",
        "token": "my_email_token"
    }
    """
    pass


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
class LoginAccount(APIView):
    """
    Класс для авторизации пользователей и получения auth токена
    """

    @swagger_auto_schema(request_body=LoginAccountSerializer)
    def post(self, request, *args, **kwargs):
        """
        Пройти аутентификацию пользователя в системе и получить auth токен

        В data необходимо передать данные:

        {
        "email": "ve4nayavesna@mail.ru",
        "password": "a43ff4a030153f267fd250bd833c7cc94"
        }

        **Если регистрация была через VK, и пользователь еще не сменил данные аккаунта, то в email необходимо передать
        access token пользователя, полученный при регистрации**
        **Поле password в таком случае не заполняется или может принимать любое значение**
        """

        # проверяем, была ли авторизация через VK
        soc_token = oauth2_provider.models.AccessToken.objects.filter(token=request.data.get('email')).first()
        if soc_token:
            token, _ = Token.objects.get_or_create(user=soc_token.user)
            return Response({'Status': True, 'Token': token.key})

        else:
            # проверяем, что все необходимые данные переданы в data
            if not {'email', 'password'}.issubset(request.data):
                return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

            # делаем валидацию email в data
            if not re.fullmatch(reg_patterns.re_email, request.data['email']):
                return Response(Error.EMAIL_WRONG.value, status=400)

            # проверяем, что пользователь с такими данными существует и активен
            user = authenticate(email=request.data['email'], password=request.data['password'])

            if not user or not user.is_active:
                return Response(Error.AUTH_FAILED.value, status=400)

            token, _ = Token.objects.get_or_create(user=user)
            return Response({'Status': True, 'Token': token.key})


# noinspection PyUnusedLocal
class LogoutAccount(APIView):
    """
    Класс для выхода пользователя из аккаунта и удаления auth-токена
    """

    # noinspection PyMethodMayBeStatic
    def post(self, request, *args, **kwargs):
        """
        Выйти пользователем из системы.

        Auth токен будет удален из БД.
        """

        # Проверяем авторизацию пользователя
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        request.user.auth_token.delete()
        return Response({'Status': True})


# noinspection PyUnusedLocal
class AccountDetails(APIView):
    """
    Класс для работы с данными пользователя
    """

    # noinspection PyMethodMayBeStatic
    def get(self, request, *args, **kwargs):
        """
        Получить данные аккаунта пользователя.

        Только для авторизованных пользователей.
        """

        # Проверяем авторизацию пользователя
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # В зависимости от типа пользователя выбираем сериализатор
        if request.user.type == 'shop':
            serializer = UserSerializer(request.user)
        else:
            serializer = UserBuyerSerializer(request.user)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=AccountCreatePatchSerializer)
    def patch(self, request, *args, **kwargs):
        """
        Редактировать данные аккаунта пользователя.

        В data необходимо передать новые данные (полностью или частично):

        {
        "first_name": "Новое имя",
        "last_name": "Новая фамилия",
        "email": "new_email@mail.ru",
        "password": "new_password",
        "company": "",
        "position": "",
        "type": "shop"
        }

        _при смене email необходимо повторное подтверждение аккаунта с новой почты_
        """

        # Проверяем авторизацию пользователя
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Проверяем наличие необходимых аргументов
        expected_args = {'first_name', 'last_name', 'email', 'company', 'position', 'type', 'password'}
        not_expected_args = expected_args.isdisjoint(request.data.keys())
        if not_expected_args:  # нет нужных элементов
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

        # делаем валидацию нового пароля, если он указан
        new_password = request.data.get('password')
        if new_password:
            try:
                validate_password(new_password)
            except ValidationError as errors:
                return Response({'Status': False, 'Errors': [str(error) for error in errors]}, status=400)

        # делаем валидацию нового email, если он указан
        new_email = request.data.get('email')
        current_email = ''
        if new_email:
            current_email = request.user.email  # сохраняем текущую почту, если не удастся заменить на новую
            if not re.fullmatch(reg_patterns.re_email, new_email):
                return Response(Error.EMAIL_WRONG.value, status=400)

        error = {}  # для записи детализации ошибок

        serializer = UserSerializer(instance=request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()

            if new_password:
                request.user.set_password(new_password)
                request.user.save()

            # При смене почты необходимо подтверждение и повторная активация с нового email адреса
            if new_email:
                try:
                    request.user.email = new_email
                    request.user.save()
                    new_account_registered.send(sender=self.__class__, user_id=request.user.id)

                # если не удалось отправить письмо на новую почту, отменяем изменение почты
                except (Exception, ):
                    request.user.email = current_email
                    request.user.save()
                    error['Error'] = Error.EMAIL_CHANGE_FAILED.value['Error']

                # если почта существует, то оставляем новую и деактивируем пользователя
                else:
                    request.user.is_active = False
                    request.user.save()
            return Response({**serializer.data, **error})

        return Response({'Status': False, 'Error': serializer.errors}, status=400)


# noinspection PyUnresolvedReferences
class CategoryView(ListAPIView):
    """
    Класс для просмотра категорий товара.

    Все категории.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


# noinspection PyUnresolvedReferences
class ShopView(ListAPIView):
    """
    Класс для просмотра магазинов, принимающих заказы.

    Без детализации.
    """
    queryset = Shop.objects.filter(state=True)
    serializer_class = ShopSerializer


# noinspection PyUnresolvedReferences
class ProductInfoView(ListAPIView):
    """
    Класс для просмотра ассортимента магазинов + поиск товаров.

    Параметры доступной фильтрации и поиска:

    'shop_id' фильтр по id магазина
    'shop_name' фильтр по названию магазину (без учета регистра, по частичному совпадению)
    'price_more' фильтр по цене больше или равно
    'price_less' фильтр по цене меньше или равно
    'category_id' фильтр по id категории продуктов
    'category' фильтр по названию категории продуктов (без учета регистра, по частичному совпадению)

    'search' поиск по названию продукта, модели, наименованию параметра (без учета регистра, по частичному совпадению)

    Параметры сортировки:

    'ordering' сортировка по цене, названию продуктов
    (price, -price, product, -product)
    """
    queryset = ProductInfo.objects.filter(shop__state=True).\
        select_related('shop', 'product__category').\
        prefetch_related('product_parameters__parameter')
    serializer_class = ProductParameterSerializer

    # фильтрация + сортировка
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = ProductsFilter
    search_fields = ['product__name', 'model', 'product_parameters__parameter__name']
    ordering_fields = ['price', 'product']


# noinspection PyUnresolvedReferences
class ProductInfoDetailView(RetrieveAPIView):
    """
    Класс для просмотра детальной информации по конкретному товару в магазине.

    Детализация с расчетом рейтинга и отзывами.
    """
    queryset = ProductInfo.objects.all().select_related('product', 'shop').\
        prefetch_related('product_parameters__parameter', 'ratings__user')
    serializer_class = ProductInfoDetailSerializer


# noinspection PyUnresolvedReferences
class RateProduct(APIView):
    """
    Класс для отправки оценки и отзыва на продукт
    """

    @swagger_auto_schema(request_body=RateProductSerializer)
    def post(self, request):
        """
        Поставить оценку приобретенному продукту и оставить отзыв.

        Доступно только авторизованному пользователю при условии наличия заказа на оцениваемый продукт.
        В data необходимо передать:

        {
        "product_id": 40,
        "rating": 4,
        "review": "тут впечатления от пользования"
        }

        **product_id, rating являются обязательными аргументами**
        rating может быть в диапазоне от 1 до 5, где 5 - максимальная оценка
        """

        # проверка авторизации
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # проверка, что переданы необходимые аргументы
        data = request.data
        if not {'product_id', 'rating'}.issubset(data):
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

        # валидация отправленных данных
        product = data['product_id']  # проверяем аргумент product_id
        if type(product) == str:
            try:
                product = int(product)
            except ValueError:
                return Response(Error.PRODUCT_ID_WRONG_TYPE.value, status=400)
        elif type(product) == int:
            pass
        else:
            return Response(Error.PRODUCT_ID_WRONG_TYPE.value, status=400)

        rating = data['rating']  # проверяем аргумент rating
        if type(rating) == int:
            rating = str(rating)
        elif type(rating) == str:
            pass
        else:
            return Response(Error.RATING_WRONG_TYPE_OR_VALUE.value, status=400)

        expected_rating = [i[0] for i in backend.models.RATING_PRODUCT_CHOICES]
        if rating not in expected_rating:
            return Response(Error.RATING_WRONG_TYPE_OR_VALUE.value, status=400)

        # проверка, что товар был приобретен пользователем
        user = request.user
        buy_item = Order.objects.exclude(state='basket').filter(user=user, ordered_items__product_info__id=product)
        if not buy_item:
            return Response(Error.BUYER_ONLY.value, status=400)

        # создание записи в таблице
        review = data.get('review')
        try:
            rate = RatingProduct.objects.create(
                user=user,
                product_id=product,
                rating=rating,
                review=review
            )
        except IntegrityError:
            return Response(Error.RATING_DUPLICATE.value, status=400)

        serializer = ReviewSerializer(rate)
        return Response({'Status': 'Success', 'Добавлена оценка': serializer.data})


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
class ContactView(APIView):
    """
    Класс для работы клиента со своими контактами
    """

    @swagger_auto_schema()
    def get(self, request, *args, **kwargs):
        """
        Получить контакты пользователя.

        Контакт со списком адресов пользователя.
        """

        # проверка на авторизацию
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        query = Q(user=request.user)
        queryset = Contact.objects.filter(query)
        serializer = ContactSerializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=ContactPostSerializer)
    def post(self, request, *args, **kwargs):
        """
        Добавить новый контакт пользователя/новые адреса к существующему контакту

        В data необходимо передать следующие данные ("phone" обязателен только при записи первого адреса, при
        добавлении последующих адресов не требуется):

        {
        "phone": 8123334444,
        "region": "Архангельская обл.",
        "district": "",
        "settlement": "Архангельск гор.",
        "street": "Ленина ул.",
        "house": "д. 121",
        "structure": "",
        "building": "стр. 1-Н",
        "apartment": "кв. 80"
        }

        **обязательными аргументами являются 'region', 'street'**
        **"phone" обязателен только, если у пользователя еще нет контакта и это добавление первого адреса**
        """

        # проверка на авторизацию
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # проверка на наличие всех обязательных аргументов
        if not {'region', 'street'}.issubset(request.data):
            return Response(Error.NOT_REQUIRED_ARGS.value, status=403)
        request_data = dict(request.data)

        # ставим ограничение на допустимое количество контактов клиента
        if Address.objects.filter(contact__user=request.user).count() >= 5:
            return Response(Error.CONTACTS_EXCEEDING.value, status=400)

        # при отправке через форм-дата в Postman оборачивает в списки (?), исправляем
        if type(list(request_data.values())[0]) == list:
            for k, v in request_data.items():
                request_data.update({k: v[0]})

        # проверяем, существует ли контакт клиента
        contact = Contact.objects.filter(user=request.user).count()
        if not contact and 'phone' not in request_data:
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

        phone = request_data.get('phone')
        if phone:
            phone = request_data.pop('phone')

        # если это добавление первого адреса, создаем контакт с телефоном
        new_contact = None
        if not contact:
            serializer = ContactSerializer(data=request.data)
            if serializer.is_valid():
                try:
                    new_contact = Contact.objects.create(user=request.user, phone=phone)
                except IntegrityError as e:
                    return Response({'Status': False, 'Errors': str(e)})
            else:
                return Response({'Status': False, 'Errors': serializer.errors})

        # добавляем адреса к существующему/созданному контакту
        request_data.update(contact=request.user.contacts)
        serializer = AddressSerializer(data=request_data)
        if serializer.is_valid():
            try:
                Address.objects.create(**request_data)
                return Response(serializer.data)
            except IntegrityError as e:
                if new_contact:
                    new_contact.delete()
                return Response({'Status': False, 'Errors': str(e)})
        else:
            if new_contact:
                new_contact.delete()
            return Response(serializer.errors)

    @swagger_auto_schema(request_body=ContactPatchSerializer)
    def patch(self, request, *args, **kwargs):
        """
        Редактировать контакт/адреса пользователя.

        При редактировании **только** номера телефона достаточно в data передать аргумент "phone".

        При редактировании данных адреса необходимо дополнительно передать id редактируемой записи и новые данные
        (полностью или частично):

        {
        "phone": 8123334444,
        "id": 31,
        "region": "Москва",
        "district": "",
        "settlement": "",
        "street": "Ленина",
         "house": "5",
        "structure": "",
        "building": "Н",
        "apartment": "80"
        }
        """

        # проверка на авторизацию
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # проверка на наличие новых данных для изменения и обязательного аргумента id и при изменении адреса
        expected_args = {'phone', 'region', 'district', 'settlement', 'street', 'house', 'structure', 'building',
                         'apartment'}
        phone = None
        if 'phone' in request.data:
            phone = request.data.pop('phone')  # забираем значение телефона из данных
        if not request.data.get('id') and True in map(lambda x: x in expected_args, request.data):
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

        contact = None
        if phone:
            # меняем номер телефона пользователя
            contact = Contact.objects.filter(user=request.user).first()
            if not contact:
                return Response(Error.CONTACT_NOT_EXIST.value, status=403)
            serializer = ContactSerializer(contact, data={'phone': phone})
            if serializer.is_valid():
                serializer.save()
            else:
                return Response(serializer.errors)

        # если переданы данные для изменения адреса - меняем
        if True in map(lambda x: x in expected_args, request.data):
            if type(request.data['id']) != int:  # проверка, что в id передано цифровое значение
                if not request.data['id'].isdigit():
                    return Response(Error.ID_NOT_INT.value, status=400)

            contact = Contact.objects.filter(user=request.user).first()  # определяем контакт
            if not contact:
                return Response(Error.CONTACT_NOT_EXIST.value, status=403)
            address = Address.objects.filter(contact=contact, id=request.data['id']).first()  # изменяемый адрес
            if not address:
                return Response(Error.CONTACT_NOT_EXIST.value, status=400)
            serializer = AddressSerializer(address, data=request.data, partial=True)
            if serializer.is_valid():
                serializer.save()
            else:
                return Response(serializer.errors)
        return Response(ContactSerializer(contact).data)

    @swagger_auto_schema(request_body=ContactDeleteSerializer)
    def delete(self, request, *args, **kwargs):
        """
        Удалить контакт полностью или адрес/несколько адресов пользователя.

        Для **полного удаления** контакта в data необходимо передать
        {
        "delete_contact": "True"
        }

        Для **удаления адреса/адресов контакта** в data необходимо передать id/перечень id удаляемых адресов:
        {
        "ids": [27, 28]
        }
        """

        # проверка на авторизацию
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # если требуется полное удаление всех контактных данных пользователя
        if request.data.get('delete_contact'):
            if request.data['delete_contact'] == 'True':
                contact = Contact.objects.filter(user=request.user).first()  # находим контакт пользователя
                if not contact:
                    return Response(Error.CONTACTS_NOT_EXIST.value, status=400)
                deleted = contact.delete()
                return Response({'Status': True, 'Удалено объектов': deleted[0]})
            return Response(Error.DELETE_CONTACT_WRONG.value, status=400)

        # если требуется частичное удаление адресов, проверка, что передан необходимый аргумент ids
        ids = request.data.get('ids')
        if not ids:
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

        # проверка, что все значения ids являются int
        ids_list = []
        if type(ids) == str:
            ids_list = [i.strip() for i in ids.split(',')]
            if False in (list(i.isdigit() for i in ids_list)):
                return Response(Error.IDS_WRONG_TYPE.value, status=400)
        elif type(ids) == list:
            try:
                ids_list = [int(i) for i in ids]
            except ValueError:
                return Response(Error.IDS_WRONG_TYPE.value, status=400)
        elif type(ids) == int:
            ids_list.append(ids)

        contact = Contact.objects.filter(user=request.user).first()  # находим контакт пользователя
        if not contact:
            return Response(Error.CONTACTS_NOT_EXIST.value, status=400)
        query = Q()
        for item in ids_list:
            query = query | Q(id=int(item), contact_id=contact.id)

        errors = {}  # сборщик ошибок
        deleted = Address.objects.filter(query).delete()
        if not deleted[0]:
            return Response(Error.CONTACTS_NOT_EXIST.value, status=400)
        if len(ids_list) > deleted[0]:
            errors['Не удалось удалить объектов'] = len(ids_list) - deleted[0]
            errors['Error'] = Error.CONTACTS_NOT_EXIST.value['Error']
        return Response({'Status': True, 'Удалено объектов': deleted[0], **errors})


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
class BasketView(APIView):
    """
    Класс для работы с корзиной покупателя
    """

    # noinspection PyMethodMayBeStatic
    def get(self, request, *args, **kwargs):
        """
        Посмотреть содержимое корзины пользователя

        Доступно только авторизованным пользователям
        """

        # проверка на авторизацию
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        basket = Order.objects.filter(state='basket', user=request.user.id).\
            select_related('user').prefetch_related('ordered_items__product_info__product__category',
                                                    'ordered_items__product_info__shop',
                                                    'ordered_items__product_info__product_parameters__parameter').\
            annotate(total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price')))
        serializer = BasketSerializer(basket, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=BasketPostSerializer)
    def post(self, request, *args, **kwargs):
        """
        Добавить товар в корзину

        В data необходимо передать список со словарями, включающими id заказываемого продукта со склада + количество:

        {"ordered_items": [
            {"product_info": 3, "quantity": 1},
            {"product_info": 4, "quantity": 2}]}
        """

        # проверка на авторизацию
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Если заказ со статусом "корзина" уже существует у пользователя, то новые отправленные в корзину
        # товары будут добавляться в этот заказ, не создавая новый
        basket, _ = Order.objects.get_or_create(state='basket', user=request.user)
        objects_created = 0

        # собиратели ошибок
        objects_failed = 0
        errors = {}
        errors_list = []

        items = request.data.get('ordered_items')

        # добавляем проверку, к какому магазину относятся товары, уже находящиеся в корзине (нельзя в одном
        # заказе совместить позиции из разных магазинов)
        basket_items = basket.ordered_items.all()
        if basket_items:
            basket_shop = basket_items.first().product_info.shop
        else:
            basket_shop = None  # если в корзине не было товаров

        # проверяем и записываем в корзину указанные в data товары
        for item in items:
            item['order'] = basket.id
            check_shops_failed = False
            serializer = OrderItemCreateSerializer(data=item)
            if serializer.is_valid():

                # проверяем, чтобы в корзине могли находиться только заказы из одного магазина
                added_item = ProductInfo.objects.filter(id=item['product_info']).first()

                added_item_shop = None
                if added_item:
                    added_item_shop = added_item.shop

                # если товары в корзине уже есть, делаем проверку
                if basket_shop is not None:
                    if basket_shop != added_item_shop:
                        objects_failed += 1
                        errors_list.append(Error.BASKET_HAS_GOOD_FROM_DIFFERENT_SHOP.value['Error'])
                        check_shops_failed = True
                else:
                    basket_shop = added_item_shop  # если не было товаров, присваиваем магазин первого товара

                if not check_shops_failed:
                    try:
                        serializer.save()
                    except IntegrityError as e:
                        objects_failed += 1
                        errors_list.append(str(e))
                    else:
                        objects_created += 1
                else:
                    continue  # если проверка магазина не пройдена, обрабатываем следующий товар
            else:
                objects_failed += 1
                errors_list.append(serializer.errors)

        # если ошибки были, добавляем счетчик ошибок
        if errors_list:
            errors['Errors'] = errors_list
            errors['Не удалось добавить товаров в корзину'] = objects_failed

        status = False if not objects_created else True
        return Response({'Status': status, 'Добавлено товаров в корзину': objects_created, **errors})

    @swagger_auto_schema(request_body=BasketPostSerializer)
    def patch(self, request, *args, **kwargs):
        """
        Изменить количество у товара в корзине.

        В data необходимо передать список со словарями, включающими id заказываемого продукта со склада + новое
         количество:

        {"ordered_items": [
            {"product_info": 3, "quantity": 1},
            {"product_info": 4, "quantity": 2}]}
        """

        # проверка на авторизацию
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        basket, _ = Order.objects.get_or_create(user=request.user, state='basket')
        objects_updated = 0

        # обработчики ошибок
        objects_failed = 0
        errors = {}
        errors_list = []

        # проверяем пришедшие data
        items = request.data.get('ordered_items')
        for item in items:
            if not {'product_info', 'quantity'}.issubset(item):
                return Response(Error.NOT_REQUIRED_ARGS.value, status=400)
            if type(item['product_info']) != int or type(item['quantity']) != int or item['quantity'] < 1:
                return Response(Error.ID_OR_QUANTITY_WRONG_TYPE.value, status=400)

        for item in items:
            try:
                result = OrderItem.objects.filter(
                    order=basket, product_info_id=item['product_info']). \
                    update(quantity=item['quantity'])
                if result:
                    objects_updated += 1

                # если товар существует, но в корзине его нет
                else:
                    objects_failed += 1
                    errors_list.append(f'Товар с id {item["product_info"]} отсутствует в корзине')

            # Обрабатываем несуществующие id
            except backend.models.ProductInfo.DoesNotExist:
                objects_failed += 1
                errors_list.append(f'Товар с id {item["product_info"]} отсутствует в корзине')

        # если есть ошибки, записываем их в словарь
        if objects_failed:
            errors['Не удалось изменить количество у товаров'] = objects_failed
            errors['Errors'] = errors_list

        status = True if objects_updated else False
        return Response({"Status": status, "Изменено количество у товаров": objects_updated, **errors})

    @swagger_auto_schema(request_body=BasketDeleteSerializer)
    def delete(self, request, *args, **kwargs):
        """
        Удалить товар/товары из корзины

        В data необходимо передать список ids товаров к удалению:
        {
        "ids": [2, 3]
        }
        """

        # Проверка авторизации пользователя
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        basket = Order.objects.filter(user=request.user, state='basket').first()
        if not basket or basket.ordered_items.count() == 0:
            return Response(Error.BASKET_IS_EMPTY.value, status=400)

        # Проверка переданных данных на пустоту, корректный тип
        ids_for_delete = request.data.get('ids')
        if not ids_for_delete:
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)
        if type(ids_for_delete) != list:
            return Response(Error.IDS_WRONG_TYPE.value, status=400)
        for item_id in ids_for_delete:
            try:
                int(item_id)
            except ValueError or TypeError:
                return Response(Error.IDS_WRONG_TYPE.value, status=400)

        objects_deleted = 0

        # сборщик ошибок
        objects_failed = 0
        errors = {}
        errors_list = []

        for item_id in ids_for_delete:
            delete = OrderItem.objects.filter(order__id=basket.id, product_info__id=item_id).delete()[0]
            objects_deleted += delete

            if not delete:
                objects_failed += 1
                errors_list.append(f"В корзине нет товара с id {item_id}")

        # если есть ошибки, заполняем сборщик ошибок
        if objects_failed:
            errors['Не удалось удалить товаров'] = objects_failed
            errors['Errors'] = errors_list

        status = True if objects_deleted else False
        return Response({'Status': status, 'Удалено товаров': objects_deleted, **errors})


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
class OrderView(APIView):
    """
    Класс для получения и размещения заказов пользователями
    """

    # получить мои заказы + фильтрация
    @swagger_auto_schema(manual_parameters=manual_parameters_orderview_get)
    def get(self, request, *args, **kwargs):
        """
        Просмотреть заказы пользователя + поиск и фильтрация

        Доступная параметризация запроса:

        'id' фильтр по номеру заказа
        'shop' поиск по магазину (без учета регистра, по частичному совпадению)
        'product' поиск по названию продукта (без учета регистра, по частичному совпадению)
        'state' фильтр по статусу заказов
        'date_before' фильтр по дате 20XX-XX-XX, раньше чем указанная
        'date_after' фильтр по дате 20XX-XX-XX, начиная с указанной
        """

        # Проверка авторизации пользователя
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Фильтрация + поиск
        query = Q(user=request.user)
        filter_kwargs = {}
        expected_query_params = [
            ('id', 'id'),  # фильтр по номеру заказа
            ('shop', 'ordered_items__product_info__shop__name__contains'),  # поиск по магазину
            ('product', 'ordered_items__product_info__product__name__contains'),  # поиск по названию продукта
            ('state', 'state', True),  # фильтр по статусу заказов
            ('date_before', 'datetime__lt'),  # фильтр по дате 20XX-XX-XX, раньше чем указанная
            ('date_after', 'datetime__gte')  # фильтр по дате 20XX-XX-XX, начиная с указанной
        ]
        for item in expected_query_params:
            arguments = [request]
            for i in item:
                arguments.append(i)
            filter_kwargs.update(query_filter_maker(*arguments))

        query_total_sum = Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))
        orders = Order.objects.exclude(state='basket').\
            filter(query, **filter_kwargs).select_related('user', 'contact').\
            prefetch_related('ordered_items__product_info__product__category',
                             'ordered_items__product_info__product_parameters',
                             'ordered_items__product_info__shop').\
            annotate(total_sum=query_total_sum).order_by('-datetime')

        serializer = OrderCustomerSerializer(orders, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=OrderPostSerializer)
    def post(self, request, *args, **kwargs):
        """
        Разместить заказ пользователя из корзины.

        В data необходимо передать id АДРЕСА контакта, желаемую дату(не ранее следующего дня) и время доставки,
        ФИО получателя

        {
        "contact": 6,
        "delivery_date": "2023-12-31",
        "delivery_time": "afternoon_15_18",
        "recipient_full_name": "Фамилия Имя Отчество"
        }

        **Варианты выбора интервалов доставки:**
        'morning_09_12',
        'afternoon_12_15',
        'afternoon_15_18',
        'evening_18_22',
        """

        # Проверка авторизации пользователя
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Сборщик ошибок
        error = {}

        # Проверка data на наличие и корректность значений, привязку к пользователю
        contact = request.data.get('contact')
        delivery_date = request.data.get('delivery_date')
        delivery_time = request.data.get('delivery_time')
        recipient_full_name = request.data.get('recipient_full_name')
        if not {'contact', 'delivery_date', 'delivery_time', 'recipient_full_name'}.issubset(request.data):
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)
        try:
            int(contact)
        except ValueError:
            return Response(Error.CONTACT_WRONG.value, status=400)
        if contact not in request.user.contacts.addresses.all().values_list('id', flat=True):
            return Response(Error.CONTACT_WRONG.value, status=400)

        # проверяем корректность переданной даты доставки
        min_date_from = datetime.date.today() + datetime.timedelta(days=1)
        if delivery_date < str(min_date_from) or not re.fullmatch(reg_patterns.re_date, delivery_date):
            return Response(Error.DATE_WRONG.value, status=400)

        # проверяем корректность переданного времени доставки:
        expected_delivery_time = [i[0] for i in backend.models.DELIVERY_TIME_CHOICES]
        if delivery_time not in expected_delivery_time:
            return Response(Error.DELIVERY_TIME_WRONG.value, status=400)

        # Проверка, что в корзине есть товары
        basket = Order.objects.filter(state='basket', user=request.user)
        if not basket or basket.first().ordered_items.all().count() == 0:
            return Response(Error.BASKET_IS_EMPTY.value, status=400)
        order_id = basket.first().id  # № заказа для передачи в сигнал

        current_order_state = 'basket'
        try:
            update_state = basket.update(contact_id=contact,
                                         state='new',
                                         delivery_date=delivery_date,
                                         delivery_time=delivery_time,
                                         recipient_full_name=recipient_full_name
                                         )
        except (ValueError, ValidationError):
            return Response(Error.DATE_WRONG.value, status=400)

        if update_state:
            current_order_state = 'new'

            # Отправка письма о размещении заказа на почту покупателя
            try:
                new_order_created.send(self.__class__, order_id=order_id)
            except SMTPRecipientsRefused:
                error['Error'] = ValidateError.EMAIL_FAILED.value
        return Response({'Status': True, 'Статус заказа': current_order_state, **error})


# noinspection PyUnresolvedReferences
class OrderDetailView(RetrieveAPIView):
    """
    Класс для просмотра детальной информации заказа по id

    Полная детализация заказа.
    """
    serializer_class = OrderDetailSerializer

    def get_queryset(self):
        if self.request.user.id:
            total_sum = Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))
            queryset = Order.objects.annotate(total_sum=total_sum).filter(user=self.request.user).\
                select_related('contact').prefetch_related('ordered_items__product_info__product')
            return queryset
        else:
            return []


'''===========Блок функционала менеджеров магазинов============================='''


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
class PartnerState(APIView):
    """
    Класс для работы со статусом приема заказов магазина.

    Действия доступны только для привязанного к магазину user.
    """

    # noinspection PyMethodMayBeStatic
    def get(self, request, *args, **kwargs):
        """
        Проверить текущий статус приема заказов магазином.

        Действия доступны только для привязанного к магазину user.
        """

        # проверка авторизации
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Проверяем, что юзер == менеджер магазина
        if request.user.type != 'shop':
            return Response(Error.USER_TYPE_NOT_SHOP.value, status=403)

        # определяем привязанный к user магазин
        try:
            shop = request.user.shop
            serializer = ShopSerializer(shop)
            return Response(serializer.data)
        except backend.models.User.shop.RelatedObjectDoesNotExist:
            return Response(Error.USER_HAS_NO_SHOP.value, status=400)

    @swagger_auto_schema(request_body=PartnerStatePostSerializer)
    def post(self, request, *args, **kwargs):
        """
        Установить новый статус приема заказов магазином.

        В data необходимо передать новый статус True или False:

        {'state': 'True'}
        """

        # проверка авторизации
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Проверяем, что юзер == менеджер магазина
        if request.user.type != 'shop':
            return Response(Error.USER_TYPE_NOT_SHOP.value, status=403)

        new_state = request.data.get('state')
        if not new_state:
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

        # проверка, что передан корректный новый статус (True/False)
        try:
            new_state = bool(strtobool(new_state))
        except ValueError:
            return Response(Error.STATE_WRONG.value, status=400)

        # обновляем статус в БД
        shop = Shop.objects.filter(user_id=request.user.id)
        if shop:
            try:
                shop.update(state=new_state)
                return Response({'Status': True, 'new_state': new_state})
            except ValueError as error:
                return Response({'Status': False, 'Errors': str(error)})
        else:
            return Response(Error.USER_HAS_NO_SHOP.value, status=403)


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
class PartnerOrders(APIView):
    """
    Класс для работы с заказами магазина.
    """

    @swagger_auto_schema(manual_parameters=manual_parameters_orderpartner_get)
    def get(self, request, *args, **kwargs):
        """
        Просмотреть заказы магазина + фильтрация и поиск.

        Доступная параметризация запроса:

        'id' фильтр по номеру заказа
        'product' поиск по названию продукта (без учета регистра, частичное совпадение)
        'state' фильтр по статусу заказов
        'date' фильтр по дате 20XX-XX-XX, за определенный день
        'date_before' фильтр по дате 20XX-XX-XX, раньше чем указанная
        'date_after' фильтр по дате 20XX-XX-XX, начиная с указанной
        'sum_more' фильтр по сумме, заказы дороже value
        'sum_less' фильтр по сумме, заказы дешевле value
        'delivery_date_before' фильтр по дате доставки 20XX-XX-XX, раньше чем указанная
        'delivery_date_after' фильтр по дате доставки 20XX-XX-XX, начиная с указанной
        """

        # проверка авторизации
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Проверяем, что юзер == менеджер магазина
        if request.user.type != 'shop':
            return Response(Error.USER_TYPE_NOT_SHOP.value, status=403)

        # Настраиваем фильтрацию и поиск
        query = Q(ordered_items__product_info__shop__user_id=request.user.id)
        filter_kwargs = {}
        expected_query_params = [
            ('id', 'id'),  # фильтр по номеру заказа
            ('product', 'ordered_items__product_info__product__name__contains'),  # поиск по названию продукта
            ('state', 'state', True),  # фильтр по статусу заказов
            ('date', 'datetime__contains'),  # фильтр по дате 20XX-XX-XX, за определенный день
            ('date_before', 'datetime__lt'),  # фильтр по дате 20XX-XX-XX, раньше чем указанная
            ('date_after', 'datetime__gte'),  # фильтр по дате 20XX-XX-XX, начиная с указанной
            ('sum_more', 'total_sum__gte'),  # фильтр по сумме, заказы дороже value
            ('sum_less', 'total_sum__lte'),  # фильтр по сумме, заказы дешевле value
            ('delivery_date_before', 'delivery_date__lt'),  # фильтр по дате доставки 20XX-XX-XX, раньше чем указанная
            ('delivery_date_after', 'delivery_date__gte')  # фильтр по дате доставки 20XX-XX-XX, начиная с указанной
        ]
        for item in expected_query_params:
            arguments = [request]
            for i in item:
                arguments.append(i)
            filter_kwargs.update(query_filter_maker(*arguments))

        # сначала фильтруем + distinct(), чтобы корректно рассчиталась total_sum, потом по ней уже применяем
        # фильтры, иначе некорректная сумма, умножает на количество строк в заказе
        try:
            queryset = Order.objects.exclude(state='basket'). \
                filter(query).\
                distinct(). \
                annotate(total_sum=Sum(F('ordered_items__quantity') * F('ordered_items__product_info__price'))). \
                filter(**filter_kwargs). \
                select_related('user', 'contact').\
                prefetch_related('ordered_items__product_info__shop',
                                 'ordered_items__product_info__product__category').\
                order_by('-datetime')
        except ValidationError:
            return Response(Error.DATE_WRONG.value, status=400)

        serializer = OrderPartnerSerializer(queryset, many=True)
        return Response(serializer.data)

    @swagger_auto_schema(request_body=PartnerOrderPostSerializer)
    def post(self, request, *args, **kwargs):
        """
        Изменить статус заказа.

        В data необходимо передать id заказа и новый статус.
        При необходимости изменения также указывается новая дата/время доставки:

        {
        "id": 8,
        "state": "assembled",
        "delivery_date": "2024-01-12",
        "delivery_time": "evening_18_22"
        }

        **Варианты выбора интервалов доставки:**
        'morning_09_12',
        'afternoon_12_15',
        'afternoon_15_18',
        'evening_18_22',
        """

        # проверка авторизации
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Проверяем, что юзер == менеджер магазина
        if request.user.type != 'shop':
            return Response(Error.USER_TYPE_NOT_SHOP.value, status=403)

        order_id = request.data.get('id')
        new_state = request.data.get('state')

        # проверяем, что в data переданы все необходимые аргументы
        if not (order_id and new_state):
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

        # проверяем, что в data передан допустимый статус
        expected_states = sum(backend.models.ORDER_STATE_CHOICES[1:], tuple())
        if new_state not in expected_states:
            return Response(Error.STATE_WRONG.value, status=400)

        order = Order.objects.filter(ordered_items__product_info__shop__user=request.user, id=order_id)
        if not order:
            return Response(Error.ORDER_NOT_EXIST.value, status=400)

        # проверяем, передана ли новая дата доставки
        delivery_date = request.data.get('delivery_date')
        if delivery_date:
            if not re.fullmatch(reg_patterns.re_date, delivery_date):
                return Response(Error.DATE_WRONG.value, status=400)
        else:
            delivery_date = order.first().delivery_date

        # проверяем, передано ли новое время доставки
        delivery_time = request.data.get('delivery_time')
        if delivery_time:
            expected_delivery_time = [i[0] for i in backend.models.DELIVERY_TIME_CHOICES]
            if delivery_time not in expected_delivery_time:
                return Response(Error.DELIVERY_TIME_WRONG.value, status=400)
        else:
            delivery_time = order.delivery_time

        try:
            order.update(state=new_state,
                         delivery_date=delivery_date,
                         delivery_time=delivery_time)
        except ValidationError:
            return Response(Error.DATE_WRONG.value, status=400)

        # Сборщик ошибок
        error = {}

        # отправляем клиенту сообщение на email об изменении статуса его заказа
        try:
            new_order_state.send(self.__class__, order_id=order.first().id)
        except SMTPRecipientsRefused:
            error['Error'] = ValidateError.EMAIL_FAILED.value
        return Response({'Status': True, 'New_state': new_state, **error})


# noinspection PyUnresolvedReferences
# noinspection PyUnusedLocal
class PartnerUpdate(APIView):
    """
    Класс для управления остатками магазина, обновления прайса от поставщика
    """
    parser_classes = (MultiPartParser,)

    @swagger_auto_schema(request_body=PartnerUpdatePostSerializer, manual_parameters=manual_parameters_partnerupdate)
    def post(self, request, *args, **kwargs):
        """
        Полностью обновить складские остатки магазина, создать новый магазин.

        В yaml-файле (аргумент file) передается полный список остатков магазина.
        Все товары на остатках, не переданные в yaml, будут значиться с нулевым количеством.
        Новые товары будут добавлены, уже имеющиеся на остатках - обновлены согласно информации в yaml-файле.

        Для создания нового магазина в data необходимо передать url + прикрепить yaml-файл с остатками товара

        {
        "url": "http://bee.ru"
        }
        """

        # Проверка авторизации пользователя
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Проверяем, что юзер == менеджер магазина
        if request.user.type != 'shop':
            return Response(Error.USER_TYPE_NOT_SHOP.value, status=403)

        # Забираем данные из .yaml + проверяем, что передан файл формата .yaml
        file = request.data.get('file')
        if not file:
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)
        if file.name.split('.')[-1] != 'yaml':
            return Response(Error.FILE_INCORRECT.value, status=400)
        file_data = get_data_from_yaml_file(file)

        # Определяем магазин или создаем новый
        shop_name = file_data.get('shop')
        shop = Shop.objects.filter(name=shop_name, user=request.user).first()
        if not shop:
            url = request.data.get('url')
            if url:
                validate_url = URLValidator()
                try:
                    validate_url(url)   # делаем валидацию url для создания магазина
                except ValidationError as error:
                    return Response({'Status': False, 'Error': str(error)}, status=400)

                try:
                    shop = Shop.objects.create(name=file_data.get('shop'), user=request.user, url=url)
                except IntegrityError:
                    return Response(Error.SHOP_USER_NOT_RELATED.value, status=400)

            else:
                return Response(Error.URL_NOT_SPECIFIED.value, status=400)

        else:
            # сносим старую базу остатков, выставляя нулевые остатки
            ProductInfo.objects.filter(shop=shop.id).update(quantity=0)

        # сборщик ошибок
        counter = 0
        errors = {}
        errors_list = []
        shop_product_failed = 0
        category_failed = 0

        # загружаем новые категории из yaml
        create_categories(file_data.get('categories'), shop, category_failed, errors_list, errors)

        # забираем данные о товарах
        goods = file_data.get('goods')
        all_tasks = []  # для селери
        if goods:
            method = str(request.method)  # определяем http-метод для task
            for good in goods:
                task_er = {}
                task_er_list = []
                # товары загружаем параллельно в task
                task = task_load_good_from_yaml.delay(method, good, shop_name, task_er_list, task_er, counter)
                all_tasks.append(task.task_id)

            # забираем данные из отправленных tasks
            counter = get_data_from_all_tasks(all_tasks, counter, shop_product_failed, errors)[0]

        status = True if counter else False
        return Response({'Status': status, 'Загружено/обновлено товаров': counter, **errors})

    @swagger_auto_schema(manual_parameters=manual_parameters_partnerupdate)
    def patch(self, request, *args, **kwargs):
        """
        Принять новую поставку на склад, обновить цены, описание товаров.

        Текущие остатки склада суммируются с указанными в yaml-накладной.
        В yaml-файле (аргумент file) передается то, что поступает на склад, или переоценка/параметры товара.
        При переоценке/изменении описания без фактического привоза товару в накладной необходимо установить
        количество = 0.
        """

        # Проверка авторизации пользователя
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Проверяем, что юзер == менеджер магазина
        if request.user.type != 'shop':
            return Response(Error.USER_TYPE_NOT_SHOP.value, status=403)

        # Забираем данные из .yaml + проверяем, что передан файл формата .yaml
        file = request.data.get('file')
        if not file:
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)
        if file.name.split('.')[-1] != 'yaml':
            return Response(Error.FILE_INCORRECT.value, status=400)
        data = get_data_from_yaml_file(file)

        # сборщик ошибок
        counter = 0
        errors = {}
        errors_list = []
        shop_product_failed = 0
        category_failed = 0

        # Определяем магазин, с которым работаем (и что у user есть к нему доступ)
        shop_name = data['shop']
        shop = Shop.objects.filter(user=request.user, name=shop_name).first()
        if not shop:
            return Response(Error.SHOP_USER_NOT_RELATED.value, status=400)

        # Обновляем/добавляем категории в базу
        new_categories = data.get('categories')
        if new_categories:
            create_categories(new_categories, shop, category_failed, errors_list, errors)

        # забираем данные о товарах
        goods = data.get('goods')
        all_tasks = []  # для селери
        if goods:
            method = str(request.method)  # определяем http-метод для task
            for good in goods:
                task_er = {}
                task_er_list = []
                # товары загружаем параллельно в task
                good_task = task_load_good_from_yaml.delay(method, good, shop_name, task_er_list, task_er, counter)
                all_tasks.append(good_task.task_id)

            # забираем данные из отправленных tasks
            counter = get_data_from_all_tasks(all_tasks, counter, shop_product_failed, errors)[0]

        status = True if counter else False
        return Response({'Status': status, 'Загружено/обновлено товаров': counter, **errors})


# noinspection PyUnresolvedReferences
class PartnerBackup(APIView):
    """
    Класс для создания резервной копии остатков магазина и отправки файла с остатками на почту менеджера
    """

    def post(self, request):
        """
        Создать резервную копию остатков магазина.

        Файл с остатками отправляется на почту менеджера магазина.
        """

        # Проверка авторизации пользователя
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Проверяем, что юзер == менеджер магазина
        if request.user.type != 'shop':
            return Response(Error.USER_TYPE_NOT_SHOP.value, status=403)

        # определяем товары в магазине пользователя
        user = request.user
        all_goods_in_shop = ProductInfo.objects.filter(shop=user.shop)
        if not all_goods_in_shop:
            return Response(Error.SHOP_USER_NOT_RELATED.value, status=400)
        shop_name = all_goods_in_shop.first().shop.name

        # делаем бэкап базы магазина
        backup_shop_base.delay(shop_name)

        return Response({'Status': True})


# noinspection PyUnresolvedReferences
class PartnerReport(APIView):
    """
    Класс для отправки отчетов
    """

    @swagger_auto_schema(request_body=CreateReportSerializer)
    def post(self, request):
        """
        Сформировать отчет по товарам в заказах магазина за период.

        В data необходимо передать аргументы для определения временного интервала:
        {
        "from_date": "2024-01-01",
        "before_date": "2024-01-31"
        }

        Сформированный отчет будет отправлен на почту менеджеру магазина.
        """

        # Проверка авторизации пользователя
        if not request.user.is_authenticated:
            return Response(Error.USER_NOT_AUTHENTICATED.value, status=403)

        # Проверяем, что юзер == менеджер магазина
        if request.user.type != 'shop':
            return Response(Error.USER_TYPE_NOT_SHOP.value, status=403)

        # Проверяем, что переданы необходимые аргументы
        if not {'from_date', 'before_date'}.issubset(request.data):
            return Response(Error.NOT_REQUIRED_ARGS.value, status=400)

        from_date = request.data.get('from_date')
        before_date = request.data.get('before_date')
        user = request.user
        shop = user.shop

        # Делаем валидацию дат
        if not re.fullmatch(reg_patterns.re_date, from_date):
            return Response(Error.DATE_WRONG.value, status=400)
        if not re.fullmatch(reg_patterns.re_date, before_date):
            return Response(Error.DATE_WRONG.value, status=400)

        try:
            ordered = OrderItem.objects.exclude(order__state='basket').\
                filter(product_info__shop=shop, order__datetime__gte=from_date, order__datetime__lt=before_date).\
                annotate(total_sum=Sum(F('product_info__price') * F('quantity')))  # все заказанные позиции магазина
        except ValidationError as e:
            return Response({'Status': False, 'Errors': e}, status=400)

        # Формируем структуру данных для таблицы отчета
        data_structure = []
        names = []
        ordered_flat = []
        for i in ordered:
            list_ = [i.product_info.external_id, i.product_info.product.name, i.product_info.price, i.quantity,
                     i.total_sum]
            ordered_flat.append(list_)

        for i in ordered_flat:
            if i[1] not in names:
                data_structure.append(i)
                names.append(i[1])
            else:
                data_structure[names.index(i[1])][3] = data_structure[names.index(i[1])][3] + i[3]
                data_structure[names.index(i[1])][4] += i[4]
        total_sum = sum([i[4] for i in data_structure])  # общая сумма по всем позициям в заказе

        signal_kwargs = {
            'data_structure': data_structure,
            'total_sum': total_sum,
            'from_date': from_date,
            'before_date': before_date,
            'shop': user.shop.name,
            'email': user.email
        }
        send_report_task.delay(signal_kwargs)

        return Response({'Status': True, 'Отчет': 'Отправлен'})
