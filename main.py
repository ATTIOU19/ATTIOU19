import os
import logging
import logging.config
import argparse
from pathlib import Path

from tqdm import tqdm
import numpy as np
from PIL import Image

from .scripersite import (
    WebScraper, get_resource_type, get_host_name, url_resolve, download_file,
    )
from .imgext import PDFImageExtractor
from .pdf2img import ConversionConfig, PDFPageConverter
from .ocr import Processor, StreamTranscription


logging.config.fileConfig('logging.conf')
logging.basicConfig(level=logging.warning)
LOGGER = logging.getLogger('')


def read_text_from_image(ocr: StreamTranscription, image_file: str) -> str:
    image = Image.open(image_file).convert("RGB")
    image = np.array(image)
    streamers = ocr.predict([image], return_result=False)
    print("\tReading character of image from \"" + image_file + "\"...")
    print("\n\033[93m")
    for i, streamer in enumerate(streamers, 1):
        text_read = ""
        for text in streamer:
            text_read += text
            print(text, end='', flush=True)
    print("\033[0m")
    return text_read


def main():
    """Main function to run archimed runtime on a link."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "url", type=str,
        help="The URL of the web page that you want to extract data"
        )
    parser.add_argument(
        "-o", "--outputs", type=str, default="outputs",
        help=("The path to the output directory which will content"
             "the results of this data extraction.")
        )
    args = parser.parse_args()
    url = args.url
    outputs_dir = Path(args.outputs)
    outputs_dir.mkdir(exist_ok=True)

    # WEB SCRAPPING:
    scraper = WebScraper()
    scraper.fetch(url)
    scrpped_text_fp = outputs_dir / "scrapped_text.txt"
    scrpped_text_file = open(scrpped_text_fp, mode='w', encoding="utf-8")

    paragraphs = scraper.get_paragraphs()
    print("\n** Extracted paragraphs:")
    for idx, p in enumerate(paragraphs, 1):
        print(f"\t{idx}. {p:16s} " + str("..." if len(p) > 16 else ""))
        scrpped_text_file.write(p + "\n\n")
    scrpped_text_file.close()

    images = scraper.get_images()
    host = get_host_name(url)
    link_images = []
    print("\n** Extracted image links:")
    images_iterator = tqdm(list(images))
    for idx, a in enumerate(images_iterator, 1):
        a = url_resolve(host, a)
        try:
            res_type = get_resource_type(a)
            mime_type = res_type['mime_type']
            images_iterator.write(f"\t{idx}. {a} --> {res_type['mime_type']}")
            supported_format = (
                'image/png', 'image/jpg', 'image/jpeg', 'image/webp',
                )
            if mime_type in supported_format:
                ext = mime_type.split("/")[-1]
                if "." in ext:
                    ext = ext.split('.')[-1]
                fn = a.split('/')[-1]
                fp = os.path.join(outputs_dir, str(fn + "." + ext))
                images_iterator.set_description(f"Downloading of {fn:8s}")
                fp = download_file(a, fp)
                link_images.append((mime_type, fp))
                images_iterator.set_description()
                images_iterator.write("\tDownload done at: \"" + fp + "\".")
        except KeyboardInterrupt as e:
            print(
                "\t\033[91mImages downloading canceled by user!\033[0m"
                )
            break
        except:
            images_iterator.write(f"\t{idx}. {a} --> unknown.")
            continue

    links = scraper.get_links()
    link_files = []
    host = get_host_name(url)
    print("\n** Extracted links:")
    links_iterator = tqdm(list(links))
    for idx, a in enumerate(links_iterator, 1):
        a = url_resolve(host, a)
        try:
            res_type = get_resource_type(a)
            mime_type = res_type['mime_type']
            links_iterator.write(f"\t{idx}. {a} --> {mime_type}")
            supported_format = (
                'application/pdf', 'text/csv', "text/plain"
                )
            if mime_type in supported_format:
                ext = mime_type.split("/")[-1]
                if "." in ext:
                    ext = ext.split('.')[-1]
                fn = a.split('/')[-1]
                fp = os.path.join(outputs_dir, str(fn + "." + ext))
                links_iterator.set_description(f"Downloading of {fn:8s}")
                fp = download_file(a, fp)
                link_files.append((mime_type, fp))
                links_iterator.set_description()
                links_iterator.write("\tDownload done at: \"" + fp + "\".")
        except KeyboardInterrupt as e:
            print(
                "\t\033[91mLink scrapping and document downloading "
                "canceled by user!\033[0m"
                )
            break
        except:
            links_iterator.write(f"\t{idx}. {a} --> unknown.")
            continue

    
    # OCR applying to images:
    if link_images:
        ocr_processor = Processor()
        ocr = StreamTranscription(ocr_processor, max_new_tokens=8192)
        texts_read = []
        print("Text reading from images:")
        for _, image_file in link_images:
            text = read_text_from_image(ocr, image_file)
            texts_read.append(text)
            print("\t", "-" * 80)
        ocr.shutdown()
        print("\n")
    
    # Convert all documents page into images:
    if link_files:
        # Initialize extractor
        extractor = PDFImageExtractor(
            output_dir=outputs_dir, log_level="WARNING"
            )
        link_files_iter = tqdm(link_files)
        for mime_type, document_file in link_files:
            if mime_type in ("application/pdf",):

                link_files_iter.write("")


if __name__ == '__main__':
    main()
