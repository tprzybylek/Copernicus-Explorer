from django.contrib import admin
from .models import Product, AdministrativeUnit

# Register your models here.


class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'satellite', 'ingestion_date', 'sensing_date', 'is_downloaded')


admin.site.register(Product, ProductAdmin)
admin.site.register(AdministrativeUnit)
