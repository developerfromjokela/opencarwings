// Route Planner names are limited to 30 characters; display labels are not.
function normalizeRoutePlanLocation(location, fallbackName) {
    function text(value) {
        if (typeof value !== 'string') return '';
        const cleaned = value.normalize('NFC').replace(/\s+/g, ' ').trim();
        return /^(null|undefined)$/i.test(cleaned) ? '' : cleaned;
    }

    const address = location.address && typeof location.address === 'object' ? location.address : {};
    const road = [text(address.road), text(address.house_number)].filter(Boolean).join(' ');
    const addressLabel = text(location.address) || [
        road,
        text(address.neighbourhood),
        text(address.suburb),
        text(address.city) || text(address.town) || text(address.village) || text(address.hamlet),
        text(address.postcode),
        text(address.country)
    ].filter(Boolean).join(', ') || text(location.display_name);
    const poi = text(location.name) === text(address.road) ? '' : text(location.name);
    const fullName = poi || road || addressLabel || text(fallbackName);
    return {
        name: Array.from(fullName).slice(0, 30).join(''),
        address: addressLabel,
        label: [...new Set([poi, addressLabel].filter(Boolean))].join(', ') || fullName
    };
}
