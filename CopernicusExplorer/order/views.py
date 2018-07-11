import os
from wsgiref.util import FileWrapper

# Django
from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, FileResponse
from django.utils import timezone
from django.contrib.gis.geos import GEOSGeometry
from django.conf import settings


# local
from search.models import Product
from .models import Order, ProductOrder
from .cart import Cart
from .forms import OrderForm

from order.tasks import perform_order


# Create your views here.

def cart_add(request):
    product_id = request.POST['id']
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
    cart.add(product)
    return HttpResponse("")


def cart_remove(request):
    product_id = request.POST['id']
    cart = Cart(request)
    product = get_object_or_404(Product, id=product_id)
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

    cart_type = None
    if cart_items.count() > 0:
        cart_type = cart_items.all().values('satellite')
        cart_type = [s['satellite'] for s in cart_type]
        cart_type = set(cart_type)

        cart_type = list(cart_type)[0][0:2]

    return render(request, 'order/cart.html', {'cart': cart_items,
                                               'cart_type': cart_type,
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
                                     layers=form_data['layers'],
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

                p = Product.objects.get(id=product)
                o.products.add(p)
                o.save()

            perform_order.delay(order['id'])
    return render(request, 'order/confirm.html', {'order': order})


def order_detail(request, order_id):
    order = Order.objects.get(id=order_id)

    order_details = {'id': order.pk,
                     'status': order.status,
                     'ordered_date_time': order.ordered_date_time,
                     'completed_date_time': order.completed_date_time,
                     'products': order.products.all()
                     }

    return render(request, 'order/detail.html', {'order': order_details})


def get_order(request, order_id):
    imagery_dir = os.path.join(settings.BASE_DIR, 'data/orders')
    file_path = os.path.join(imagery_dir, str(order_id) + '.zip')
    chunk_size = 8192

    response = FileResponse(
        FileWrapper(
            open(file_path, 'rb'),
            chunk_size
        ),
        content_type="application/octet-stream"
    )

    response['Content-Length'] = os.path.getsize(file_path)
    response['Content-Disposition'] = "attachment; filename=%s" % str(order_id) + '.zip'

    return response
