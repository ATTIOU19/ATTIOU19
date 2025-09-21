#!/usr/bin/env python3
"""
PDF Image Extractor

A robust Python script for extracting images from PDF documents
with proper error handling, logging, and best practices for data engineering
workflows.

Dependencies:
    pip install PyMuPDF Pillow

Author: Data Engineering Script
Version: 1.0.0
"""

import os
import sys
import logging
import argparse
from datetime import datetime
from typing import List, Optional, Tuple
from pathlib import Path

try:
    import fitz  # PyMuPDF
    from PIL import Image
except ImportError as e:
    print(f"Required dependency missing: {e}")
    print("Please install dependencies: pip install PyMuPDF Pillow")
    sys.exit(1)


class PDFImageExtractor:
    """
    A class to extract images from PDF documents with comprehensive error handling
    and logging capabilities.
    """

    def __init__(self, output_dir: str = "extracted_images",
                 log_level: str = "INFO"):
        """
        Initialize the PDF Image Extractor.

        Args:
            output_dir (str): Directory to save extracted images
            log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.output_dir = Path(output_dir)
        self.setup_logging(log_level)
        self.setup_output_directory()

        # Supported image formats
        self.supported_formats = {
            'jpeg': 'jpg',
            'jpg': 'jpg',
            'png': 'png',
            'tiff': 'tiff',
            'bmp': 'bmp'
        }

        # Statistics tracking
        self.stats = {
            'total_pdfs_processed': 0,
            'total_images_extracted': 0,
            'failed_extractions': 0,
            'skipped_images': 0
        }

    def setup_logging(self, log_level: str) -> None:
        """Setup logging configuration."""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format=log_format,
            handlers=[
                logging.FileHandler(
                    f'pdf_extraction_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)

    def setup_output_directory(self) -> None:
        """Create output directory if it doesn't exist."""
        try:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            self.logger.info(f"Output directory ready: {self.output_dir}")
        except Exception as e:
            self.logger.error(f"Failed to create output directory: {e}")
            raise

    def validate_pdf_file(self, pdf_path: Path) -> bool:
        """
        Validate if the file is a valid PDF.

        Args:
            pdf_path (Path): Path to the PDF file

        Returns:
            bool: True if valid PDF, False otherwise
        """
        if not pdf_path.exists():
            self.logger.error(f"File does not exist: {pdf_path}")
            return False

        if not pdf_path.is_file():
            self.logger.error(f"Path is not a file: {pdf_path}")
            return False

        if pdf_path.suffix.lower() != '.pdf':
            self.logger.warning(f"File extension is not .pdf: {pdf_path}")
            return False

        try:
            # Try to open the PDF to validate it
            doc = fitz.open(pdf_path)
            doc.close()
            return True
        except Exception as e:
            self.logger.error(f"Invalid PDF file {pdf_path}: {e}")
            return False

    def extract_images_from_page(self, page: fitz.Page, pdf_name: str,
                                 page_num: int) -> List[str]:
        """
        Extract images from a single PDF page.

        Args:
            page (fitz.Page): PDF page object
            pdf_name (str): Name of the PDF file (without extension)
            page_num (int): Page number

        Returns:
            List[str]: List of extracted image file paths
        """
        extracted_files = []

        try:
            # Get list of images on the page
            image_list = page.get_images(full=True)

            if not image_list:
                self.logger.debug(
                    f"No images found on page {page_num + 1} of {pdf_name}")
                return extracted_files

            self.logger.info(
                f"Found {len(image_list)} images on page {page_num + 1} of {pdf_name}")

            for img_index, img in enumerate(image_list):
                try:
                    # Get image data
                    xref = img[0]
                    pix = fitz.Pixmap(page.parent, xref)

                    # Skip if image is too small (likely artifacts)
                    if pix.width < 10 or pix.height < 10:
                        self.logger.debug(
                            f"Skipping small image: {pix.width}x{pix.height}")
                        pix = None
                        self.stats['skipped_images'] += 1
                        continue

                    # Determine image format
                    if pix.n - pix.alpha < 4:  # GRAY or RGB
                        img_format = "png"
                    else:  # CMYK: convert to RGB first
                        pix_rgb = fitz.Pixmap(fitz.csRGB, pix)
                        pix = None
                        pix = pix_rgb
                        img_format = "png"

                    # Generate filename
                    filename = f"{pdf_name}_page_{page_num + 1:03d}_img_{img_index + 1:03d}.{img_format}"
                    filepath = self.output_dir / filename

                    # Save image
                    pix.save(str(filepath))
                    extracted_files.append(str(filepath))

                    self.logger.info(
                        f"Extracted: {filename} ({pix.width}x{pix.height})")
                    self.stats['total_images_extracted'] += 1

                    # Clean up
                    pix = None

                except Exception as e:
                    self.logger.error(
                        f"Failed to extract image {img_index + 1} from page {page_num + 1}: {e}")
                    self.stats['failed_extractions'] += 1
                    continue

        except Exception as e:
            self.logger.error(
                f"Error processing page {page_num + 1} of {pdf_name}: {e}")

        return extracted_files

    def extract_images_from_pdf(self, pdf_path: Path,
                                create_subdir: bool = True) -> List[str]:
        """
        Extract all images from a PDF document.

        :param pdf_path: Path to the PDF file.
        :param create_subdir: Create subdirectory for each PDF.

        :returns: List of all extracted image file paths.
        """
        if not self.validate_pdf_file(pdf_path):
            return []

        pdf_name = pdf_path.stem
        all_extracted_files = []

        # Create subdirectory for this PDF if requested
        if create_subdir:
            pdf_output_dir = self.output_dir / pdf_name
            pdf_output_dir.mkdir(exist_ok=True)
            original_output_dir = self.output_dir
            self.output_dir = pdf_output_dir

        try:
            self.logger.info(f"Processing PDF: {pdf_path}")

            # Open PDF document
            doc = fitz.open(pdf_path)

            self.logger.info(f"PDF has {len(doc)} pages")

            # Process each page
            for page_num in range(len(doc)):
                page = doc.load_page(page_num)
                extracted_files = self.extract_images_from_page(page, pdf_name,
                                                                page_num)
                all_extracted_files.extend(extracted_files)

            # Close document
            doc.close()

            self.stats['total_pdfs_processed'] += 1
            self.logger.info(
                f"Completed processing {pdf_path}. Extracted {len(all_extracted_files)} images.")

        except Exception as e:
            self.logger.error(f"Error processing PDF {pdf_path}: {e}")
        finally:
            # Restore original output directory if we created a subdirectory
            if create_subdir:
                self.output_dir = original_output_dir

        return all_extracted_files

    def process_directory(self, input_dir: str, recursive: bool = False,
                          create_subdirs: bool = True) -> None:
        """
        Process all PDF files in a directory.

        Args:
            input_dir (str): Directory containing PDF files
            recursive (bool): Search subdirectories recursively
            create_subdirs (bool): Create subdirectories for each PDF
        """
        input_path = Path(input_dir)

        if not input_path.exists():
            self.logger.error(f"Input directory does not exist: {input_dir}")
            return

        # Find PDF files
        pattern = "**/*.pdf" if recursive else "*.pdf"
        pdf_files = list(input_path.glob(pattern))

        if not pdf_files:
            self.logger.warning(f"No PDF files found in {input_dir}")
            return

        self.logger.info(f"Found {len(pdf_files)} PDF files to process")

        # Process each PDF
        for pdf_file in pdf_files:
            self.extract_images_from_pdf(pdf_file, create_subdirs)

        self.print_statistics()

    def process_single_pdf(self, pdf_path: str, create_subdir: bool = True) -> \
    List[str]:
        """
        Process a single PDF file.

        Args:
            pdf_path (str): Path to the PDF file
            create_subdir (bool): Create subdirectory for the PDF

        Returns:
            List[str]: List of extracted image file paths
        """
        pdf_file = Path(pdf_path)
        extracted_files = self.extract_images_from_pdf(pdf_file, create_subdir)
        self.print_statistics()
        return extracted_files

    def print_statistics(self) -> None:
        """Print extraction statistics."""
        self.logger.info("=== Extraction Statistics ===")
        self.logger.info(
            f"PDFs processed: {self.stats['total_pdfs_processed']}")
        self.logger.info(
            f"Images extracted: {self.stats['total_images_extracted']}")
        self.logger.info(
            f"Failed extractions: {self.stats['failed_extractions']}")
        self.logger.info(f"Skipped images: {self.stats['skipped_images']}")
        self.logger.info("=============================")


