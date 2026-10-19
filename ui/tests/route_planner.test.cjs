// Run with: node --test ui/tests/route_planner.test.cjs
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const {test} = require('node:test');
const normalize = vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../static/js/route_planner.js'), 'utf8') + '\nnormalizeRoutePlanLocation;');
const fallback = 'Location';
const longName = 'Árvíztűrő tükörfúrógép látogatóközpont és parkoló';

test('long Hungarian POI keeps its full display label and bounds the protocol name', () => {
    const result = normalize({name: longName, address: 'Budapest, Fő utca 12.'}, fallback);
    assert.equal(result.name, Array.from(longName).slice(0, 30).join(''));
    assert.equal(result.label, longName + ', Budapest, Fő utca 12.');
});
for (const length of [30, 31]) {
    test(`${length} character boundary`, () => {
        assert.equal(normalize({name: 'ő'.repeat(length)}, fallback).name, 'ő'.repeat(30));
    });
}
test('POI without address never renders null', () => {
    const result = normalize({name: 'Smart Parking', address: null}, fallback);
    assert.equal(result.name, 'Smart Parking');
    assert.equal(result.label, 'Smart Parking');
});
test('structured address without POI uses road and house number', () => {
    const result = normalize({address: {road: 'Fő utca', house_number: '12', city: 'Budapest', country: 'Magyarország'}}, fallback);
    assert.equal(result.name, 'Fő utca 12');
    assert.equal(result.label, 'Fő utca 12, Budapest, Magyarország');
});
test('road name from Nominatim also retains the house number', () => {
    assert.equal(normalize({name: 'Fő utca', address: {road: 'Fő utca', house_number: '12'}}, fallback).name, 'Fő utca 12');
});
test('resolved link address without POI is usable', () => {
    const result = normalize({name: null, address: 'Budapest, Fő utca 12.'}, fallback);
    assert.equal(result.name, 'Budapest, Fő utca 12.');
    assert.equal(result.label, result.name);
});
test('Nominatim display_name and other address parts are usable fallbacks', () => {
    assert.equal(normalize({display_name: 'Budapest, Magyarország'}, fallback).name, 'Budapest, Magyarország');
    assert.equal(normalize({address: {village: 'Tihany'}}, fallback).name, 'Tihany');
});
for (const name of [null, undefined, '', '  ', 'null', 'undefined', ' NULL ']) {
    test(`missing/sentinel name ${JSON.stringify(name)} uses translated fallback`, () => {
        const result = normalize({name}, 'Helyszín');
        assert.equal(result.name, 'Helyszín');
        assert.equal(result.label, 'Helyszín');
    });
}
test('normalizes whitespace and Unicode without splitting surrogate pairs', () => {
    assert.equal(normalize({name: '  Fo\u030b\n utca  '}, fallback).name, 'Fő utca');
    assert.equal(Array.from(normalize({name: '🚘'.repeat(31)}, fallback).name).length, 30);
});
test('equal POI/address is displayed once and input is not mutated', () => {
    const location = Object.freeze({name: 'Budapest', address: 'Budapest'});
    assert.equal(normalize(location, fallback).label, 'Budapest');
});

function formContext() {
    const template = fs.readFileSync(path.join(__dirname, '../templates/ui/car_detail.html'), 'utf8');
    const source = template.slice(template.indexOf('        function updateCurrentRoutePlanFromForm()'), template.indexOf('        function routePlanPointSearch('))
        .replace(/{{ route_location_label\|escapejs }}/g, 'Location')
        .replace(/{{ route_point_error\|escapejs }}/g, 'Select a location for this point before saving.')
        .replace(/{% translate ["']([^"']+)["'] %}/g, '$1');
    const fields = ['rp-start', 'rp-waypoint-1', 'rp-finish'].map(id => ({id, dataset: {lat: '47.5', lon: '19.1', name: longName}}));
    const layer = {addTo(){return this}, bindPopup(){return this}};
    const context = vm.createContext({normalizeRoutePlanLocation: normalize, document: {getElementsByClassName: () => fields, getElementById: () => ({value: 'Test route'})}, composingRoutePlan: {}, routeplanMap: {invalidateSize(){}, eachLayer(){}, fitBounds(){}}, L: {tileLayer: () => layer, icon: () => ({}), marker: () => layer, polyline: () => layer}, marker: null, staticRes: '', updateRoutePlannerState(){}});
    vm.runInContext(source, context);
    return {context, fields};
}
test('actual form payload bounds start, finish and waypoint, including legacy sentinel names', () => {
    const {context, fields} = formContext();
    fields[0].dataset.name = 'undefined';
    fields[2].dataset.name = 'null';
    vm.runInContext('updateCurrentRoutePlanFromForm()', context);
    for (const key of ['start_name', 'finish_name', 'point1_name']) {
        const name = context.composingRoutePlan[key];
        assert.ok(name && name !== 'undefined' && name !== 'null');
        assert.ok(Array.from(name).length <= 30);
    }
    assert.equal(context.composingRoutePlan.count, 3);
});
test('existing valid route names and coordinates are preserved', () => {
    const {context, fields} = formContext();
    for (const field of fields) field.dataset.name = 'Valid location';
    vm.runInContext('updateCurrentRoutePlanFromForm()', context);
    assert.equal(context.composingRoutePlan.start_name, 'Valid location');
    assert.equal(context.composingRoutePlan.finish_lat, '47.5000000000');
    assert.equal(context.composingRoutePlan.point1_lon, '19.1000000000');
});

