from django.shortcuts import render
from rest_framework import viewsets

from .models import Product
from .serializers import SearchSerializer

from django.http import HttpResponse

# Create your views here.

def index(request):
    return render(request, 'search/form.html')

def results(request):
    return render(request, 'search/results.html')

class SearchView(viewsets.ModelViewSet):
    queryset = Product.objects.all()
    serializer_class = SearchSerializer