def main():
    """Main function to handle command line arguments and execute extraction."""
    parser = argparse.ArgumentParser(
        description="Extract images from PDF documents",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s file.pdf                     # Extract from single PDF
  %(prog)s -d /path/to/pdfs             # Extract from all PDFs in directory
  %(prog)s -d /path/to/pdfs -r          # Extract recursively from subdirectories
  %(prog)s file.pdf -o custom_output    # Custom output directory
  %(prog)s file.pdf --no-subdir         # Don't create subdirectories
        """
    )

    # Input arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("pdf_file", nargs="?",
                       help="Path to PDF file to process")
    group.add_argument("-d", "--directory",
                       help="Directory containing PDF files")

    # Output options
    parser.add_argument("-o", "--output", default="extracted_images",
                        help="Output directory for extracted images (default: extracted_images)")
    parser.add_argument("--no-subdir", action="store_true",
                        help="Don't create subdirectories for each PDF")

    # Processing options
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Process subdirectories recursively")

    # Logging options
    parser.add_argument("--log-level",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO", help="Logging level (default: INFO)")

    args = parser.parse_args()

    # Initialize extractor
    extractor = PDFImageExtractor(output_dir=args.output,
                                  log_level=args.log_level)

    try:
        if args.pdf_file:
            # Process single PDF
            extractor.process_single_pdf(args.pdf_file, not args.no_subdir)
        elif args.directory:
            # Process directory
            extractor.process_directory(args.directory, args.recursive,
                                        not args.no_subdir)

    except KeyboardInterrupt:
        extractor.logger.info("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        extractor.logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
