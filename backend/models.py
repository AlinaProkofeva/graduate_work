from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from django.db.models import Sum, F
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator, MinLengthValidator, URLValidator
from django_rest_passwordreset.tokens import get_token_generator
from datetime import date, timedelta


# Варианты статуса заказа клиента
ORDER_STATE_CHOICES = (
    # заказы в статусе с элементом [0] - недопустимы к просмотру/изменению менеджером партнера
    # в class PartnerOrders(APIView)
    ('basket', 'В корзине'),
    ('new', 'Новый'),
    ('confirmed', 'Подтверждён'),
    ('assembled', 'Собран'),
    ('sent', 'Отправлен'),
    ('delivered', 'Доставлен'),
    ('canceled', 'Отменен'),
)

# Варианты типа пользователя - менеджер магазина или покупатель
USER_TYPE_CHOICES = (
    ('shop', 'Магазин'),
    ('buyer', 'Покупатель')
)

# Варианты интервалов времени доставки
DELIVERY_TIME_CHOICES = (
    ('morning_09_12', '09:00 - 12:00'),
    ('afternoon_12_15', '12:00 - 15:00'),
    ('afternoon_15_18', '15:00 - 18:00'),
    ('evening_18_22', '18:00 - 22:00')
)

# Варианты оценки товара
RATING_PRODUCT_CHOICES = (
    ('1', '1 звезда'),
    ('2', '2 звезды'),
    ('3', '3 звезды'),
    ('4', '4 звезды'),
    ('5', '5 звезд')
)


