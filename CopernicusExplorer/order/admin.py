from django.contrib import admin

# Register your models here.

from .models import Order, ProductOrder


class OrderAdmin(admin.ModelAdmin):
    list_display = ('pk', 'ordered_date_time', 'completed_date_time', 'status')

admin.site.register(Order, OrderAdmin)
admin.site.register(ProductOrder)
