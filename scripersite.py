import os
import logging
import base64
from typing import List, Optional, Iterator, Dict

import requests
import magic
# import mimetypes
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
    )
LOGGER = logging.getLogger(__name__)


class WebScraper:
    """
    A simple web scraper to extract all paragraph text content
    from a web page.
    """
    def __init__(
        self,
        user_agent: Optional[str] = None,
        timeout: int=10
    ) -> None:
        self.user_agent = user_agent
        if self.user_agent is None:
            self.user_agent = (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0 Safari/537.36"
                )
        self.timeout = timeout
        self.headers = {"User-Agent": self.user_agent}
        self._response = None
        self._soup = None
        self._base_url = None

    def fetch(self, url: str) -> None:
        self._response = requests.get(
            url=url, headers=self.headers, timeout=self.timeout
            )
        self._response.raise_for_status()
        self._soup = BeautifulSoup(self._response.text, "html.parser")
        self._base_url = url
        LOGGER.info("Page fetched and parsed successfully.")

    def get_paragraphs(self) -> Iterator[str]:
        """
        Extract all paragraph (<p>) texts from a web page.

        :returns: An iterator of paragraph texts found on the page.
        """
        if not self._soup:
            raise RuntimeError("No page content. Call fetch() first.")

        results = [p.get_text(strip=True) for p in self._soup.find_all("p")]
        return (para for para in results if para)  # Generator (skip empty)

    def get_links(self) -> Iterator[str]:
        """
        Extract all hyperlinks (<a href="...">) from a web page.

        :returns: An iterator of link URLs found on the page.
        """
        if not self._soup:
            raise RuntimeError("No page content. Call fetch() first.")
        links = [
            a["href"]
            for a in self._soup.find_all("a", href=True)
            if a["href"].strip()
            ]
        return (link for link in links)  # Generator

    def get_images(self) -> Iterator[str]:
        """
        Extract all image sources (<img src="...">) from a web page.

        :returns: An iterator of image URLs found on the page.
        """
        if not self._soup:
            raise RuntimeError("No page content. Call fetch() first.")
        images = [
            urljoin(self._base_url, img["src"])
            for img in self._soup.find_all("img", src=True)
            if img["src"].strip()
            ]
        return (src for src in images)


def get_resource_type(url: str, timeout: int = 10) -> Dict[str, str]:
    """
    Download a resource in binary mode and detect its content type.

    :param url: The resource URL.
    :param timeout: Request timeout in seconds.
    :return: A dictionary containing detected mime type info.
    :raises requests.RequestException: When an error is occurrence.
    """
    if url.startswith("data:image/"):
        parts = url.split(":")
        parts = parts[1].split(";")
        return {
            "mime_type": parts[0],
            "description": "image",
            "header_content_type": parts[0]
            }
    LOGGER.info(f"Fetching resource from: {url}")
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()

    # Step 1: Try Content-Type header
    content_type = response.headers.get("Content-Type")
    if content_type:
        LOGGER.info(f"Content-Type from header: {content_type}")

    # Step 2: Read small chunk of content for analysis
    content = response.raw.read(2048)  # only first 2KB
    response.close()

    # Step 3: Use python-magic if available
    mime_type = magic.from_buffer(content, mime=True)
    description = magic.from_buffer(content)
    return {
        "mime_type": mime_type,
        "description": description,
        "header_content_type": content_type or "Unknown"
        }

    # Step 4: Fallback → mimetypes (based on URL extension)
    # mime_guess, _ = mimetypes.guess_type(url)
    # return {
    #     "mime_type": mime_guess or "Unknown",
    #     "description": "Detection requires python-magic for deep analysis",
    #     "header_content_type": content_type or "Unknown"
    #     }


def get_host_name(url: str) -> str:
    parts = url.split("/")
    host_name = parts[0] + "//" + parts[2]
    return host_name


def url_resolve(host: str, url: str) -> str:
    if url.startswith("#"):
        url = os.path.join(url, url)
    elif url.startswith("/"):
        url = os.path.join(host, url[1:])
    return url


