from decimal import Decimal
from django.conf import settings
from order.models import Product


class Cart(object):

    def __init__(self, request):
        self.session = request.session
        cart = self.session.get(settings.CART_SESSION_ID)
        if not cart:
            cart = self.session[settings.CART_SESSION_ID] = {'products': []}
        self.cart = cart

    # def __iter__(self):

    def __len__(self):
        return len(self.cart['products'])

    def add(self, product):
        id = str(product.id)
        satellite = str(product.satellite)
        if product not in self.cart['products']:
            self.cart['products'].append(id)
        self.save()

    def remove(self, product):
        id = str(product.id)
        if id in self.cart['products']:
            self.cart['products'].remove(id)
            self.save()

    def save(self):
        self.session[settings.CART_SESSION_ID] = self.cart
        self.session.modified = True

    def clear(self):
        del self.session[settings.CART_SESSION_ID]
        self.session.modified = True
