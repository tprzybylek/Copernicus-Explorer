from django.urls import path, include
from . import views

from rest_framework import routers

router = routers.DefaultRouter()
router.register('product', views.SearchView)

urlpatterns = [
    # path('', views.index, name='index'),
    path('results/', views.results, name='results'),
    path('', include(router.urls))
]