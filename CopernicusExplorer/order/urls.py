from django.urls import path

from . import views

urlpatterns = [
    path('cart/', views.cart_show_all, name='cart_show_all'),
    path('add/', views.cart_add, name='cart_add'),
    path('remove/', views.cart_remove, name='cart_remove'),
    path('empty/', views.cart_empty, name='cart_empty'),
    path('confirm/', views.order_confirm, name='order_confirm'),
]
