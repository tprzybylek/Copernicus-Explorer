import os

from django.conf import settings
from django.contrib.gis.utils import LayerMapping
from .models import AdministrativeUnit

world_mapping = {
    'gml_id': 'gml_id',
    'unit_type': 'rodzajJednostki',
    'unit_code': 'kodJednostki',
    'unit_name': 'nazwaJednostki',
    'poly': 'MULTIPOLYGON',
}

world_shp = os.path.abspath(
    os.path.join(settings.BASE_DIR, 'data/shp/country.xml')
)


def run(verbose=True):
    lm = LayerMapping(
        AdministrativeUnit, world_shp, world_mapping,
        transform=True, encoding='iso-8859-1',
    )
    lm.save(strict=True, verbose=verbose)
