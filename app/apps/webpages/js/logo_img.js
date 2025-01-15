function getFaviconBase64(imgUrl) {
    return new Promise((resolve, reject) => {
        var canvas = document.createElement('canvas');
        var img = document.createElement('img');

        img.onload = () => {
            canvas.width = img.width;
            canvas.height = img.height;
            var context = canvas.getContext('2d');
            context.drawImage(img, 0, 0);
            resolve(canvas.toDataURL('image/png'));
        };

        img.onerror = (error) => {
            resolve(null);
            // reject(new Error('Failed to load image: ' + error.message));
        };

        img.crossOrigin = 'anonymous';
        img.src = imgUrl;
    });
}


function get_logo_attr_image_urls() {
    const logoImgs = Array.from(document.querySelectorAll('img'))
        .filter(img => Array.from(img.attributes)
            .some(attr => attr.value.toLowerCase().includes('logo')))
        .map(img => new URL(img.getAttribute('src'), window.location.href).href);
    return logoImgs;
}

function get_div_logo_image_urls() {
    const logoDivs = Array.from(document.querySelectorAll('div'))
        .filter(div => Array.from(div.classList)
            .some(className => className.toLowerCase().includes('logo'))
        );

    const logoImgs = [];

    logoDivs.forEach(div => {
        const imgs = Array.from(div.querySelectorAll('img'))
        const images = Array.from(imgs)
            .filter(img => img.getAttribute('src'))
            .map(img => {
                return new URL(img.getAttribute('src'), window.location.href).href
            });
        logoImgs.push(...images);
    });
    return logoImgs;
}

function get_svg_logo_image_urls() {
    const svgLogos = Array.from(document.querySelectorAll('svg'))
        .filter(svg => Array.from(svg.attributes)
            .some(attr => attr.value.toLowerCase().includes('logo')))
        .map(svg => {
            const serializer = new XMLSerializer();
            return 'data:image/svg+xml;base64,' + btoa(serializer.serializeToString(svg));
        });

    const logoDivs = Array.from(document.querySelectorAll('div'))
        .filter(div => Array.from(div.classList)
            .some(className => className.toLowerCase().includes('logo'))
        );

    logoDivs.forEach(div => {
        const svg = Array.from(div.querySelectorAll('svg'))
            .map(svg => {
                const serializer = new XMLSerializer();
                return 'data:image/svg+xml;base64,' + btoa(serializer.serializeToString(svg));
            });
        svgLogos.push(...svg);
    });
    return svgLogos;
}


function get_logo_image_urls() {
    const logoUrls = [...get_logo_attr_image_urls(), ...get_div_logo_image_urls()];
    const uniqueArray = Array.from(new Set(logoUrls));
    const filteredArray = uniqueArray.filter(url =>
        !url.toLowerCase().includes('samandehi') &&
        !url.toLowerCase().includes('enamad')
    );
    return filteredArray;
}

const logoUrls = get_logo_image_urls();
const svgLogos = get_svg_logo_image_urls();

var callback = arguments[0];
// Run getFaviconBase64 on each logo URL and handle the result with the callback
Promise.all([...logoUrls, ...svgLogos].map(url => {
    if (url.startsWith('data:image/svg+xml;base64,')) {
        // Return SVG data URL as-is
        return url;
    } else {
        // Convert image URL to base64
        return getFaviconBase64(url);
    }
}))
    .then(result => callback(result.filter(base64 => base64 != null)))
    .catch(error => callback(error.toString()));