function saveContext(invalidId = null) {
    const {context, fields} = formContext();
    for (const field of fields) {
        if (field.id === invalidId) field.dataset = {};
        field.setCustomValidity = message => { field.error = message; };
        field.reportValidity = () => !field.error;
        field.focus = () => { context.focused = field.id; };
    }
    context.document.getElementById = () => ({value: 'Test route', reportValidity: () => true});
    context.routePlans = [];
    context.vin = 'local-fixture';
    context.requests = [];
    context.fetch = (url, options) => {
        context.requests.push(JSON.parse(options.body));
        return new Promise(() => {});
    };
    const template = fs.readFileSync(path.join(__dirname, '../templates/ui/car_detail.html'), 'utf8');
    const source = template.slice(template.indexOf('        function saveRoutePlan()'), template.indexOf('        function exitRoutePlanEditor()'))
        .replace(/{{ route_location_label\|escapejs }}/g, 'Location')
        .replace(/{{ route_point_error\|escapejs }}/g, 'Select a location for this point before saving.')
        .replace(/{% translate ["']([^"']+)["'] %}/g, '$1');
    vm.runInContext(source, context);
    return {context, fields};
}
for (const id of ['rp-start', 'rp-finish', 'rp-waypoint-1']) {
    test(`unselected ${id} blocks save and reports the exact field`, () => {
        const {context, fields} = saveContext(id);
        vm.runInContext('saveRoutePlan()', context);
        assert.equal(context.requests.length, 0);
        assert.equal(context.focused, id);
        assert.match(fields.find(field => field.id === id).error, /Select a location/);
        assert.equal(context.routePlans.length, 0);
    });
}
test('save regenerates and normalizes payload before PATCH', () => {
    const {context} = saveContext();
    vm.runInContext('saveRoutePlan()', context);
    assert.equal(context.requests.length, 1);
    const route = context.requests[0].route_plans[0];
    for (const key of ['start_name', 'finish_name', 'point1_name']) {
        assert.equal(Array.from(route[key]).length, 30);
    }
});
test('typing over a selected point clears stale coordinates and blocks save', () => {
    const {context, fields} = saveContext();
    let onInput;
    context.document.getElementById = () => ({value: 'Test route', reportValidity: () => true, addEventListener: (type, callback) => { onInput = callback; }});
    const template = fs.readFileSync(path.join(__dirname, '../templates/ui/car_detail.html'), 'utf8');
    const start = template.indexOf("            document.getElementById('routeplanner-compose').addEventListener('input'");
    vm.runInContext(template.slice(start, template.indexOf('            // listener for routeplan field', start)), context);
    fields[0].classList = {contains: name => name === 'rp-searchfield'};
    onInput({target: fields[0]});
    assert.equal(Object.keys(fields[0].dataset).length, 0);
    assert.equal(context.composingRoutePlan.start_lat, undefined);
    vm.runInContext('saveRoutePlan()', context);
    assert.equal(context.requests.length, 0);
    assert.equal(context.focused, 'rp-start');
});
for (const [url, location, label] of [
    ['https://maps.app.goo.gl/local-short', {name: 'Smart Parking', address: null, lat: '47.5', lon: '19.1'}, 'Smart Parking'],
    ['https://maps.google.com/resolved', {name: null, address: 'Budapest, Fő utca 12.', lat: '47.5', lon: '19.1'}, 'Budapest, Fő utca 12.'],
]) {
    test(`actual map-link search handler normalizes ${url}`, async () => {
        const {context, fields} = formContext();
        const field = fields[0];
        field.value = url;
        field.setCustomValidity = () => {};
        const results = {};
        const template = fs.readFileSync(path.join(__dirname, '../templates/ui/car_detail.html'), 'utf8');
        const source = template.slice(template.indexOf('        function routePlanPointSearch('), template.indexOf('        function addWayPoint('))
            .replace(/{{ route_location_label\|escapejs }}/g, 'Location')
            .replace(/{% translate ["']([^"']+)["'] %}/g, '$1');
        vm.runInContext(template.split('\n').find(line => line.includes('const mapUrlRegex =')), context);
        context.map = {invalidateSize(){}};
        context.fetch = async (endpoint, options) => {
            assert.equal(endpoint, '/api/maplink/resolve');
            assert.ok(JSON.parse(options.body).url);
            return {json: async () => ({location})};
        };
        vm.runInContext(source, context);
        context.routePlanPointSearch({preventDefault(){}, target: {getElementsByClassName: name => [name === 'rp-searchfield' ? field : results]}});
        await new Promise(resolve => setImmediate(resolve));
        assert.equal(field.value, label);
        assert.ok(field.dataset.name);
        assert.ok(Array.from(context.composingRoutePlan.start_name).length <= 30);
    });
}
