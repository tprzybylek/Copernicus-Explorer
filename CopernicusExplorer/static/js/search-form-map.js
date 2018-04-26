var osmUrl = 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            osmAttrib = '&copy; <a href="http://openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            osm = L.tileLayer(osmUrl, { maxZoom: 18, attribution: osmAttrib }),
            map = new L.Map('mapid', {center: new L.LatLng(52.07, 19.48), zoom: 5, minZoom: 5 }),
            drawnItems = L.featureGroup().addTo(map);

osm.addTo(map);
map.addControl(new L.Control.Draw({
    draw: {
        featureGroup: drawnItems,
        polyline: false,
        polygon: false,
        circle: false,
        marker: false,
        circlemarker: false
    },
    edit: {
        featureGroup: drawnItems,
        edit: false
    }
}));

map.on(L.Draw.Event.CREATED, function(event) {
    var layer = event.layer;
    drawnItems.addLayer(layer);
});