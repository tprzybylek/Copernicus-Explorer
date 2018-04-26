#Django
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.utils import timezone
from django.contrib.gis.geos import GEOSGeometry

#local
from search.models import Product
from .models import Order, ProductOrder
from .cart import Cart
from .forms import OrderForm


# Create your views here.

def cart_add(request):
    id = request.POST['id']
    cart = Cart(request)
    product = get_object_or_404(Product, id=id)
    cart.add(product)
    return HttpResponse("")


def cart_remove(request):
    id = request.POST['id']
    cart = Cart(request)
    product = get_object_or_404(Product, id=id)
    cart.remove(product)
    return HttpResponse("")


def cart_empty(request):
    cart = Cart(request)
    cart.empty()
    return HttpResponse("")


def cart_show_all(request):
    form = OrderForm()

    cart = Cart(request)
    cart_items = Product.objects.filter(id__in=cart.cart['products'])

    search_extent = cart.cart['extent']
    if search_extent is not None:
        search_extent = 'L.geoJSON(' \
                        + search_extent \
                        + ', {style: ' \
                          '{"color": "#000", ' \
                          '"weight": 1, ' \
                          '"fillOpacity": 0, ' \
                          '"dashArray": "10, 5"}' \
                          '}).addTo(map);'

    i_geom = []
    for item in cart_items:
        i_tuple = item.coordinates.tuple[0]
        i_tuple_coords = []
        for point in i_tuple:
            i_tuple_coords.append([point[1], point[0]])
        i_geom.append("L.polygon("
                      + str(i_tuple_coords)
                      + ", {className: '"
                      + item.id
                      + "', color: '#000', "
                        "weight: '1', "
                        "fillOpacity: '0.1'"
                        "}).addTo(map);")

    return render(request, 'order/cart.html', {'cart': cart_items,
                                               'items_geom': i_geom,
                                               'search_extent': search_extent,
                                               'form': form
                                               }
                  )


def order_confirm(request):
    if request.method == 'POST':
        form = OrderForm(request.POST)
        if form.is_valid():
            form_data = form.cleaned_data

            cart = Cart(request)
            order = {'e_mail': form_data['e_mail'],
                     'status': 0,
                     'ordered_date_time': timezone.now(),
                     'clip_extent': GEOSGeometry(cart.cart['extent']),
                     'products': cart.cart['products'],
                     }

            o = Order.objects.create(e_mail=form_data['e_mail'],
                                     status=0,
                                     ordered_date_time=timezone.now(),
                                     clip_extent=GEOSGeometry(cart.cart['extent'])
                                     )
            o.save()

            order['id'] = o.id

            for product in cart.cart['products']:
                po = ProductOrder.objects.create(product_id=Product.objects.get(id=product),
                                                 order_id=o
                                                 )
                po.save()

    return render(request, 'order/confirm.html', {'order': order})
