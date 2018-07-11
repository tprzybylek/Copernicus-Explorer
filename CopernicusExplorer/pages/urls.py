from django.urls import path

from . import views

urlpatterns = [
    path('help/', views.pages_help, name='pages_help'),
    path('about/', views.pages_about, name='pages_about')
]
