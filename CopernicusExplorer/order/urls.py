from django.urls import path

from . import views

urlpatterns = [
    path('cart/', views.cart_show_all, name='cart_show_all'),
    path('add/', views.cart_add, name='cart_add'),
    path('remove/', views.cart_remove, name='cart_remove'),
    path('empty/', views.cart_empty, name='cart_empty'),
    path('get_length', views.cart_get_length, name='cart_get_length'),
    path('confirm/', views.order_confirm, name='order_confirm'),
    path('<int:order_id>/', views.order_detail, name='order_detail'),
    path('get_order/<int:order_id>/', views.get_order, name='order_get_order'),
]
