"""shop_site URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import debug_toolbar
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
# noinspection PyUnresolvedReferences
from django.urls import re_path as url

from backend.views import CategoryView, ShopView, ProductInfoView, PartnerState, PartnerOrders, ContactView, \
    OrderView, BasketView, PartnerUpdate, RegisterAccount, ConfirmAccount, AccountDetails, LoginAccount, \
    LogoutAccount, MyResetPasswordRequestToken, MyResetPasswordConfirm, ProductInfoDetailView, \
    OrderDetailView, RateProduct, PartnerBackup
from .yasg import urlpatterns as doc_urls


urlpatterns = [
    path('admin/', admin.site.urls),
    path('__debug__/', include(debug_toolbar.urls)),

    path('categories/', CategoryView.as_view(), name='categories'),
    path('shops/', ShopView.as_view(), name='shops'),
    path('products/', ProductInfoView.as_view(), name='products'),
    path('products/<int:pk>/', ProductInfoDetailView.as_view(), name='product_detail'),
    path('products/rate/', RateProduct.as_view(), name='rate_product'),
    path('basket/', BasketView.as_view(), name='basket'),
    path('order/', OrderView.as_view(), name='order'),
    path('order/<int:pk>/', OrderDetailView.as_view(), name='order_detail'),

    path('user/register/', RegisterAccount.as_view(), name='user_register'),
    path('user/register/confirm/', ConfirmAccount.as_view(), name='user_register_confirm'),
    path('user/login/', LoginAccount.as_view(), name='user_login'),
    path('user/logout/', LogoutAccount.as_view(), name='user_logout'),
    path('user/register_vk/', include('rest_framework_social_oauth2.urls')),  # /user/register_vk/convert-token/
    path('user/password_reset/', MyResetPasswordRequestToken.as_view(), name='password_reset'),
    path('user/password_reset/confirm/', MyResetPasswordConfirm.as_view(), name='password_reset_confirm'),
    path('user/details/', AccountDetails.as_view(), name='user_details'),
    path('user/contact/', ContactView.as_view(), name='user_contact'),

    path('partner/state/', PartnerState.as_view(), name='partner_state'),
    path('partner/orders/', PartnerOrders.as_view(), name='partner_orders'),
    path('partner/update/', PartnerUpdate.as_view(), name='partner_update'),
    path('partner/backup/', PartnerBackup.as_view(), name='partner_backup'),
]

urlpatterns += doc_urls

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
