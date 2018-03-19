from django.urls import path
from . import views

urlpatterns = [
    path('', views.search_form, name='search'),
    path('results/', views.results, name='results'),
]