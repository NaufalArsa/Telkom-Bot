const https = require("https");
const puppeteer = require("puppeteer");

let limitRequestInit = 0;
let limitRequest = 3;

function isGoogleMapsUrl(url) {
  const regexes = [
    /^(http|https):\/\/(www\.)?maps\.google\.com\/(\?q=|maps\?)(.*)$/, // Standard Maps URLs
    /^(http|https):\/\/(www\.)?google\.com\/maps\/place\/(.*)$/, // Place URLs
    /^(http|https):\/\/(www\.)?maps\.googleapis\.com\/maps\/api\/staticmap\?(.*)$/, // Static Map URLs
    /^https:\/\/maps\.app\.goo\.gl\/\w+$/,
    /^(http|https):\/\/(www\.)?google\.com\/maps\/(preview\/)?\?q=[\d\.\-]+,[\d\.\-]+(@[\d\.\-]+,[\d\.\-]+)?(,[\d]+z)?$/,
    /^(http|https):\/\/(www\.)?google\.com\/maps\/preview\/@[\d\.\-]+,[\d\.\-]+,[\d]+z$/,
  ];

  for (const regex of regexes) {
    if (regex.test(url)) {
      return true;
    }
  }

  return false;
}

function unshortenUrl(url) {
  return new Promise((resolve, reject) => {
    try {
      const parsedUrl = new URL(url);
      const hostname = parsedUrl.hostname;

      const options = {
        hostname,
        method: "HEAD",
        path: parsedUrl.pathname + parsedUrl.search,
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
      };

      const req = https.request(options, (res) => {
        if (res.statusCode >= 300 && res.statusCode < 400 && res.headers.location) {
          const newUrl = res.headers.location;
          unshortenUrl(newUrl).then(resolve).catch(() => resolve(url)); // Recursively unshorten
        } else {
          resolve(url);
        }
        req.end();
      });

      req.on("error", (error) => {
        console.error("Error unshortening URL:", url, error.message);
        resolve(url); // Return original URL on error
      });

      req.end();
    } catch (error) {
      console.error("Error unshortening URL:", url, error.message);
      resolve(url); // Return original URL on error
    }
  });
}

function urlToPoint(url) {
  const regex = /@(-?[0-9]+\.[0-9]+),(-?[0-9]+\.[0-9]+)/;
  const match = url.match(regex);

  if (match) {
    const latitude = parseFloat(match[1]);
    const longitude = parseFloat(match[2]);
    return { latitude, longitude };
  } else {
    console.error("Failed to extract coordinates from URL:", url);
    return null;
  }
}

async function convertMapUrlToPoint(url) {
  const check = isGoogleMapsUrl(url);
  if (check === false) {
    return { latitude: null, longitude: null };
  }
  
  try {
    const unshortenedUrl = await unshortenUrl(url);
    console.log("Unshortened URL:", unshortenedUrl);
    
    let coor = urlToPoint(unshortenedUrl);
    if (coor === null) {
      coor = await getCoordsWithPuppeteer(unshortenedUrl);
    }
    return coor;
  } catch (error) {
    console.error("Error processing URL:", error);
    return { latitude: null, longitude: null };
  }
}

async function getCoordsWithPuppeteer(url) {
  const browser = await puppeteer.launch({
    args: ["--no-sandbox", "--disable-setuid-sandbox"],
    headless: true
  });
  const page = await browser.newPage();

  try {
    await page.goto(url, { waitUntil: 'networkidle2' });

    // Wait for 3 seconds for the full URL to appear
    await new Promise((res) => setTimeout(res, 3000));

    const fullUrl = page.url(); // Get the updated URL
    console.log("Final URL from Puppeteer:", fullUrl);

    if (url !== fullUrl) {
      return urlToPoint(fullUrl);
    }

    return null;
  } catch (error) {
    console.error("Error using Puppeteer:", error);
    return null;
  } finally {
    await browser.close(); // Close the browser
  }
}

module.exports = { convertMapUrlToPoint };

// Command line interface
if (require.main === module) {
  const inputUrl = process.argv[2];
  if (!inputUrl) {
    console.error("Usage: node index.js <google-maps-url>");
    process.exit(1);
  }
  
  convertMapUrlToPoint(inputUrl).then((coords) => {
    console.log("Result:", JSON.stringify(coords));
  }).catch((error) => {
    console.error("Error:", error);
    process.exit(1);
  });
}