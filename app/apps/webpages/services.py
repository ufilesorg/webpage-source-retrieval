import asyncio
import binascii
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import httpx
import langdetect
import validators
from bs4 import BeautifulSoup
from fastapi_mongo_base.tasks import TaskStatusEnum
from fastapi_mongo_base.utils import basic, imagetools
from googleapiclient.discovery import build
from PIL import Image, ImageFile
from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchWindowException,
    StaleElementReferenceException,
    TimeoutException,
)
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support.ui import WebDriverWait
from server.config import Settings

from .models import Webpage

ImageFile.LOAD_TRUNCATED_IMAGES = True
image_url_pattern = re.compile(
    r"(?:https?:\/\/)?[^\s\"']+\.(?:jpg|jpeg|png|gif|webp|bmp|tiff|ico)(?:\?[^\s\"']*)?",
    re.IGNORECASE,
)

semaphore = asyncio.Semaphore(4)
image_limit_semaphore = asyncio.Semaphore(4)  # adjust the limit as necessary


def get_main_domain(url: str) -> str:
    from urllib.parse import urlparse

    netloc = urlparse(url).netloc
    netloc_parts = netloc.split(".")
    remove_parts = ["www", "app", "console", "admin", "panel"]
    filtered_netloc_parts = [
        part for part in netloc_parts[:-2] if part not in remove_parts
    ] + netloc_parts[-2:]
    main_domain = ".".join(filtered_netloc_parts)
    return main_domain


@basic.try_except_wrapper
async def fetch_webpage_direct(webpage: Webpage, **kwargs) -> dict | None:
    if "https://www.reddit.com" in webpage.url:
        return None
    try:
        follow_redirects = kwargs.pop("follow_redirects", True)

        async with httpx.AsyncClient(follow_redirects=follow_redirects) as client:
            response = await client.get(webpage.url, timeout=Settings.httpx_timeout)
            response.raise_for_status()
            if response.headers.get("Content-Type") != "text/html":
                return {"error": "not_html"}
            return {"source_code": response.text}  # Return page content if successful
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 403:
            return {"error": "permission_denied"}
        logging.error(f"Error fetching `{webpage.url}` with direct: {type(e)} {e}")
        return {"error": f"{type(e)} {e}"}
    except Exception as e:
        logging.error(f"Error fetching `{webpage.url}` with direct: {type(e)} {e}")
        return {"error": f"{type(e)} {e}"}


async def fetch_webpage_dynamic(webpage: Webpage, **kwargs):

    def browser_img_arr(
        driver: webdriver.Remote, js_filename: str = "logo_img.js"
    ) -> list[BytesIO]:
        """Fetches a list of logos as base64 images using JavaScript in Selenium."""
        # Load the JavaScript file to retrieve and convert logos to base64
        file_dir = (
            Path(__file__).parent
            if "__file__" in globals()
            else Settings.base_dir / "apps" / "webpages"
        )
        with open(file_dir / "js" / js_filename, "r") as js_file:
            js_code = js_file.read()

        # Execute the JavaScript asynchronously
        try:
            image_base64_list = driver.execute_async_script(js_code)
            return image_base64_list
        except Exception as e:
            logging.error(f"Error fetching images: {e}")
            return []

    def capture_full_page_screenshot(
        driver: webdriver.Remote, max_width=1920, max_height=10800
    ):
        # Get the total page height
        driver.set_window_size(1920, 1200)
        dimension = driver.execute_script(
            "return { width: document.body.clientWidth, height: document.body.scrollHeight }"
        )
        width = min(dimension["width"], max_width)
        height = min(dimension["height"], max_height)

        # Set the window size to capture the full page height
        driver.set_window_size(width, height)

        # Take a screenshot and save it to a BytesIO object
        screenshot_bytes = BytesIO(driver.get_screenshot_as_png())

        return screenshot_bytes

    def get_source_with_iframes(driver: webdriver.Remote):
        try:
            WebDriverWait(driver, Settings.selenium_loading_time).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException as e:
            logging.warning(f"Page did not load in time: {e}")

        main_page_source = driver.page_source
        iframes = driver.find_elements("tag name", "iframe")
        iframe_contents = []

        for _ in range(len(iframes)):
            iframes = driver.find_elements("tag name", "iframe")  # Refresh iframe list
            iframe = iframes[_]

        for iframe in iframes:
            try:
                if iframe.is_displayed():
                    driver.switch_to.frame(iframe)
                    WebDriverWait(driver, Settings.selenium_loading_time).until(
                        lambda d: d.execute_script("return document.readyState")
                        == "complete"
                    )
                    iframe_contents.append(driver.page_source)
            except TimeoutException:
                logging.warning(
                    f"IFrame did not load in time: {iframe.get_attribute('src')}"
                )
            except NoSuchWindowException as e:
                logging.warning(
                    f"NoSuchWindowError: The browser window was closed or discarded. {e}"
                )
            except StaleElementReferenceException as e:
                logging.warning(
                    f"StaleElementReferenceError: The element is no longer attached to the DOM. {e}"
                )
            except Exception as e:
                logging.warning(f"Error fetching iframe content: {e}")
            finally:
                driver.switch_to.default_content()

        full_page_source = main_page_source + "\n".join(iframe_contents)
        return full_page_source

    def browser_fetch(webpage: Webpage, kwargs: dict = {}):
        try:
            webdriver_options = webdriver.FirefoxOptions()
            webdriver_options.add_argument("--no-shm")

            driver = webdriver.Remote(
                f"{Settings.selenium_remote_url}/wd/hub",
                DesiredCapabilities.FIREFOX,
                options=webdriver_options,
            )
            driver.set_page_load_timeout(Settings.browser_timeout)
            driver.implicitly_wait(Settings.selenium_loading_time)
            try:
                driver.get(webpage.url)
                time.sleep(Settings.selenium_loading_time)
            except TimeoutException:
                driver.execute_script("window.stop();")

            source_code = get_source_with_iframes(driver)
            if kwargs.get("extract_images", False):
                images = browser_img_arr(driver, "image_extractor.js")
            else:
                images = []
            # favicon_images = browser_img_arr(driver, "favicon.js")
            # logo_images = browser_img_arr(driver, "logo_img.js")
            # screenshot_image = capture_full_page_screenshot(driver)
            return {
                "source_code": source_code,
                "images": images,
                # "favicon_images": favicon_images,
                # "logo_images": logo_images,
                # "screenshot_image": screenshot_image,
            }
        finally:
            try:
                driver.quit()
            except:
                pass

    try:
        with ThreadPoolExecutor() as executor:
            return await asyncio.get_event_loop().run_in_executor(
                executor, browser_fetch, webpage
            )
    except Exception as e:
        webpage.task_status = TaskStatusEnum.error
        await webpage.save_report(
            f"Error fetching `{webpage.url}` with browser",
            emit=False,
            log_type="crawl_error",
        )
        logging.error(f"Error fetching `{webpage.url}` with browser: {type(e)} {e}")
        return {}


