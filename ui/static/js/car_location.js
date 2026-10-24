function buildCarLocationLinks(lat, lon) {
    if (lat == null || lon == null) return null;
    const destination = encodeURIComponent(`${lat},${lon}`);
    return {
        coordinates: `${lat}, ${lon}`,
        google: `https://www.google.com/maps/dir/?api=1&destination=${destination}&travelmode=walking`
    };
}