class UserManager(BaseUserManager):
    """Управление созданием модели пользователя с email вместо username в качестве идентификатора User"""

    use_in_migrations = True

    def _creation(self, email, password, **extra_fields):
        """Создание объекта модели User с необходимыми установленными extra"""

        if not email:
            raise ValueError(_('The Email must be set'))
        email = self.normalize_email(email)

        # Для авторизации через vk. После необходимо сменить почту в аккаунте
        # при авторизации через vk пользователь сразу активен, подтверждение письмом не требуется
        if email == 'example@mail.ru':
            extra_fields.setdefault('is_active', True)
            email = extra_fields['username']

        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)

        return user

    def create_user(self, email=None, password=None, **extra_fields):
        """установка необходимых extra + вызов self._creation() для создания пользователя"""

        if email == '':
            email = 'example@mail.ru'  # для авторизации через vk

        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)

        return self._creation(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """установка необходимых для superuser параметров + активация и роль менеджера + вызов self._creation()"""

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        extra_fields.setdefault('type', 'shop')

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Superuser must have is_staff=True.'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(_('Superuser must have is_superuser=True.'))

        return self._creation(email, password, **extra_fields)


class User(AbstractUser):
    """Кастомизированный пользователь"""

    REQUIRED_FIELDS = []
    objects = UserManager()  # при создании объектов использует валидацию и методы из этого миксина
    USERNAME_FIELD = 'email'  # задаем уникальный идентификатор
    email = models.EmailField(_('email address'),
                              unique=True)
    company = models.CharField(max_length=40,
                               blank=True,
                               verbose_name='Компания')
    position = models.CharField(max_length=40,
                                blank=True,
                                verbose_name='Должность')
    username = models.CharField(_('username'),
                                max_length=150,
                                blank=True)
    is_active = models.BooleanField(_('active'),
                                    default=False)
    type = models.CharField(choices=USER_TYPE_CHOICES,
                            max_length=5,
                            default='buyer')
    # contacts - контакты пользователя
    # shop - связанный магазин
    # confirm_email_token - токен активации пользователя
    # ratings - оценки и отзывы пользователя

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ('email', )

    def __str__(self):
        return f'{self.first_name} {self.last_name}'


class ConfirmEmailToken(models.Model):
    """Токены подтверждения email пользователей для активации"""

    user = models.ForeignKey(User,
                             related_name='confirm_email_token',
                             on_delete=models.CASCADE,
                             verbose_name='Пользователь')
    created_at = models.DateTimeField(auto_now_add=True,
                                      verbose_name=_("When was this token generated"))
    token = models.CharField(max_length=64,
                             db_index=True,
                             unique=True,
                             verbose_name='Токен подтверждения')

    @staticmethod
    def generate_token():
        """ generates a pseudo random code using os.urandom and binascii.hexlify """
        return get_token_generator().generate_token()

    def save(self, *args, **kwargs):
        """Создание токена пользователю"""
        if not self.token:
            self.token = self.generate_token()
        return super(ConfirmEmailToken, self).save(*args, **kwargs)

    def __str__(self):
        return f'Токен {self.token} подтверждения email для пользователя {self.user}'

    class Meta:
        verbose_name = 'Токен подтверждения Email'
        verbose_name_plural = 'Токены подтверждения Email'


class Shop(models.Model):
    """Магазины"""

    name = models.CharField(max_length=50,
                            unique=True,
                            verbose_name='Название')
    url = models.URLField(null=True,
                          blank=True,
                          validators=[URLValidator()],
                          verbose_name='Ссылка')
    state = models.BooleanField(default=True,
                                verbose_name='Статус получения заказов')
    user = models.OneToOneField(User,
                                on_delete=models.CASCADE,
                                related_name='shop',
                                null=True,
                                blank=True,
                                verbose_name='Пользователь')
    # product_info - м2м связь с магазинами, остатки на складах
    # categories - категории товаров в магазине

    class Meta:
        verbose_name = 'Магазин'
        verbose_name_plural = 'Магазины'
        ordering = ('name', )

    def __str__(self):
        return self.name


class Category(models.Model):
    """Категория товара - Смартфоны, Аксессуары, USB-накопители и т.д."""

    name = models.CharField(verbose_name='Название',
                            max_length=50,
                            unique=True)
    shops = models.ManyToManyField(Shop,
                                   related_name='categories',
                                   blank=True,
                                   verbose_name='Магазины')

    class Meta:
        verbose_name = 'Категория товара'
        verbose_name_plural = 'Категории товаров'
        ordering = ('name',)

    def __str__(self):
        return self.name


class Product(models.Model):
    """Связь Категории товара с наименованием Продукта"""

    name = models.CharField(max_length=80,
                            verbose_name='Наименование')
    category = models.ForeignKey(Category,
                                 on_delete=models.CASCADE,
                                 related_name='products',
                                 blank=True,
                                 verbose_name='Категория')
    # product_info - м2м связь с магазинами, остатки на складах

    class Meta:
        verbose_name = 'Продукт'
        verbose_name_plural = 'Продукты'
        ordering = ('name',)
        unique_together = ('category', 'name')

    def __str__(self):
        return f'{self.name}, {self.category}'


class ProductInfo(models.Model):
    """
    Промежуточная таблица Продукт-Магазин, остатки на конкретных складах с магазинным артикулом, названием
    модели, количеством, ценой и рекомендуемой розничной ценой
    """

    product = models.ForeignKey(Product,
                                on_delete=models.CASCADE,
                                related_name='product_info',
                                blank=True,
                                verbose_name='Продукт')
    description = models.TextField(blank=True,
                                   null=True,
                                   verbose_name='Описание товара')
    shop = models.ForeignKey(Shop,
                             on_delete=models.CASCADE,
                             related_name='product_info',
                             blank=True,
                             verbose_name='Магазин')
    quantity = models.PositiveIntegerField(verbose_name='Количество')
    external_id = models.PositiveIntegerField(verbose_name='Артикул товара')
    model = models.CharField(max_length=80,
                             blank=True,
                             verbose_name='Модель')
    price = models.PositiveIntegerField(verbose_name='Цена')
    price_rrc = models.PositiveIntegerField(verbose_name='Рекомендуемая розничная цена')
    # product_parameters - m2m связь с характеристиками
    # ratings - m2m связь с отзывами

    class Meta:
        verbose_name = 'Информация о продукте'
        verbose_name_plural = 'Информация о продуктах в магазинах с характеристиками'
        unique_together = ('shop', 'external_id')

    def __str__(self):  # для админки и писем
        return f'{self.product}, "{self.shop}", цена: {self.price}'


class Parameter(models.Model):
    """Перечень возможных характеристик для описания продуктов"""
    name = models.CharField(max_length=80,
                            unique=True,
                            verbose_name='Название')
    # product_parameters - m2m связь с характеристиками и продуктами

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = 'Параметры'
        ordering = ('name',)

    def __str__(self):
        return self.name


class ProductParameter(models.Model):
    """Описание параметров товара: товар-характеристика-значение"""

    product = models.ForeignKey(ProductInfo,
                                related_name='product_parameters',
                                on_delete=models.CASCADE,
                                blank=True,
                                verbose_name='Продукт')
    parameter = models.ForeignKey(Parameter,
                                  related_name='product_parameters',
                                  on_delete=models.CASCADE,
                                  blank=True,
                                  verbose_name='Параметр')
    value = models.CharField(max_length=100,
                             verbose_name='Значение')

    class Meta:
        verbose_name = 'Параметр'
        verbose_name_plural = 'Параметры товара'
        unique_together = ('product', 'parameter')

    def __str__(self):
        return f'{self.parameter}'


class RatingProduct(models.Model):
    """Оценка товара и отзывы от покупателей"""

    product = models.ForeignKey(ProductInfo,
                                related_name='ratings',
                                on_delete=models.CASCADE,
                                verbose_name='Товар')
    rating = models.CharField(max_length=1,
                              choices=RATING_PRODUCT_CHOICES,
                              verbose_name='Рейтинг')
    user = models.ForeignKey(User,
                             related_name='ratings',
                             on_delete=models.CASCADE,
                             verbose_name='Пользователь')
    review = models.TextField(verbose_name='Отзыв о товаре',
                              blank=True,
                              null=True)

    class Meta:
        verbose_name = 'Рейтинг товара'
        verbose_name_plural = 'Рейтинг товара'
        unique_together = ('product', 'user')

    def __str__(self):
        return self.rating


class Contact(models.Model):
    """Контактные данные для создания заказа"""

    user = models.OneToOneField(User,
                                related_name='contacts',
                                on_delete=models.CASCADE,
                                verbose_name='Пользователь')
    phone = models.CharField(max_length=10,
                             validators=[MinLengthValidator(10)],
                             verbose_name='Телефон')
    # addresses - o2m-связь с адресами

    class Meta:
        verbose_name = 'Контактные данные пользователя'
        verbose_name_plural = 'Контактные данные пользователей'

    def __str__(self):
        return f'{self.user}, {self.phone}'


# noinspection PyUnresolvedReferences
class Address(models.Model):
    """Адреса контактов пользователей"""

    contact = models.ForeignKey(Contact,
                                related_name='addresses',
                                on_delete=models.CASCADE,
                                verbose_name='Контакт пользователя')
    region = models.CharField(max_length=50,
                              verbose_name='Регион')
    district = models.CharField(max_length=50,
                                blank=True,
                                verbose_name='Район')
    settlement = models.CharField(max_length=50,
                                  blank=True,
                                  verbose_name='Населенный пункт')
    street = models.CharField(max_length=100,
                              verbose_name='Улица')
    house = models.CharField(max_length=15,
                             blank=True,
                             verbose_name='Дом')
    structure = models.CharField(max_length=15,
                                 blank=True,
                                 verbose_name='Корпус')
    building = models.CharField(max_length=15,
                                blank=True,
                                verbose_name='Строение')
    apartment = models.CharField(max_length=15,
                                 blank=True,
                                 verbose_name='Квартира')

    class Meta:
        verbose_name = 'Адрес пользователя'
        verbose_name_plural = 'Адреса пользователя'
        unique_together = ('contact', 'region', 'district', 'settlement', 'street', 'house', 'structure', 'building',
                           'apartment')

    def __str__(self):
        return f'id {self.id}, {self.contact.user} {self.region} {self.district} {self.settlement}, {self.street}, ' \
               f'{self.house}'


# noinspection PyUnresolvedReferences
class Order(models.Model):
    """Клиентский заказ товара"""

    user = models.ForeignKey(User,
                             related_name='orders',
                             on_delete=models.CASCADE,
                             blank=True,
                             verbose_name='Пользователь')
    datetime = models.DateTimeField(auto_now_add=True,
                                    verbose_name='Дата и время создания заказа')
    state = models.CharField(max_length=30,
                             choices=ORDER_STATE_CHOICES,
                             verbose_name='Статус заказа',
                             default='new')
    contact = models.ForeignKey(Address,
                                on_delete=models.CASCADE,
                                blank=True,
                                null=True,
                                verbose_name='Адрес доставки')
    # доставка возможна не ранее, чем на следующий день, может быть изменена поставщиком при подтверждении заказа
    delivery_date = models.DateField(verbose_name='Дата доставки',
                                     blank=True,
                                     null=True,
                                     default=date.today() + timedelta(days=1),
                                     validators=[MinValueValidator(date.today() + timedelta(days=1))])
    delivery_time = models.CharField(verbose_name='Время доставки',
                                     choices=DELIVERY_TIME_CHOICES,
                                     blank=True,
                                     null=True,
                                     default='morning_09_12',
                                     max_length=30)
    recipient_full_name = models.CharField(verbose_name='ФИО получателя',
                                           blank=True,
                                           null=True,
                                           max_length=50)
    # ordered_items - наполнение заказа через м2м таблицу OrderItem

    class Meta:
        verbose_name = 'Заказ'
        verbose_name_plural = 'Заказы'
        ordering = ('-datetime',)

    def total_sum(self):  # возвращает словарь {'total': sum}
        return self.ordered_items.aggregate(total=Sum(F('quantity') * F('product_info__price')))

    def __str__(self):
        return f'{self.datetime.strftime("%Y-%m-%d %H:%M:%S")}'


class OrderItem(models.Model):
    """Промежуточная таблица для связи заказов с продуктами в нужном количестве"""

    product_info = models.ForeignKey(ProductInfo,
                                     related_name='ordered_items',
                                     on_delete=models.CASCADE,
                                     blank=True,
                                     verbose_name='Информация о продукте')
    order = models.ForeignKey(Order,
                              related_name='ordered_items',
                              on_delete=models.CASCADE,
                              blank=True,
                              verbose_name='Заказ')
    quantity = models.PositiveIntegerField(default=1,
                                           verbose_name='Количество')

    class Meta:
        verbose_name = 'Заказанная позиция'
        verbose_name_plural = 'Список заказанных позиций'
        unique_together = ('order', 'product_info')

    def __str__(self):
        return f'{self.product_info}'
