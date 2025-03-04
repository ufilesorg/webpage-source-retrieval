/**
 * This file is used to extract images from the page and return a list of image as a base64 string.
 * It will run in the browser using selenium.
 * It uses extractImageUrls function to get the image urls.
 * Then it downloads the image, and converts it to a base64 string.
 * Finally it checks if the image is valid using getImagesBase64 function.
 * If the image is valid, it adds it to the list of images.
 * If the image is not valid, it skips it.
 */


/**
 * This function is used to convert an image URL to a base64 string.
 * @param {string} imgUrl - The URL of the image to convert.
 * @returns {Promise<string>} - A promise that resolves to the base64 string of the image.
 */
function getImagesBase64(imgUrl) {
    if (imgUrl.startsWith('data:image')) {

        return imgUrl;
    }

    return new Promise((resolve, reject) => {
        var canvas = document.createElement('canvas');
        var img = document.createElement('img');

        img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            var context = canvas.getContext('2d');
            context.drawImage(img, 0, 0);
            // Convert to JPEG format with 0.9 quality (90%)
            resolve(canvas.toDataURL('image/jpeg', 0.9));
        };

        img.onerror = (error) => {
            resolve(null);
            // reject(new Error('Failed to load image: ' + error.message));
        };

        img.crossOrigin = 'anonymous';
        img.src = imgUrl;
    });
}


/**
 * This function is used to verify if an image meets certain size criteria.
 * @param {string} imageBase64 - The base64 string of the image to verify.
 * @param {number} minAcceptableSide - The minimum acceptable side length in pixels.
 * @param {number} maxAcceptableSide - The maximum acceptable side length in pixels.
 * @returns {Promise<boolean>} - A promise that resolves to true if the image meets the criteria, false otherwise.
 */
async function getImageVerification(imageBase64, minAcceptableSide = 600, maxAcceptableSide = 2500, aspectRatio = 0.75) {
    try {
        return new Promise((resolve, reject) => {
            const img = new Image();

            img.onload = () => {
                const width = img.width;
                const height = img.height;
                const longerSide = Math.max(width, height);
                const shorterSide = Math.min(width, height);

                if (
                    shorterSide >= minAcceptableSide &&
                    // longerSide <= maxAcceptableSide &&
                    shorterSide / longerSide >= aspectRatio
                ) {
                    resolve(true);
                } else {
                    resolve(false);
                }
            };

            img.onerror = () => {
                resolve(false);
            };

            // Set source to the base64 string directly
            // If it's already a data URL, use it as is; otherwise, assume it's a base64 string and create a data URL
            img.src = imageBase64.startsWith('data:') ? imageBase64 : `data:image/jpeg;base64,${imageBase64}`;
        });
    } catch (error) {
        console.error(`Error verifying image: ${error}`);
        return false;
    }
}


/**
 * This function is used to extract image URLs from the page.
 * @returns {Promise<string[]>} - A promise that resolves to an array of image URLs.
 */
function extractImageUrls() {
    const urls = new Set();
    const baseUrl = window.location.href;
    const htmlSource = document.documentElement.outerHTML;

    // Process all img elements
    document.querySelectorAll('img').forEach(img => {
        // Handle src attribute
        const src = img.getAttribute('src');
        if (src) {
            urls.add(new URL(src, baseUrl).href);
        }

        // Handle srcset attribute
        const srcset = img.getAttribute('srcset');
        if (srcset) {
            // Split srcset by commas (similar to re.split in Python)
            srcset.split(/,\s*/).forEach(part => {
                // Get the URL part (first part before space or the whole string)
                const urlPart = part.split(/\s+/)[0] || part;
                urls.add(new URL(urlPart, baseUrl).href);
            });
        }
    });

    // Extract image URLs from HTML source using regex (similar to image_url_pattern in Python)
    // Note: This is a simplified version, you may need to adjust the regex pattern
    const imageUrlPattern = /\burl\s*\(\s*['"]?([^'"\s)]+)['"]?\s*\)/gi;
    let match;
    while ((match = imageUrlPattern.exec(htmlSource)) !== null) {
        urls.add(new URL(match[1], baseUrl).href);
    }

    return Array.from(urls);
}

var callback = arguments[0];
var minAcceptableSide = 600;
var maxAcceptableSide = 2500;
var aspectRatio = 0.75;
if (arguments.length > 1) {
    minAcceptableSide = arguments[1];
}
if (arguments.length > 2) {
    maxAcceptableSide = arguments[2];
}
if (arguments.length > 3) {
    aspectRatio = arguments[3];
}

// First convert all image URLs to base64
Promise.all(extractImageUrls().map(url => getImagesBase64(url)))
    .then(async base64Results => {
        // Filter out null results
        const validBase64s = base64Results.filter(base64 => base64 != null);

        // Check each image against size criteria
        const verificationPromises = validBase64s.map(base64 =>
            getImageVerification(base64, minAcceptableSide, maxAcceptableSide, aspectRatio)
        );

        // Wait for all verifications to complete
        const verificationResults = await Promise.all(verificationPromises);

        // Create array of valid images that passed verification
        const validImages = validBase64s.filter((base64, index) => verificationResults[index] === true);

        // Send only valid images to callback
        callback(validImages);
    })
    .catch(error => callback(error.toString()));