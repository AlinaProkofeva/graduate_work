from django_filters import CharFilter, NumberFilter, rest_framework

from backend.models import ProductInfo


def query_filter_maker(request, param_name: str, lookup: str, lower=False) -> dict:
    """
    Фильтры/поиск из параметров запроса для APIView

    Функция проверяет, есть ли в запросе предполагаемый в param_name query_params, если да, то забирает
    его значение и с заданным lookup_expr сохраняет в filter_kwargs

    :param request объект запроса
    :param param_name наименование параметра в строке запроса
    :param lookup параметр фильтрации
    :param lower регистр, по умолчанию False и применяется capitalize(). Если передано True, применится lower()
    """
    param = request.query_params.get(param_name)
    filter_kwargs = {}

    if param:
        param = param if lower else param.capitalize()
        lookup = {lookup: param}
        filter_kwargs = {'%s' % field: value for field, value in lookup.items()}

    return filter_kwargs


class ProductsFilter(rest_framework.FilterSet):
    """
    Фильтры для ProductInfoView (Просмотр и поиск товаров в магазинах)
    """

    # фильтр по id категории продуктов
    category_id = CharFilter(field_name='product', lookup_expr='category_id')

    # фильтр по частичному совпадению названия категории продуктов
    category = CharFilter(field_name='product', lookup_expr='category__name__icontains')

    # фильтр по цене больше или равно
    price_more = NumberFilter(field_name='price', lookup_expr='gte')

    # фильтр по цене меньше или равно
    price_less = NumberFilter(field_name='price', lookup_expr='lte')

    # фильтр по частичному совпадению названия магазина
    shop_name = CharFilter(field_name='shop__name', lookup_expr='icontains')

    class Meta:
        model = ProductInfo
        fields = ['shop_id', 'category_id', 'price_more', 'price_less', 'shop_name', 'category']
