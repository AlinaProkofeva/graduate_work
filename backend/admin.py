from django.contrib import admin
from django.utils.safestring import mark_safe
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.admin import TokenProxy

from backend.forms import ShopForm, OrderItemInLineFormset, OrderForm, UserForm, ContactForm, AddressForm, RatingForm, \
    ProductPhotoInLineFormset
from backend.models import Order, Category, Product, Parameter, ProductParameter, Contact, Shop, ProductInfo, \
    OrderItem, User, ConfirmEmailToken, Address, RatingProduct, ProductInfoPhoto

# убираем автоматически создаваемую таблицу с токенами, ниже сделаем кастомную
admin.site.unregister(TokenProxy)


@admin.register(RatingProduct)
class RatingProductAdmin(admin.ModelAdmin):
    """Рейтинг и отзыв на товар"""
    list_display = ['id', 'product', 'rating', 'user']
    list_display_links = ['id', 'product']
    search_fields = ['product__product__name', 'review']
    list_filter = ['rating']
    form = RatingForm


@admin.register(Token)
class TokenAdmin(admin.ModelAdmin):
    """Auth-токены пользователей"""
    list_display = ['key', 'user', 'created']
    list_display_links = ['key', 'user']
    search_fields = ['user__first_name', 'user__last_name']


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    """Пользователи"""
    # list_display = ['email', 'type', 'avatar', 'first_name', 'last_name', 'is_active', 'is_superuser']
    list_display = ['email', 'type', 'get_html_thumbnail', 'first_name', 'last_name', 'is_active', 'is_superuser']
    list_editable = ['is_active', 'is_superuser']
    list_filter = ['is_active', 'type', 'is_superuser']
    search_fields = ['email', 'first_name', 'last_name']
    form = UserForm
    fields = ['get_html_photo', 'first_name', 'last_name', 'date_joined', 'email', 'company', 'position', 'is_active',
              'type', 'avatar_thumbnail']
    readonly_fields = ['get_html_photo', 'date_joined']

    def get_html_thumbnail(self, object):
        """Отображение в админке миниатюры аватара, а не ссылки"""
        if object.avatar_thumbnail:
            return mark_safe(f'<img src="{object.avatar_thumbnail.url}" width=50 height=65')

    def get_html_photo(self, object):
        """Отображение в админке в профиле пользователя аватарки"""
        if object.avatar_thumbnail:
            return mark_safe(f'<img src="{object.avatar_thumbnail.url}"')

    get_html_thumbnail.short_description = 'Аватарка'
    get_html_photo.short_description = 'Аватар'


@admin.register(ConfirmEmailToken)
class ConfirmEmailTokenAdmin(admin.ModelAdmin):
    """Токены подтверждения email пользователей"""
    list_display = ['user', 'token']
    list_display_links = ['user', 'token']
    search_fields = ['user__first_name', 'user__last_name']


class ProductParameterInLine(admin.TabularInline):
    """Характеристики товара с указанием значения"""
    model = ProductParameter
    extra = 1


class OrderItemInLine(admin.TabularInline):
    """
    Заказанные товары с указанием количества.
    В formset настроен запрет на добавление в один заказ товаров из разных магазинов
    """
    model = OrderItem
    extra = 0
    formset = OrderItemInLineFormset


class CatsInline(admin.TabularInline):
    """Категории товаров в магазине"""
    model = Category.shops.through
    extra = 0


@admin.register(Shop)
class ShopAdmin(admin.ModelAdmin):
    """Информация о магазине с перечнем категорий товаров"""
    list_display = ['id', 'name', 'url', 'state', 'user']
    list_display_links = ['name', 'url']
    search_fields = ['name']
    list_filter = ['state']
    list_editable = ['state']
    inlines = [CatsInline]
    form = ShopForm


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    """Информация о заказе с перечнем выбранных товаров и их количеством"""
    list_display = ['id', 'datetime', 'user', 'state', 'delivery_date', 'delivery_time']
    list_display_links = ['datetime']
    inlines = [OrderItemInLine]
    list_filter = ['state', 'datetime', 'delivery_date']
    search_fields = ['id', 'user__first_name', 'user__last_name']
    form = OrderForm
    fieldsets = (
        (None, {'fields': ('user', 'state')}),
        ('Информация о доставке',
         {'fields': ('contact', 'delivery_date', 'delivery_time', 'recipient_full_name')})
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Категории товаров"""
    list_display = ['id', 'name']
    list_display_links = ['id', 'name']
    search_fields = ['name']
    exclude = ['shops']


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """Связь Категория - Наименование продукта"""
    list_display = ['id', 'name', 'category']
    list_display_links = ['id', 'name', 'category']
    search_fields = ['name', 'category']
    list_filter = ['category']


@admin.register(Parameter)
class ParameterAdmin(admin.ModelAdmin):
    """Характеристики для описания товаров"""
    list_display = ['id', 'name']
    list_display_links = ['id', 'name']
    search_fields = ['name']


class AddressInline(admin.TabularInline):
    model = Address
    extra = 0
    form = AddressForm


@admin.register(Contact)
class ContactAdmin(admin.ModelAdmin):
    """Контактные данные клиента для доставки"""
    list_display = ['id', 'user', 'phone']
    list_display_links = ['id', 'user']
    search_fields = ['id', 'user__first_name', 'user__last_name', 'phone']
    form = ContactForm
    inlines = [AddressInline, ]


class PhotoInline(admin.TabularInline):
    """Инлайн с изображениями товара и определением главной иконки для отображения в списке"""
    model = ProductInfoPhoto
    extra = 0
    readonly_fields = ['image_preview', ]
    fields = ['image_preview', 'is_main', 'photo']
    formset = ProductPhotoInLineFormset

    def image_preview(self, obj):
        """Отображение фото в инлайне вместо url"""
        if obj.photo:
            return mark_safe(f'<img src="{obj.photo_small.url}"')

    image_preview.short_description = 'Фото'


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    """Связь Товар - Магазин, остатки на конкретных складах с магазинным артикулом, названием
    модели, количеством, ценой, рекомендуемой розничной ценой и характеристиками товара"""
    list_display = ['id', 'product', 'external_id', 'price', 'shop', 'quantity']
    list_display_links = ['id', 'product']
    search_fields = ['model', 'product__name', 'external_id']
    list_filter = ['shop']
    inlines = [ProductParameterInLine, PhotoInline]
    fieldsets = (
        ('Информация о товаре', {
            'fields': ('product', 'description', 'model', 'external_id')
        }),
        ('Информация о наличии и стоимости', {
            'fields': ('shop', 'quantity', 'price', 'price_rrc')
        })
    )


# @admin.register(ProductInfoPhoto)   # в инлайне информации о товаре в магазине
# class ProductInfoPhotoAdmin(admin.ModelAdmin):
#     list_display = ['id', 'get_html_photo_icon', 'is_main', 'product']
#     list_display_links = ['id', 'product']
#     fields = ['get_html_photo', 'product', 'is_main', 'photo']
#     readonly_fields = ['get_html_photo']
#
#     def get_html_photo_icon(self, object):
#         """Отображение иконки в списке админки"""
#         if object.photo:
#             return mark_safe(f'<img src="{object.photo_small.url}"')
#
#     def get_html_photo(self, object):
#         """Отображение фото товара крупным планом"""
#         if object.photo:
#             return mark_safe(f'<img src="{object.photo_large.url}"')
#
#     get_html_photo_icon.short_description = 'Изображение'
#     get_html_photo.short_description = 'Изображение'
