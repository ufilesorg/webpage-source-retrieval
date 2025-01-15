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

var favicon_urls = Array.from(document.querySelectorAll(
    [
        'link[rel="icon"]',
        'link[rel="shortcut icon"]',
        'link[rel="apple-touch-icon"]',
        'link[rel="apple-touch-icon-precomposed"]',
        'link[rel="apple-touch-startup-image"]',
        'link[rel="mask-icon"]',
        'link[rel="fluid-icon"]',
    ].join(', ')
)).map(element => element.href).filter(url => url != null);

Array.from(document.querySelectorAll(
    [
        'meta[property="og:image"]',
        'meta[name="twitter:image"]'
    ]
)).map(element => element.content).forEach(url => favicon_urls.push(url));

var callback = arguments[0];  // This is the callback function provided by Selenium
Promise.all(favicon_urls.map(getFaviconBase64))
    .then(result => callback(result.filter(base64 => base64 != null)))
    .catch(error => callback(error.toString()));