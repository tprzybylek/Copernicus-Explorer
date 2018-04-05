from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from order.models import Product
from .cart import Cart
from django.http import HttpResponse

# @require_POST

# Create your views here.


def cart_add(request):
    id = request.POST['id']
    cart = Cart(request)
    product = get_object_or_404(Product, id=id)
    cart.add(product)
    return HttpResponse("")
    # return redirect('cart_show_all')


def cart_remove(request):
    id = request.POST['id']
    cart = Cart(request)
    product = get_object_or_404(Product, id=id)
    cart.remove(product)
    return HttpResponse("")

def cart_clear(request):
    # TODO empty cart
    return HttpResponse("")


def cart_show_all(request):
    cart = Cart(request)
    cart_items = Product.objects.filter(id__in = cart.cart['products'])
    return render(request, 'order/cart.html', {'cart': cart_items})
