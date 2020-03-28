from django.contrib import admin
from .models import Product, AdministrativeUnit, UpdateLog

# Register your models here.


class ProductAdmin(admin.ModelAdmin):
    list_display = ('id', 'satellite', 'ingestion_date', 'sensing_date', 'is_downloaded')

class UpdateLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'log_date', 'status')

admin.site.register(Product, ProductAdmin)
admin.site.register(AdministrativeUnit)
admin.site.register(UpdateLog, UpdateLogAdmin)
