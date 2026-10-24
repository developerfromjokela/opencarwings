// Run with: node --test ui/tests/car_location.test.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const helper = fs.readFileSync(path.join(__dirname, '../static/js/car_location.js'), 'utf8');
const template = fs.readFileSync(path.join(__dirname, '../templates/ui/car_detail.html'), 'utf8');
const helpers = vm.runInNewContext(helper + '\n({buildCarLocationLinks});');

test('Hungarian coordinates produce walking directions to the car, with no forced origin or navigation start', () => {
    const links = helpers.buildCarLocationLinks('47.5', '19.1');
    assert.equal(links.coordinates, '47.5, 19.1');
    const google = new URL(links.google);
    assert.equal(google.origin + google.pathname, 'https://www.google.com/maps/dir/');
    assert.equal(google.searchParams.get('api'), '1');
    assert.equal(google.searchParams.get('destination'), '47.5,19.1');
    assert.equal(google.searchParams.get('travelmode'), 'walking');
    assert.equal(google.searchParams.has('origin'), false);
    assert.equal(google.searchParams.has('dir_action'), false);
});

for (const [lat, lon] of [[0, 0], [0, 19.1], [47.5, 0], [-90, -180], [90, 180]]) {
    test(`valid zero/boundary coordinates ${lat},${lon}`, () => {
        assert.equal(helpers.buildCarLocationLinks(lat, lon).coordinates, `${lat}, ${lon}`);
    });
}
for (const value of [null, undefined]) {
    test(`missing coordinate ${String(value)} makes no URL`, () => {
        assert.equal(helpers.buildCarLocationLinks(value, 19.1), null);
        assert.equal(helpers.buildCarLocationLinks(47.5, value), null);
    });
}
test('preserves decimal strings supplied by the backend without losing precision', () => {
    const links = helpers.buildCarLocationLinks('47.1234567890', '19.9876543210');
    assert.equal(links.coordinates, '47.1234567890, 19.9876543210');
    assert.equal(new URL(links.google).searchParams.get('destination'), '47.1234567890,19.9876543210');
});

function uiContext(clipboard = {writeText: async () => {}}) {
    const elements = Object.fromEntries(['car-coordinates', 'car-location-copy-status', 'car-location-unavailable', 'car-location-actions', 'copy-car-coordinates', 'car-google-directions'].map(id => [id, {
        value: '', textContent: '', hidden: false, disabled: false,
        removeAttribute(name) { delete this[name]; }
    }]));
    const map = {views: [], removed: [], setView(point, zoom) {this.views.push({point: [...point], zoom});}, removeLayer(marker) {this.removed.push(marker);}};
    const context = vm.createContext({document: {getElementById: id => elements[id]}, navigator: {clipboard}, currentCarLocation: {}, marker: null, overviewMarker: null,
        L: {marker(point) {return {point: [...point], setLatLng(point) {this.point = [...point];}, addTo() {return this;}};}}
    });
    let source = template.slice(template.indexOf('        function updateCarLocation('), template.indexOf('        // Tab Switching with Map Fix'));
    source = source.replace('{{ coordinates_copied|escapejs }}', 'Coordinates copied.').replace('{{ coordinates_copy_failed|escapejs }}', 'Could not copy coordinates. Select and copy them manually.');
    vm.runInContext(helper + '\n' + source, context);
    return {context, elements, map};
}

test('shows selectable coordinates and a link, then removes stale actions when a fresh location is invalid', () => {
    const {context, elements} = uiContext();
    context.updateCarLocation({lat: 47.5, lon: 19.1});
    assert.equal(elements['car-coordinates'].value, '47.5, 19.1');
    assert.equal(elements['car-location-actions'].hidden, false);
    assert.equal(elements['car-location-unavailable'].hidden, true);
    elements['car-location-copy-status'].textContent = 'Coordinates copied.';
    context.updateCarLocation({lat: null, lon: 19.1});
    assert.equal(elements['car-coordinates'].value, '');
    assert.equal(elements['car-location-actions'].hidden, true);
    assert.equal(elements['car-location-unavailable'].hidden, false);
    assert.equal(elements['copy-car-coordinates'].disabled, true);
    assert.equal(elements['car-google-directions'].href, undefined);
    assert.equal(elements['car-location-copy-status'].textContent, '');
    context.updateCarLocation(null);
    assert.equal(elements['car-location-actions'].hidden, true);
    context.updateCarLocation({lat: 0, lon: 0});
    assert.equal(elements['car-coordinates'].value, '0, 0');
    assert.equal(elements['copy-car-coordinates'].disabled, false);
});
test('copy writes the displayed coordinates and announces success', async () => {
    let copied;
    const {context, elements} = uiContext({writeText: async value => {copied = value;}});
    context.updateCarLocation({lat: 47.5, lon: 19.1});
    await context.copyCarCoordinates();
    assert.equal(copied, '47.5, 19.1');
    assert.equal(elements['car-location-copy-status'].textContent, 'Coordinates copied.');
});
for (const clipboard of [undefined, {writeText: async () => {throw new Error('Denied');}}]) {
    test('unavailable or denied clipboard offers manual copying', async () => {
        const {context, elements} = uiContext(clipboard);
        context.navigator.clipboard = clipboard;
        context.updateCarLocation({lat: 47.5, lon: 19.1});
        await context.copyCarCoordinates();
        assert.match(elements['car-location-copy-status'].textContent, /Select and copy them manually/);
        assert.equal(elements['car-coordinates'].value, '47.5, 19.1');
    });
}
test('an old clipboard completion cannot announce success for a new car location', async () => {
    let done;
    const {context, elements} = uiContext({writeText: () => new Promise(resolve => {done = resolve;})});
    context.updateCarLocation({lat: 47.5, lon: 19.1});
    const copying = context.copyCarCoordinates();
    context.updateCarLocation({lat: 47.6, lon: 19.2});
    done();
    await copying;
    assert.equal(elements['car-location-copy-status'].textContent, '');
});
test('the actual map creates, moves, removes and recreates markers, including at zero', () => {
    const {context, map} = uiContext();
    let marker = context.updateMap(47.5, 19.1, map, null, 15);
    assert.deepEqual(marker.point, [47.5, 19.1]);
    const moved = context.updateMap(0, 0, map, marker, 15);
    assert.equal(moved, marker);
    assert.deepEqual(marker.point, [0, 0]);
    marker = context.updateMap(undefined, 19, map, marker, 15);
    assert.equal(marker, null);
    assert.equal(context.marker, null);
    assert.equal(map.removed.length, 1);
    assert.deepEqual(map.views.at(-1), {point: [0, 0], zoom: 2});
    marker = context.updateMap(-90, -180, map, marker, 15);
    assert.deepEqual(marker.point, [-90, -180]);
    let overview = context.updateMap(47, 19, map, null, 15, true);
    assert.equal(context.overviewMarker, overview);
    overview = context.updateMap(null, 19, map, overview, 15, true);
    assert.equal(overview, null);
    assert.equal(context.overviewMarker, null);
});
test('search-result map previews do not change the car coordinate controls', () => {
    const {context, elements, map} = uiContext();
    context.updateCarLocation({lat: 47.5, lon: 19.1});
    context.updateMap(48, 20, map, null, 16);
    assert.equal(elements['car-coordinates'].value, '47.5, 19.1');
    assert.equal(new URL(elements['car-google-directions'].href).searchParams.get('destination'), '47.5,19.1');
});