def download_file(
    src: str,
    dest_path: str,
    chunk_size: int=8192,
    timeout: int=30
) -> str:
    """
    Download a file from a URL in chunks and save it locally.

    :param src: URL or data source of the file to download.
    :param dest_path: Path to save the downloaded file.
    :param chunk_size: Size of each chunk (in bytes). Default: 8192 (8 KB).
    :param timeout: Request timeout in seconds.
    :return: Path to the downloaded file if successful, None otherwise.
    :raises requests.RequestException: Download failed from URL given.
    """
    LOGGER.info(f"Starting download from {src}")
    os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)

    if src.startswith("data:"):
        # Inline base64 image
        header, b64data = src.split(",", 1)
        # Determine extension from mime type
        mime_type = header.split(";")[0].split(":")[1]  # e.g., image/png
        ext = mime_type.split("/")[-1]
        if not dest_path.lower().endswith(ext):
            dest_path += f".{ext}"

        LOGGER.info(f"Decoding base64 image to {dest_path}")
        with open(dest_path, "wb") as f:
            f.write(base64.b64decode(b64data))

    else:
        # Regular HTTP/HTTPS download
        LOGGER.info(f"Downloading image from {src} to {dest_path}")
        with requests.get(src, stream=True, timeout=timeout) as response:
            response.raise_for_status()
            with open(dest_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)

    LOGGER.info(f"Download completed: {dest_path}")
    return dest_path


def main() -> int:
    """Main function to run web scrapping."""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("url", type=str)
    parser.add_argument("-o", "--outputs", type=str, default="outputs")
    args = parser.parse_args()

    scraper = WebScraper()
    url = args.url
    outputs_dir = args.outputs

    # url = "https://www.example.com"
    # url = "https://beautiful-soup-4.readthedocs.io/en/latest/"
    # url = "https://arxiv.org/abs/1706.03762"
    # url = "https://duckduckgo.com/?q=BeautifulSoup+document&ia=web/"
    # url = "https://www.geeksforgeeks.org/python-web-scraping-tutorial/"
    # url = "https://www.awesomescreenshot.com/"
    # url = "https://www.google.com/search?sca_esv=a6493d853efe4d30&sxsrf=AE3TifNkcqd07sZd9usjPy5VYBUhyhh1NA:1758276680403&udm=2&fbs=AIIjpHxU7SXXniUZfeShr2fp4giZ1Y6MJ25_tmWITc7uy4KIeoJTKjrFjVxydQWqI2NcOhYPURIv2wPgv_w_sE_0Sc6QqqU7k8cSQndc5mTXCIWHa_uc-TjDJYRtLl-RKXlVOTL5mI-WiiglTJRFGvAEXXnfLCt0BkYsC0T-4-k-mSSl9LqZBVj0n-XtnANItk--Gvyv2TNedRXhVojzV4R3s6nqe8F-Yg&q=screen+shot&sa=X&ved=2ahUKEwiK-86Hy-SPAxXRWqQEHfcYAwUQtKgLegQIFBAB&biw=935&bih=894&dpr=1"
    scraper.fetch(url)
    print("Fetch URL:", url, "is done.")

    os.makedirs(outputs_dir, exist_ok=True)
    text_fp = os.path.join(outputs_dir, "text_file.txt")
    text_file = open(text_fp, mode='w', encoding="utf-8")

    paragraphs = scraper.get_paragraphs()
    print("Extracted paragraphs:")
    for idx, p in enumerate(paragraphs, 1):
        print(f"  {idx}. {p:16s} " + str("..." if len(p) > 16 else ""))
        text_file.write(p + "\n\n")
    text_file.close()

    images = scraper.get_images()
    host = get_host_name(url)
    print("Extracted image links:")
    for idx, a in enumerate(images, 1):
        a = url_resolve(host, a)
        try:
            res_type = get_resource_type(a)
            print(f"  {idx}. {a} --> {res_type['mime_type']}")
            ext = res_type['mime_type'].split("/")[-1]
            if "." in ext:
                ext = ext.split('.')[-1]
            fn = a.split('/')[-1]
            fp = os.path.join(outputs_dir, str(fn + "." + ext))
            fp = download_file(a, fp)
            print("Download done at: \"" + fp + "\".")
        except KeyboardInterrupt as e:
            raise e
        except:
            print(f"  {idx}. {a} --> unknown.")
            continue

    links = scraper.get_links()
    host = get_host_name(url)
    print("Extracted links:")
    for idx, a in enumerate(links, 1):
        a = url_resolve(host, a)
        try:
            res_type = get_resource_type(a)
            print(f"  {idx}. {a} --> {res_type['mime_type']}")
            ext = res_type['mime_type'].split("/")[-1]
            if "." in ext:
                ext = ext.split('.')[-1]
            fn = a.split('/')[-1]
            fp = os.path.join(outputs_dir, str(fn + "." + ext))
            fp = download_file(a, fp)
            print("Download done at: \"" + fp + "\".")
        except KeyboardInterrupt as e:
            raise e
        except:
            print(f"  {idx}. {a} --> unknown.")
            continue
    return 0


if __name__ == '__main__':
    try:
        code = main()
        exit(code)
    except KeyboardInterrupt:
        print("\033[91mCanceled by user.\033[0m")
        exit(125)
    except Exception as e:  # noqa
        LOGGER.error("[" + e.__class__.__name__ + "]" + str(e))
        exit(1)
