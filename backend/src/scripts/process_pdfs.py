#!/usr/bin/env python3
"""
CLI script to process downloaded PDFs and store them in the database.

This script:
1. Scans the MAS crawler download directory for PDFs
2. Extracts text from each PDF
3. Stores documents in the database with metadata
4. Queues documents for embedding

Usage:
    python -m src.scripts.process_pdfs --download-dir ./downloads
    python -m src.scripts.process_pdfs --download-dir ./downloads --batch-size 10
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.services.supabase_pdf_processor import SupabasePDFProcessor
from src.logging_config import setup_logging

logger = logging.getLogger(__name__)


def main():
    """Main entry point for PDF processing script"""

    parser = argparse.ArgumentParser(
        description="Process downloaded PDFs and store in database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process all PDFs in download directory
  python -m src.scripts.process_pdfs --download-dir ./downloads

  # Process only recent PDFs (last 100)
  python -m src.scripts.process_pdfs --download-dir ./downloads --batch-size 100

  # Process with specific source
  python -m src.scripts.process_pdfs --download-dir ./downloads --source MAS
        """
    )

    parser.add_argument(
        "--download-dir",
        type=str,
        required=True,
        help="Directory containing downloaded PDF files"
    )

    parser.add_argument(
        "--source",
        type=str,
        default="MAS",
        help="Ingestion source identifier (default: MAS)"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=None,
        help="Maximum number of PDFs to process (default: all)"
    )

    parser.add_argument(
        "--pattern",
        type=str,
        default="*.pdf",
        help="File pattern to match (default: *.pdf)"
    )

    parser.add_argument(
        "--log-level",
        type=str,
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        default="INFO",
        help="Logging level (default: INFO)"
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(level=args.log_level)

    logger.info(f"Starting PDF processing from {args.download_dir}")

    # Get list of PDF files
    download_path = Path(args.download_dir)

    if not download_path.exists():
        logger.error(f"Download directory does not exist: {args.download_dir}")
        sys.exit(1)

    pdf_files = sorted(download_path.glob(args.pattern), key=lambda p: p.stat().st_mtime, reverse=True)

    if args.batch_size:
        pdf_files = pdf_files[:args.batch_size]

    logger.info(f"Found {len(pdf_files)} PDF files to process")

    if len(pdf_files) == 0:
        logger.warning("No PDF files found. Exiting.")
        sys.exit(0)

    # Process each PDF
    successful = 0
    failed = 0
    duplicates = 0

    # Create processor (no database session needed - uses Supabase REST API)
    processor = SupabasePDFProcessor()

    for i, pdf_file in enumerate(pdf_files, 1):
        logger.info(f"[{i}/{len(pdf_files)}] Processing {pdf_file.name}")

        try:
            # Use file path as source URL for now
            # (In production, crawler should provide actual source URL)
            source_url = f"https://www.mas.gov.sg/{pdf_file.name}"

            response = processor.process_downloaded_pdf(
                pdf_path=str(pdf_file.absolute()),
                source_url=source_url,
                ingestion_source=args.source
            )

            if "Duplicate" in response.message:
                duplicates += 1
                logger.info(f"  → Duplicate: {response.document_id}")
            else:
                successful += 1
                logger.info(f"  → Success: {response.document_id} ({response.status.value})")

        except Exception as e:
            failed += 1
            logger.error(f"  → Failed: {str(e)}")
            continue

    # Print summary
    logger.info("\n" + "=" * 60)
    logger.info("PDF Processing Summary")
    logger.info("=" * 60)
    logger.info(f"Total files:      {len(pdf_files)}")
    logger.info(f"Successfully processed: {successful}")
    logger.info(f"Duplicates:       {duplicates}")
    logger.info(f"Failed:           {failed}")
    logger.info("=" * 60)

    if failed > 0:
        logger.warning(f"{failed} files failed to process. Check logs for details.")
        sys.exit(1)

    logger.info("All PDFs processed successfully!")
    sys.exit(0)


if __name__ == "__main__":
    main()
