#!/usr/bin/env python3
"""
PDF Pages to Images Converter

A robust Python script for converting PDF pages to high-quality images with proper error handling,
logging, and best practices for data engineering workflows.

Dependencies:
    pip install PyMuPDF Pillow pdf2image

Author: Data Engineering Script
Version: 1.0.0
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import argparse
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from dataclasses import dataclass, asdict

try:
    import fitz  # PyMuPDF
    from PIL import Image
    from pdf2image import convert_from_path
    import pdf2image.exceptions
except ImportError as e:
    print(f"Required dependency missing: {e}")
    print("Please install dependencies: pip install PyMuPDF Pillow pdf2image")
    print(
        "Note: pdf2image requires poppler-utils (Linux/Mac) or poppler for Windows")
    sys.exit(1)


@dataclass
class ConversionConfig:
    """Configuration class for PDF to image conversion."""
    dpi: int = 300
    format: str = "PNG"
    quality: int = 95
    use_cropbox: bool = True
    transparent: bool = False
    thread_count: int = 4
    memory_limit: str = "1GB"


@dataclass
class ConversionStats:
    """Statistics tracking for conversion process."""
    total_pdfs_processed: int = 0
    total_pages_converted: int = 0
    failed_conversions: int = 0
    skipped_pages: int = 0
    processing_time: float = 0.0


class PDFPageConverter:
    """
    A class to convert PDF pages to images with comprehensive error handling,
    performance optimization, and logging capabilities.
    """
    def __init__(self,
                 output_dir: str = "pdf_pages",
                 config: Optional[ConversionConfig] = None,
                 log_level: str = "INFO"):
        """
        Initialize the PDF Page Converter.

        Args:
            output_dir (str): Directory to save converted images
            config (ConversionConfig): Configuration for conversion parameters
            log_level (str): Logging level (DEBUG, INFO, WARNING, ERROR)
        """
        self.output_dir = Path(output_dir)
        self.config = config or ConversionConfig()
        self.setup_logging(log_level)
        self.setup_output_directory()

        # Supported output formats
        self.supported_formats = {
            'PNG': {'extension': 'png', 'pillow_format': 'PNG'},
            'JPEG': {'extension': 'jpg', 'pillow_format': 'JPEG'},
            'JPG': {'extension': 'jpg', 'pillow_format': 'JPEG'},
            'TIFF': {'extension': 'tiff', 'pillow_format': 'TIFF'},
            'BMP': {'extension': 'bmp', 'pillow_format': 'BMP'},
            'WEBP': {'extension': 'webp', 'pillow_format': 'WEBP'}
        }

        # Validate format
        if self.config.format.upper() not in self.supported_formats:
            self.logger.warning(
                f"Unsupported format {self.config.format}, using PNG")
            self.config.format = "PNG"

        # Statistics tracking
        self.stats = ConversionStats()

        # Conversion methods available
        self.conversion_methods = ['pymupdf', 'pdf2image']
        self.default_method = 'pymupdf'

    def setup_logging(self, log_level: str) -> None:
        """Setup logging configuration."""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

        # Create logs directory
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format=log_format,
            handlers=[
                logging.FileHandler(
                    logs_dir / f'pdf_page_conversion_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log'
                ),
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

    def validate_pdf_file(self, pdf_path: Path) -> Tuple[bool, Optional[int]]:
        """
        Validate if the file is a valid PDF and get page count.

        Args:
            pdf_path (Path): Path to the PDF file

        Returns:
            Tuple[bool, Optional[int]]: (is_valid, page_count)
        """
        if not pdf_path.exists():
            self.logger.error(f"File does not exist: {pdf_path}")
            return False, None

        if not pdf_path.is_file():
            self.logger.error(f"Path is not a file: {pdf_path}")
            return False, None

        if pdf_path.suffix.lower() != '.pdf':
            self.logger.warning(f"File extension is not .pdf: {pdf_path}")
            return False, None

        try:
            # Try to open the PDF to validate it and get page count
            doc = fitz.open(pdf_path)
            page_count = len(doc)
            doc.close()
            return True, page_count
        except Exception as e:
            self.logger.error(f"Invalid PDF file {pdf_path}: {e}")
            return False, None

    def convert_page_pymupdf(self,
                             pdf_path: Path,
                             page_num: int,
                             pdf_name: str) -> Optional[str]:
        """
        Convert a single PDF page to image using PyMuPDF.

        Args:
            pdf_path (Path): Path to the PDF file
            page_num (int): Page number (0-indexed)
            pdf_name (str): Name of the PDF file (without extension)

        Returns:
            Optional[str]: Path to the converted image file, None if failed
        """
        try:
            # Open PDF document
            doc = fitz.open(pdf_path)
            page = doc.load_page(page_num)

            # Create transformation matrix for desired DPI
            zoom = self.config.dpi / 72.0
            mat = fitz.Matrix(zoom, zoom)

            # Render page to pixmap
            pix = page.get_pixmap(
                matrix=mat,
                alpha=self.config.transparent,
                clip=page.cropbox if self.config.use_cropbox else None
            )

            # Generate filename
            format_info = self.supported_formats[self.config.format.upper()]
            filename = f"{pdf_name}_page_{page_num + 1:04d}.{format_info['extension']}"
            filepath = self.output_dir / filename

            # Convert to PIL Image for better format support and quality control
            img_data = pix.tobytes("ppm")
            pil_img = Image.open(io.BytesIO(img_data)) if img_data else None

            if pil_img is None:
                # Fallback: save directly from pixmap
                pix.save(str(filepath))
            else:
                # Save with PIL for better quality control
                save_kwargs = {}
                if self.config.format.upper() in ['JPEG', 'JPG']:
                    save_kwargs['quality'] = self.config.quality
                    save_kwargs['optimize'] = True
                elif self.config.format.upper() == 'PNG':
                    save_kwargs['optimize'] = True

                pil_img.save(str(filepath), format_info['pillow_format'],
                             **save_kwargs)

            # Clean up
            pix = None
            doc.close()
            if pil_img:
                pil_img.close()

            # Get file size for logging
            file_size = filepath.stat().st_size / 1024  # KB

            self.logger.debug(
                f"Converted page {page_num + 1} -> {filename} ({file_size:.1f} KB)")
            return str(filepath)

        except Exception as e:
            self.logger.error(
                f"Failed to convert page {page_num + 1} using PyMuPDF: {e}")
            return None

    def convert_pages_pdf2image(self,
                                pdf_path: Path,
                                pdf_name: str,
                                page_range: Optional[
                                    Tuple[int, int]] = None) -> List[str]:
        """
        Convert PDF pages to images using pdf2image library.

        Args:
            pdf_path (Path): Path to the PDF file
            pdf_name (str): Name of the PDF file (without extension)
            page_range (Optional[Tuple[int, int]]): (first_page, last_page) 1-indexed

        Returns:
            List[str]: List of converted image file paths
        """
        converted_files = []

        try:
            # Convert PDF to images
            images = convert_from_path(
                str(pdf_path),
                dpi=self.config.dpi,
                first_page=page_range[0] if page_range else None,
                last_page=page_range[1] if page_range else None,
                fmt=self.config.format.lower(),
                use_cropbox=self.config.use_cropbox,
                transparent=self.config.transparent
            )

            format_info = self.supported_formats[self.config.format.upper()]

            for i, image in enumerate(images):
                page_num = (page_range[0] if page_range else 1) + i
                filename = f"{pdf_name}_page_{page_num:04d}.{format_info['extension']}"
                filepath = self.output_dir / filename

                # Save with quality settings
                save_kwargs = {}
                if self.config.format.upper() in ['JPEG', 'JPG']:
                    save_kwargs['quality'] = self.config.quality
                    save_kwargs['optimize'] = True
                elif self.config.format.upper() == 'PNG':
                    save_kwargs['optimize'] = True

                image.save(str(filepath), format_info['pillow_format'],
                           **save_kwargs)
                converted_files.append(str(filepath))

                # Get file size for logging
                file_size = filepath.stat().st_size / 1024  # KB
                self.logger.debug(
                    f"Converted page {page_num} -> {filename} ({file_size:.1f} KB)")

        except pdf2image.exceptions.PDFInfoNotInstalledError:
            self.logger.error(
                "pdf2image requires poppler-utils to be installed")
            return []
        except Exception as e:
            self.logger.error(f"Failed to convert PDF using pdf2image: {e}")
            return []

        return converted_files

    def convert_pdf_pages(self,
                          pdf_path: Path,
                          method: str = None,
                          page_range: Optional[Tuple[int, int]] = None,
                          create_subdir: bool = True) -> List[str]:
        """
        Convert all pages of a PDF to images.

        Args:
            pdf_path (Path): Path to the PDF file
            method (str): Conversion method ('pymupdf' or 'pdf2image')
            page_range (Optional[Tuple[int, int]]): Range of pages to convert (1-indexed)
            create_subdir (bool): Create subdirectory for each PDF

        Returns:
            List[str]: List of converted image file paths
        """
        start_time = datetime.now()

        # Validate PDF
        is_valid, page_count = self.validate_pdf_file(pdf_path)
        if not is_valid:
            return []

        pdf_name = pdf_path.stem
        method = method or self.default_method

        # Validate page range
        if page_range:
            start_page, end_page = page_range
            if start_page < 1 or end_page > page_count or start_page > end_page:
                self.logger.error(
                    f"Invalid page range {page_range} for PDF with {page_count} pages")
                return []
            page_count = end_page - start_page + 1

        # Create subdirectory for this PDF if requested
        original_output_dir = None
        if create_subdir:
            pdf_output_dir = self.output_dir / pdf_name
            pdf_output_dir.mkdir(exist_ok=True)
            original_output_dir = self.output_dir
            self.output_dir = pdf_output_dir

        self.logger.info(
            f"Converting {page_count} pages from {pdf_path} using {method}")

        converted_files = []

        try:
            if method == 'pdf2image':
                # Use pdf2image for batch conversion
                converted_files = self.convert_pages_pdf2image(pdf_path,
                                                               pdf_name,
                                                               page_range)

            else:  # pymupdf
                # Use PyMuPDF for page-by-page conversion
                if self.config.thread_count > 1:
                    # Multi-threaded conversion
                    converted_files = self._convert_pages_threaded(pdf_path,
                                                                   pdf_name,
                                                                   page_range)
                else:
                    # Single-threaded conversion
                    start_page = page_range[0] - 1 if page_range else 0
                    end_page = page_range[1] if page_range else page_count

                    for page_num in range(start_page, end_page):
                        result = self.convert_page_pymupdf(pdf_path, page_num,
                                                           pdf_name)
                        if result:
                            converted_files.append(result)
                            self.stats.total_pages_converted += 1
                        else:
                            self.stats.failed_conversions += 1

            self.stats.total_pdfs_processed += 1

            # Calculate processing time
            processing_time = (datetime.now() - start_time).total_seconds()
            self.stats.processing_time += processing_time

            success_count = len(converted_files)
            self.logger.info(
                f"Completed {pdf_path}: {success_count}/{page_count} pages converted "
                f"in {processing_time:.2f}s ({processing_time / page_count:.2f}s per page)"
            )

        except Exception as e:
            self.logger.error(f"Error converting PDF {pdf_path}: {e}")

        finally:
            # Restore original output directory
            if original_output_dir:
                self.output_dir = original_output_dir

        return converted_files

    def _convert_pages_threaded(self,
                                pdf_path: Path,
                                pdf_name: str,
                                page_range: Optional[
                                    Tuple[int, int]] = None) -> List[str]:
        """
        Convert pages using multiple threads.

        Args:
            pdf_path (Path): Path to the PDF file
            pdf_name (str): Name of the PDF file
            page_range (Optional[Tuple[int, int]]): Range of pages to convert

        Returns:
            List[str]: List of converted image file paths
        """
        converted_files = []

        # Determine page range
        _, total_pages = self.validate_pdf_file(pdf_path)
        if page_range:
            start_page, end_page = page_range[0] - 1, page_range[1]
        else:
            start_page, end_page = 0, total_pages

        page_numbers = list(range(start_page, end_page))

        # Convert pages in parallel
        with ThreadPoolExecutor(
                max_workers=self.config.thread_count) as executor:
            # Submit all tasks
            future_to_page = {
                executor.submit(self.convert_page_pymupdf, pdf_path, page_num,
                                pdf_name): page_num
                for page_num in page_numbers
            }

            # Collect results
            for future in as_completed(future_to_page):
                page_num = future_to_page[future]
                try:
                    result = future.result()
                    if result:
                        converted_files.append(result)
                        self.stats.total_pages_converted += 1
                    else:
                        self.stats.failed_conversions += 1
                except Exception as e:
                    self.logger.error(
                        f"Thread error for page {page_num + 1}: {e}")
                    self.stats.failed_conversions += 1

        # Sort files by page number for consistent ordering
        converted_files.sort()
        return converted_files

    def process_directory(self,
                          input_dir: str,
                          recursive: bool = False,
                          method: str = None,
                          create_subdirs: bool = True) -> None:
        """
        Process all PDF files in a directory.

        Args:
            input_dir (str): Directory containing PDF files
            recursive (bool): Search subdirectories recursively
            method (str): Conversion method to use
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
        for i, pdf_file in enumerate(pdf_files, 1):
            self.logger.info(
                f"Processing {i}/{len(pdf_files)}: {pdf_file.name}")
            self.convert_pdf_pages(pdf_file, method,
                                   create_subdir=create_subdirs)

        self.save_conversion_report()
        self.print_statistics()

    def save_conversion_report(self) -> None:
        """Save detailed conversion report as JSON."""
        report_data = {
            'timestamp': datetime.now().isoformat(),
            'configuration': asdict(self.config),
            'statistics': asdict(self.stats),
            'output_directory': str(self.output_dir)
        }

        report_file = self.output_dir / 'conversion_report.json'
        try:
            with open(report_file, 'w') as f:
                json.dump(report_data, f, indent=2)
            self.logger.info(f"Conversion report saved: {report_file}")
        except Exception as e:
            self.logger.error(f"Failed to save report: {e}")

    def print_statistics(self) -> None:
        """Print conversion statistics."""
        self.logger.info("=== Conversion Statistics ===")
        self.logger.info(f"PDFs processed: {self.stats.total_pdfs_processed}")
        self.logger.info(
            f"Pages converted: {self.stats.total_pages_converted}")
        self.logger.info(
            f"Failed conversions: {self.stats.failed_conversions}")
        self.logger.info(
            f"Total processing time: {self.stats.processing_time:.2f}s")

        if self.stats.total_pages_converted > 0:
            avg_time = self.stats.processing_time / self.stats.total_pages_converted
            self.logger.info(f"Average time per page: {avg_time:.2f}s")

        self.logger.info("=============================")


