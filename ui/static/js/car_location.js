function normalizeCarCoordinates(lat, lon) {
    function coordinate(value, limit) {
        if (typeof value !== 'number' && typeof value !== 'string') return null;
        if (typeof value === 'string' && !value.trim()) return null;
        const number = Number(value);
        return Number.isFinite(number) && Math.abs(number) <= limit ? number : null;
    }
    const latitude = coordinate(lat, 90);
    const longitude = coordinate(lon, 180);
    return latitude === null || longitude === null ? null : {lat: latitude, lon: longitude};
}

function buildCarLocationLinks(lat, lon) {
    const point = normalizeCarCoordinates(lat, lon);
    if (!point) return null;
    const destination = encodeURIComponent(`${point.lat},${point.lon}`);
    return {
        coordinates: `${point.lat}, ${point.lon}`,
        google: `https://www.google.com/maps/dir/?api=1&destination=${destination}&travelmode=walking`
    };
}
