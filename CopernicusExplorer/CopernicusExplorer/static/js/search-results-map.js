<div id="mapid">
    <script>
        var osmUrl = 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
        osmAttrib = '&copy; <a href="http://openstreetmap.org/copyright">OpenStreetMap</a> contributors',
        osm = L.tileLayer(osmUrl, { maxZoom: 18, attribution: osmAttrib }),
        map = new L.Map('mapid', {center: new L.LatLng(52.07, 19.48), zoom: 5, minZoom: 5 }),
        drawnItems = L.featureGroup().addTo(map);
        osm.addTo(map);
    </script>
</div>

