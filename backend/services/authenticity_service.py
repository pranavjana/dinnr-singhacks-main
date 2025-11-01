"""
Authenticity and tamper detection service for images.
"""

import io
import json
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

import imagehash
import numpy as np
import requests
from PIL import Image
from PIL.ExifTags import TAGS

try:
    from backend.models.document import (
        ExifData, PHashResult, ELAResult,
        ReverseImageMatch, ReverseImageSearchResult,
        AIGenerationHeuristic, AuthenticityCheck
    )
except ModuleNotFoundError:
    from models.document import (
        ExifData, PHashResult, ELAResult,
        ReverseImageMatch, ReverseImageSearchResult,
        AIGenerationHeuristic, AuthenticityCheck
    )


class AuthenticityService:
    """Service for checking image authenticity and tampering."""

    def __init__(self, corpus_dir: str = "corpus"):
        """Initialize authenticity service.

        Args:
            corpus_dir: Directory containing known document hashes
        """
        self.corpus_dir = Path(corpus_dir)
        self.corpus_dir.mkdir(exist_ok=True)
        self._hash_db_path = self.corpus_dir / "phash_db.json"
        self._load_hash_db()

    def _load_hash_db(self):
        """Load perceptual hash database."""
        if self._hash_db_path.exists():
            with open(self._hash_db_path, "r") as f:
                self._hash_db = json.load(f)
        else:
            self._hash_db = {}

    def _save_hash_db(self):
        """Save perceptual hash database."""
        with open(self._hash_db_path, "w") as f:
            json.dump(self._hash_db, f, indent=2)

    def check_exif(self, image: Image.Image) -> ExifData:
        """Extract and analyze EXIF metadata from image.

        Args:
            image: PIL Image object

        Returns:
            ExifData with metadata and anomalies
        """
        try:
            exif_data = image._getexif()
            if not exif_data:
                return ExifData(present=False)

            # Extract common EXIF fields
            exif_dict = {}
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, tag_id)
                exif_dict[tag] = value

            # Check for anomalies
            anomalies = []

            # Check for missing camera info
            if "Make" not in exif_dict and "Model" not in exif_dict:
                anomalies.append("Missing camera make/model")

            # Check for software watermark
            software = exif_dict.get("Software", "")
            if any(ai_tool in software.lower() for ai_tool in ["midjourney", "stable diffusion", "dall-e", "photoshop"]):
                anomalies.append(f"AI/editing software detected: {software}")

            # Check for future dates
            if "DateTime" in exif_dict:
                try:
                    dt = datetime.strptime(str(exif_dict["DateTime"]), "%Y:%m:%d %H:%M:%S")
                    if dt > datetime.now():
                        anomalies.append("Future date in EXIF")
                except:
                    pass

            # Extract GPS coordinates if present
            gps_coords = None
            if "GPSInfo" in exif_dict:
                gps_coords = {"present": True}

            return ExifData(
                present=True,
                camera_make=str(exif_dict.get("Make", "")),
                camera_model=str(exif_dict.get("Model", "")),
                software=str(exif_dict.get("Software", "")),
                datetime=str(exif_dict.get("DateTime", "")),
                gps_coords=gps_coords,
                anomalies=anomalies
            )

        except Exception as e:
            return ExifData(present=False)

    def compute_phash(self, image: Image.Image) -> str:
        """Compute perceptual hash of image.

        Args:
            image: PIL Image object

        Returns:
            Hex string of perceptual hash
        """
        return str(imagehash.phash(image))

    def check_duplicates(self, phash_value: str, threshold: int = 5) -> PHashResult:
        """Check for duplicate/similar images in corpus.

        Args:
            phash_value: Perceptual hash to check
            threshold: Hamming distance threshold for similarity

        Returns:
            PHashResult with duplicates and similarity scores
        """
        duplicates = []
        similarities = []

        phash_obj = imagehash.hex_to_hash(phash_value)

        for stored_file, stored_hash in self._hash_db.items():
            stored_hash_obj = imagehash.hex_to_hash(stored_hash)
            distance = phash_obj - stored_hash_obj

            if distance <= threshold:
                similarity = 1.0 - (distance / 64.0)  # Normalize to 0-1
                duplicates.append({
                    "file": stored_file,
                    "hash": stored_hash,
                    "hamming_distance": int(distance)
                })
                similarities.append(similarity)

        return PHashResult(
            hash_value=phash_value,
            duplicates_found=duplicates,
            similarity_scores=similarities
        )

    def add_to_corpus(self, filename: str, image: Image.Image):
        """Add image hash to corpus database.

        Args:
            filename: Name of file to store
            image: PIL Image object
        """
        phash_value = self.compute_phash(image)
        self._hash_db[filename] = phash_value
        self._save_hash_db()

    def ela_analysis(self, image: Image.Image, quality: int = 95) -> ELAResult:
        """Perform Error Level Analysis to detect tampering.

        Args:
            image: PIL Image object
            quality: JPEG quality for recompression

        Returns:
            ELAResult with tampering indicators
        """
        try:
            # Convert to RGB if necessary
            if image.mode != "RGB":
                image = image.convert("RGB")

            # Save at specified quality
            buffer = io.BytesIO()
            image.save(buffer, "JPEG", quality=quality)
            buffer.seek(0)
            resaved_image = Image.open(buffer)

            # Compute difference
            original_array = np.array(image, dtype=np.float32)
            resaved_array = np.array(resaved_image, dtype=np.float32)

            diff = np.abs(original_array - resaved_array)

            # Calculate statistics
            mean_score = float(np.mean(diff))
            variance = float(np.var(diff))

            # Threshold-based anomaly detection
            # Higher mean and variance suggest tampering
            anomaly_detected = mean_score > 35 or variance > 1200
            confidence = min(mean_score / 100, 1.0)  # Normalize

            return ELAResult(
                mean_score=mean_score,
                variance=variance,
                anomaly_detected=anomaly_detected,
                confidence=confidence
            )

        except Exception as e:
            return ELAResult(
                mean_score=0.0,
                variance=0.0,
                anomaly_detected=False,
                confidence=0.0
            )

    def reverse_image_search(self, image: Image.Image) -> ReverseImageSearchResult:
        """Perform reverse image search using Google Cloud Vision API.

        Args:
            image: PIL Image object

        Returns:
            ReverseImageSearchResult with matches

        Note:
            Requires GOOGLE_APPLICATION_CREDENTIALS environment variable
            pointing to a service account JSON key file.
        """
        import logging
        logger = logging.getLogger(__name__)

        try:
            from google.cloud import vision

            logger.info("Starting reverse image search...")

            # Convert PIL image to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr.seek(0)
            content = img_byte_arr.read()

            logger.info(f"Image converted to bytes: {len(content)} bytes")

            # Create Vision API client
            client = vision.ImageAnnotatorClient()
            vision_image = vision.Image(content=content)

            logger.info("Calling Google Vision API web_detection...")

            # Perform web detection
            response = client.web_detection(image=vision_image)
            web_detection = response.web_detection

            logger.info(f"API response received: full_matching={len(web_detection.full_matching_images)}, partial={len(web_detection.partial_matching_images)}, pages={len(web_detection.pages_with_matching_images)}")

            exact_matches = []
            partial_matches = []

            # Process full matching images
            if web_detection.full_matching_images:
                for match in web_detection.full_matching_images[:5]:
                    exact_matches.append(ReverseImageMatch(
                        url=match.url,
                        page_title="",
                        source="Google Vision - Full Match"
                    ))

            # Process partial matching images
            if web_detection.partial_matching_images:
                for match in web_detection.partial_matching_images[:5]:
                    partial_matches.append(ReverseImageMatch(
                        url=match.url,
                        page_title="",
                        source="Google Vision - Partial Match"
                    ))

            # Process pages with matching images
            if web_detection.pages_with_matching_images:
                for page in web_detection.pages_with_matching_images[:5]:
                    if page.url not in [m.url for m in exact_matches + partial_matches]:
                        partial_matches.append(ReverseImageMatch(
                            url=page.url,
                            page_title=page.page_title if hasattr(page, 'page_title') else "",
                            source="Google Vision - Page Match"
                        ))

            total_matches = len(exact_matches) + len(partial_matches)

            # Determine risk level
            if total_matches == 0:
                risk = "Low"
            elif total_matches <= 3:
                risk = "Med"
            else:
                risk = "High"

            return ReverseImageSearchResult(
                exact_matches=exact_matches,
                partial_matches=partial_matches,
                total_matches=total_matches,
                authenticity_risk=risk
            )

        except ImportError as e:
            # Google Cloud Vision not installed
            logger.error(f"ImportError in reverse_image_search: {e}")
            return ReverseImageSearchResult(
                exact_matches=[],
                partial_matches=[],
                total_matches=0,
                authenticity_risk="Low"
            )
        except Exception as e:
            # API error or credentials not configured
            # Fail gracefully - don't break the whole analysis
            logger.error(f"Exception in reverse_image_search: {type(e).__name__}: {e}")
            return ReverseImageSearchResult(
                exact_matches=[],
                partial_matches=[],
                total_matches=0,
                authenticity_risk="Low"
            )

    def ai_generation_heuristic(self, image: Image.Image, exif: ExifData) -> AIGenerationHeuristic:
        """Lightweight AI generation detection heuristic.

        Args:
            image: PIL Image object
            exif: EXIF data

        Returns:
            AIGenerationHeuristic with likelihood and indicators
        """
        indicators = []
        score = 0.0

        # Check 1: Missing EXIF
        if not exif.present:
            indicators.append("No EXIF metadata")
            score += 0.3

        # Check 2: EXIF software indicates AI
        if exif.present and exif.anomalies:
            for anomaly in exif.anomalies:
                if "AI" in anomaly or "software" in anomaly.lower():
                    indicators.append(anomaly)
                    score += 0.5

        # Check 3: Uniform noise pattern (simple check)
        try:
            # Convert to grayscale and check noise
            gray = image.convert("L")
            img_array = np.array(gray)
            noise = np.std(img_array)

            if noise < 5:  # Very low noise - suspicious
                indicators.append("Unusually low noise (< 5)")
                score += 0.2
        except:
            pass

        # Determine confidence
        if score < 0.3:
            confidence = "Low"
        elif score < 0.6:
            confidence = "Med"
        else:
            confidence = "High"

        return AIGenerationHeuristic(
            likelihood=min(score, 1.0),
            indicators=indicators,
            confidence=confidence
        )

    def check_authenticity(self, image: Image.Image) -> AuthenticityCheck:
        """Perform comprehensive authenticity check.

        Args:
            image: PIL Image object

        Returns:
            AuthenticityCheck with all results
        """
        # EXIF check
        exif = self.check_exif(image)

        # pHash and duplicate check
        phash_value = self.compute_phash(image)
        phash_result = self.check_duplicates(phash_value)

        # ELA tampering detection
        ela = self.ela_analysis(image)

        # Reverse image search (placeholder)
        reverse_search = self.reverse_image_search(image)

        # AI generation heuristic
        ai_gen = self.ai_generation_heuristic(image, exif)

        return AuthenticityCheck(
            exif=exif,
            phash=phash_result,
            ela=ela,
            reverse_search=reverse_search,
            ai_generation=ai_gen,
            applicable=True
        )


# Singleton instance
authenticity_service = AuthenticityService()