# Add missing import
import io


def main():
    """Main function to handle command line arguments and execute conversion."""
    parser = argparse.ArgumentParser(
        description="Convert PDF pages to images",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s file.pdf                                    # Convert all pages
  %(prog)s file.pdf --pages 1-10                      # Convert pages 1-10
  %(prog)s -d /path/to/pdfs                           # Convert all PDFs in directory
  %(prog)s file.pdf --dpi 600 --format JPEG           # High DPI JPEG output
  %(prog)s file.pdf --method pdf2image --threads 8    # Use pdf2image with 8 threads
  %(prog)s file.pdf -o custom_output --no-subdir      # Custom output, no subdirectories
        """
    )

    # Input arguments
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("pdf_file", nargs="?",
                       help="Path to PDF file to process")
    group.add_argument("-d", "--directory",
                       help="Directory containing PDF files")

    # Output options
    parser.add_argument("-o", "--output", default="pdf_pages",
                        help="Output directory for converted images (default: pdf_pages)")
    parser.add_argument("--no-subdir", action="store_true",
                        help="Don't create subdirectories for each PDF")

    # Conversion options
    parser.add_argument("--dpi", type=int, default=300,
                        help="DPI for image conversion (default: 300)")
    parser.add_argument("--format",
                        choices=["PNG", "JPEG", "JPG", "TIFF", "BMP", "WEBP"],
                        default="PNG",
                        help="Output image format (default: PNG)")
    parser.add_argument("--quality", type=int, default=95,
                        help="JPEG quality 1-100 (default: 95)")
    parser.add_argument("--pages",
                        help="Page range to convert (e.g., '1-10', '5-', '-20')")
    parser.add_argument("--method", choices=["pymupdf", "pdf2image"],
                        default="pymupdf",
                        help="Conversion method (default: pymupdf)")
    parser.add_argument("--threads", type=int, default=4,
                        help="Number of threads for conversion (default: 4)")

    # Processing options
    parser.add_argument("-r", "--recursive", action="store_true",
                        help="Process subdirectories recursively")
    parser.add_argument("--transparent", action="store_true",
                        help="Preserve transparency (PNG only)")

    # Logging options
    parser.add_argument("--log-level",
                        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
                        default="INFO", help="Logging level (default: INFO)")

    args = parser.parse_args()

    # Parse page range
    page_range = None
    if args.pages:
        try:
            if '-' in args.pages:
                parts = args.pages.split('-')
                if len(parts) == 2:
                    start = int(parts[0]) if parts[0] else 1
                    end = int(parts[1]) if parts[1] else None
                    if end is None:
                        # Handle open-ended range like '5-'
                        page_range = (start, 9999)  # Large number for end
                    else:
                        page_range = (start, end)
                else:
                    raise ValueError("Invalid page range format")
            else:
                # Single page
                page_num = int(args.pages)
                page_range = (page_num, page_num)
        except ValueError:
            print(f"Invalid page range: {args.pages}")
            print("Use format: '1-10', '5-', '-20', or '5'")
            sys.exit(1)

    # Create configuration
    config = ConversionConfig(
        dpi=args.dpi,
        format=args.format,
        quality=args.quality,
        transparent=args.transparent,
        thread_count=args.threads
    )

    # Initialize converter
    converter = PDFPageConverter(output_dir=args.output, config=config,
                                 log_level=args.log_level)

    try:
        if args.pdf_file:
            # Process single PDF
            converter.convert_pdf_pages(
                Path(args.pdf_file),
                method=args.method,
                page_range=page_range,
                create_subdir=not args.no_subdir
            )
            converter.print_statistics()
        elif args.directory:
            # Process directory
            converter.process_directory(
                args.directory,
                args.recursive,
                args.method,
                not args.no_subdir
            )

    except KeyboardInterrupt:
        converter.logger.info("Process interrupted by user")
        sys.exit(1)
    except Exception as e:
        converter.logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
