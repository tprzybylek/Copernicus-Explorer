from django.urls import path
from . import views

urlpatterns = [
    path('', views.search_form, name='search_form'),
    path('results/', views.results, name='search_results'),
    path('get_product/<str:product_id>/', views.get_product, name='search_get_product')
]
