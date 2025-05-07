import unittest
from unittest.mock import MagicMock, patch
from modules.image_processing_module import FashionDesignMatcher
from modules.s3_service import S3Service

class TestFashionDesignMatcher(unittest.TestCase):
    @patch("modules.image_processing_module.cv2.imread")
    @patch("modules.image_processing_module.S3Service")
    def test_feature_extraction(self, mock_s3_service, mock_cv2_imread):
        """Test feature extraction logic."""
        mock_cv2_imread.return_value = MagicMock()  # Mock image data
        mock_s3_service.s3 = MagicMock()
        mock_s3_service.bucket = "test-bucket"
        mock_s3_service.folder = "test-folder/"
        
        matcher = FashionDesignMatcher(mock_s3_service)
        features = matcher._extract_features("test_image.jpeg")
        
        self.assertIsNotNone(features)
        self.assertGreater(len(features), 0)

    @patch("modules.image_processing_module.S3Service")
    def test_catalog_loading(self, mock_s3_service):
        """Test catalog loading with valid S3Service."""
        mock_s3_service.s3 = MagicMock()
        mock_s3_service.bucket = "test-bucket"
        mock_s3_service.folder = "test-folder/"
        
        matcher = FashionDesignMatcher(mock_s3_service)
        self.assertGreater(len(matcher.design_catalog), 0)

    @patch("modules.image_processing_module.urllib.request.urlretrieve")
    @patch("modules.image_processing_module.S3Service")
    def test_match_design(self, mock_s3_service, mock_urlretrieve):
        """Test design matching logic."""
        mock_s3_service.s3 = MagicMock()
        mock_s3_service.bucket = "test-bucket"
        mock_s3_service.folder = "test-folder/"
        mock_urlretrieve.return_value = None
        
        matcher = FashionDesignMatcher(mock_s3_service)
        matches = matcher.match_design("http://example.com/test_image.jpeg")
        
        self.assertIsInstance(matches, list)
        self.assertLessEqual(len(matches), 3)

if __name__ == "__main__":
    unittest.main()