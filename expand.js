const { convertMapUrlToPoint } = require('gmaps-expand-shorturl');

// Check if running from command line
if (process.argv.length > 2) {
    const url = process.argv[2];
    
    (async () => {
        try {
            const coords = await convertMapUrlToPoint(url);
            console.log("Result:", JSON.stringify(coords));
        } catch (error) {
            console.error("Error:", error);
            process.exit(1);
        }
    })();
} else {
    // Default test URLs
    (async () => {
        const pointLatLong2 = await convertMapUrlToPoint('https://maps.app.goo.gl/QbwD3NE9qmR62nYJ9?g_st=ipc');

        console.log(pointLatLong2);
    })();
}