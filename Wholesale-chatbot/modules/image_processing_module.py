import cv2
import numpy as np
import tempfile
import urllib.request
import logging
from typing import List, Dict, Optional
from botocore.exceptions import ClientError
from modules.s3_service import S3Service
from logging_config import configure_logger  # Updated import

# Configure logger for this module
logger = configure_logger("image_processing_module")
logger.info("ImageProcessor initialized.")

class ImageProcessor:
    def __init__(self, s3_service: S3Service):
        """Initialize with S3Service for catalog matching."""
        if not s3_service or not isinstance(s3_service, S3Service):
            raise ValueError("Invalid S3Service instance provided.")
        
        self.s3 = s3_service.s3
        self.bucket = s3_service.bucket
        self.folder = s3_service.folder
        self.design_catalog = self._load_catalog_features()

    def _load_catalog_features(self) -> List[Dict]:
        """Pre-load design features for matching."""
        catalog = [
            {"id": "Bukky_Dashiki", "name": "Bukky Dashiki"},
            {"id": "Cece_Dashiki", "name": "Cece Dashiki"},
            {"id": "Stripe_Dashiki_NP", "name": "Stripe Dashiki (NP)"},
            {"id": "Swiss_Dashiki", "name": "Swiss Dashiki"},
            {"id": "Dochi_Dashiki", "name": "Dochi Dashiki"}
        ]
        
        for design in catalog:
            try:
                with tempfile.NamedTemporaryFile(suffix='.jpeg') as tmp:
                    self.s3.download_file(
                        Bucket=self.bucket,
                        Key=f"{self.folder}{design['id']}.jpeg",
                        Filename=tmp.name
                    )
                    design['features'] = self._extract_features(tmp.name)
            except Exception as e:
                logger.warning(f"Couldn't load features for {design['name']}: {str(e)}")
                design['features'] = None
                
        return [d for d in catalog if d.get('features') is not None]

    def _extract_features(self, image_path: str) -> Optional[np.array]:
        """Extract visual features using OpenCV."""
        try:
            logger.debug(f"Extracting features from image: {image_path}")
            img = cv2.imread(image_path)
            if img is None:
                raise ValueError("Could not read image")
                
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            hist = cv2.calcHist([hsv], [0, 1], None, [50, 60], [0, 180, 0, 256])
            cv2.normalize(hist, hist)
            
            if hist is None or hist.size == 0:
                raise ValueError("Histogram extraction failed")
            
            logger.info(f"Features extracted successfully for image: {image_path}")
            return hist.flatten()
        except Exception as e:
            logger.error(f"Feature extraction failed for image {image_path}: {e}")
            return None

    def match_design(self, image_url: str, top_n: int = 3) -> List[Dict]:
        """Match customer's image against catalog."""
        if not image_url:
            logging.error("Invalid image URL provided.")
            return []
        
        try:
            with tempfile.NamedTemporaryFile(suffix='.jpeg') as tmp:
                urllib.request.urlretrieve(image_url, tmp.name)
                query_features = self._extract_features(tmp.name)
                if query_features is None:
                    return []
                
                matches = []
                for design in self.design_catalog:
                    if design.get('features') is None:
                        continue
                    
                    similarity = cv2.compareHist(
                        query_features.reshape(50, 60),
                        design['features'].reshape(50, 60),
                        cv2.HISTCMP_CORREL
                    )
                    matches.append((design, similarity))
                
                matches.sort(key=lambda x: x[1], reverse=True)
                logger.debug(f"Matching image from URL: {image_url}")
                logger.debug(f"Top {top_n} matches: {matches[:top_n]}")
                return [{"id": m[0]['id'], "name": m[0]['name'], "price": 15000, "similarity": float(m[1])} for m in matches[:top_n]]
        except Exception as e:
            logger.error(f"Matching failed for image URL {image_url}: {e}")
            return []

    def get_design_url(self, design_id: str) -> Optional[str]:
        """Generate secure temporary access to a design image."""
        try:
            return self.s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.bucket,
                    'Key': f"{self.folder}{design_id}.jpeg"
                },
                ExpiresIn=1800,
                HttpMethod='GET'
            )
        except ClientError as e:
            print(f"URL generation failed: {str(e)}")
            return None