async def fetch_google_data(webpage: Webpage):
    if webpage.google_data:
        return

    try:
        google_results = await get_google_result(webpage.url)
        webpage.google_data = google_results
    except Exception as e:
        logging.error(f"Error fetching Google data for `{webpage.url}`: {e}")


async def get_google_result(url, **kwargs):
    # search_url = f"https://www.googleapis.com/customsearch/v1/?key={Settings.GSEARCH_API_KEY}&q={url}&cx={Settings.GSEARCH_CX}"
    service = build("customsearch", "v1", developerKey=Settings.GSEARCH_API_KEY)
    res: dict = service.cse().list(q=url, cx=Settings.GSEARCH_CX, **kwargs).execute()
    items = res.get("items")
    if not items:
        return

    # Attempt to retrieve icon from pagemap
    for item in items:
        if get_main_domain(item["link"]) == get_main_domain(url):
            break
    srcs: list[str] = []
    pagemap: dict[str, list[dict]] = item.get("pagemap", {})

    for thumbnail in pagemap.get("cse_thumbnail", []):
        if thumbnail.get("src"):
            srcs.append(thumbnail.get("src"))
    for image in pagemap.get("cse_image", []):
        if image.get("src"):
            srcs.append(image.get("src"))

    return item


@basic.try_except_wrapper
# @basic.retry_execution(attempts=3, delay=1)
async def fetch_webpage(webpage: Webpage, **kwargs) -> dict:
    webpage.id = (await Webpage.get_by_url(webpage.url)).id

    async with semaphore:
        # Check cache first
        if webpage.check_cache() and not kwargs.get("force_refetch"):
            logging.info(f"Fetching webpage {webpage.url} from cache")
            webpage.task_status = TaskStatusEnum.completed
            await webpage.save()
            return webpage

        # browser_task = asyncio.create_task(fetch_webpage_dynamic(webpage))
        # fetch_tasks = [browser_task]

        # Try network fetch
        content = await fetch_webpage_direct(webpage, **kwargs)
        if content.get("error") == "not_html":
            webpage.page_source = "<html><body><h1>Not HTML</h1></body></html>"
            await webpage.save()
            return webpage

        webpage.page_source = content.get("source_code") if content else None
        if webpage.is_enough_text():
            webpage.task_status = TaskStatusEnum.completed
            logging.info(f"Fetching webpage {webpage.url} from network")
            await webpage.save()
            return webpage

        content: dict = await fetch_webpage_dynamic(webpage, **kwargs)
        webpage.page_source = content.get("source_code") if content else None
        webpage.images = content.get("images") if content else None
        webpage.task_status = TaskStatusEnum.completed
        logging.info(f"Fetching webpage {webpage.url} from browser")

        await webpage.save()
        return webpage


