var osmUrl = 'http://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
            osmAttrib = '&copy; <a href="http://openstreetmap.org/copyright">OpenStreetMap</a> contributors',
            osm = L.tileLayer(osmUrl, { maxZoom: 18, attribution: osmAttrib }),
            map = new L.Map('mapid', {center: new L.LatLng(52.07, 19.48), zoom: 5, minZoom: 5 }),
            drawnItems = L.featureGroup().addTo(map);

osm.addTo(map);


var drawControlDrawOnly = new L.Control.Draw({
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
});

var drawControlEditOnly = new L.Control.Draw({
    edit: {
        featureGroup: drawnItems,
        edit: false
    },
    draw: false
});

map.addControl(drawControlDrawOnly);

/*
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
*/


map.on(L.Draw.Event.CREATED, function(event) {
    var layer = event.layer;

    layer.addTo(drawnItems);
    //drawControlDrawOnly.removeFrom(map);
    //drawControlEditOnly.addTo(map)
    drawnItems.addLayer(layer);
    latLngs = layer.getLatLngs();

    var lats = []
    var lngs = []

    for (i = 0; i < latLngs[0].length; i++) {
        lats.push(latLngs[0][i].lat)
        lngs.push(latLngs[0][i].lng)
    }

    document.getElementById('id_search_extent_min_x').value = Math.min(...lngs)
    document.getElementById('id_search_extent_max_x').value = Math.max(...lngs)
    document.getElementById('id_search_extent_min_y').value = Math.min(...lats)
    document.getElementById('id_search_extent_max_y').value = Math.max(...lats)
});

/*
map.on("draw:created", function (e) {
    var layer = e.layer;

    layer.addTo(drawnItems);
    //drawControlDrawOnly.removeFrom(map);
    //drawControlEditOnly.addTo(map)
    drawnItems.addLayer(layer);

    alert(layer.getLatLngs());

});
*/
/*
map.on("draw:deleted", function (e) {
    drawControlEditOnly.removeFrom(map);
    drawControlFull.addTo(map);
});


map.on(L.Draw.Event.DELETED, function (e) {
    document.getElementById('extent_form').value = null;
});
*/