from django.contrib import admin
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.admin import TokenProxy

from backend.forms import ShopForm, OrderItemInLineFormset, OrderForm, UserForm, ContactForm, AddressForm, RatingForm
from backend.models import Order, Category, Product, Parameter, ProductParameter, Contact, Shop, ProductInfo, \
    OrderItem, User, ConfirmEmailToken, Address, RatingProduct

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
    list_display = ['email', 'type', 'first_name', 'last_name', 'is_active', 'is_superuser']
    list_editable = ['is_active', 'is_superuser']
    list_filter = ['is_active', 'type', 'is_superuser']
    search_fields = ['email', 'first_name', 'last_name']
    exclude = ['password', 'groups', 'is_staff', 'user_permissions', 'is_superuser', 'last_login']
    form = UserForm


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


@admin.register(ProductInfo)
class ProductInfoAdmin(admin.ModelAdmin):
    """Связь Товар - Магазин, остатки на конкретных складах с магазинным артикулом, названием
    модели, количеством, ценой, рекомендуемой розничной ценой и характеристиками товара"""
    list_display = ['id', 'product', 'external_id', 'price', 'shop', 'quantity']
    list_display_links = ['id', 'product']
    search_fields = ['model', 'product__name', 'external_id']
    list_filter = ['shop']
    inlines = [ProductParameterInLine]
    fieldsets = (
        ('Информация о товаре', {
            'fields': ('product', 'description', 'model', 'external_id')
        }),
        ('Информация о наличии и стоимости', {
            'fields': ('shop', 'quantity', 'price', 'price_rrc')
        })
    )