@basic.try_except_wrapper
async def language_validation(
    soup: BeautifulSoup, invalid_languages: list[str] = ["fa"]
) -> bool:
    # Extract all text from the soup
    full_text = soup.get_text(strip=True)

    # If there's not enough text to analyze, consider it valid
    if len(full_text) < 100:
        return True

    # Split text into chunks for better language detection
    chunk_size = 500  # Characters per chunk
    chunks = [
        full_text[i : i + chunk_size] for i in range(0, len(full_text), chunk_size)
    ]

    # Detect language for each chunk
    language_counts = {}
    for chunk in chunks:
        # Skip chunks that are too short for reliable detection
        if len(chunk.strip()) < 50:
            continue

        try:
            lang = langdetect.detect(chunk)
            language_counts[lang] = language_counts.get(lang, 0) + 1
        except langdetect.LangDetectException:
            # Skip chunks where language detection fails
            continue

    # If no languages were detected, consider it valid
    if not language_counts:
        return True

    # Calculate percentage of each language
    total_chunks = sum(language_counts.values())
    language_percentages = {
        lang: (count / total_chunks) * 100 for lang, count in language_counts.items()
    }

    # Check if any invalid language exceeds threshold (e.g., 20%)
    threshold = 20.0
    for invalid_lang in invalid_languages:
        if language_percentages.get(invalid_lang, 0) > threshold:
            return False

    return True


async def get_image_verification(
    image_url: str, min_acceptable_side=600, max_acceptable_side=2500
) -> dict:
    try:
        img_response = await imagetools.get_image_metadata(
            image_url, with_exif=False, follow_redirects=True
        )
        if not img_response:
            return False
        width, height = img_response.get("width"), img_response.get("height")
        longer_side, shorter_side = max(width, height), min(width, height)
        if (
            shorter_side >= min_acceptable_side
            and longer_side <= max_acceptable_side
            and shorter_side / longer_side >= 0.75
        ):
            return True

    except (binascii.Error, Image.UnidentifiedImageError, ValueError) as e:
        logging.error(f"Error downloading image {image_url}: {type(e)} {e}")
    except httpx.HTTPError as e:
        if hasattr(e, "response") and (
            e.response.status_code == 404 or e.response.status_code == 403
        ):
            return False
        logging.error(f"Error downloading image {image_url}: {type(e)} {e}")
    return False


def is_valid_image_url(img_url: str, base_url: str, check_svg: bool = True) -> bool:
    full_url = urljoin(base_url, img_url)
    return (
        full_url
        and full_url != base_url
        and (full_url.startswith("data:image/") or validators.url(full_url))
        and not (
            check_svg
            and (full_url.endswith(".svg") or "data:image/svg+xml" in full_url)
        )
    )


def extract_image_urls(
    soup: BeautifulSoup, base_url: str, html_source: str
) -> set[str]:
    def join_url(url: str) -> str:
        if url.startswith("https:/") and not url.startswith("https://"):
            url = url.replace("https:/", "https://", 1)
        return urljoin(base_url, url)

    urls = set()
    for img in soup.find_all("img"):
        src = img.get("src")
        if src:
            urls.add(join_url(src))
        srcset = img.get("srcset")
        if srcset:
            # Adjust splitting as needed: some srcset values are comma separated.
            for part in re.split(r",\s*", srcset):
                url_part = (part.split() or [part])[0]
                urls.add(join_url(url_part))
    urls.update(join_url(img_url) for img_url in image_url_pattern.findall(html_source))
    return urls


async def images_from_webpage(
    webpage: Webpage,
    *,
    invalid_languages: list[str] = ["fa"],
    min_acceptable_side=600,
    max_acceptable_side=2500,
    with_svg: bool = False,
):
    if webpage.images:
        return webpage.images

    url = webpage.url
    html_source = webpage.page_source
    soup = webpage.soup

    if not await language_validation(soup, invalid_languages=invalid_languages):
        logging.warning(f"Skipping {url} as its language is Persian.")
        return []

    # Extract and filter candidate image URLs.
    all_urls = extract_image_urls(soup, url, html_source)
    candidate_image_urls = {
        img_url
        for img_url in all_urls
        if is_valid_image_url(img_url, url, not with_svg)
    }

    async def limited_verification(image_url: str) -> bool:
        async with image_limit_semaphore:
            return await get_image_verification(
                image_url, min_acceptable_side, max_acceptable_side
            )

    verification_tasks = [
        limited_verification(image_url) for image_url in candidate_image_urls
    ]
    verifications = await asyncio.gather(*verification_tasks)
    valid_image_urls = [
        image_url
        for image_url, verified in zip(candidate_image_urls, verifications)
        if verified
    ]
    return valid_image_urls
