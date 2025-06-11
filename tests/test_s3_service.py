import unittest
from unittest.mock import patch, MagicMock
from modules.s3_service import S3Service
from config import config

class TestS3Service(unittest.TestCase):
    @patch("modules.s3_service.boto3.client")
    def setUp(self, mock_boto_client):
        """Set up the S3Service instance with mocked boto3 client."""
        self.mock_s3 = MagicMock()
        mock_boto_client.return_value = self.mock_s3
        self.s3_service = S3Service()

    @patch("modules.s3_service.urllib.request.urlretrieve")
    @patch("modules.s3_service.magic.Magic")
    def test_upload_from_url(self, mock_magic, mock_urlretrieve):
        """Test uploading a file from a URL to S3."""
        mock_magic.return_value.from_file.return_value = "image/jpeg"
        mock_urlretrieve.return_value = None
        
        url = "https://salescabal.s3.eu-west-3.amazonaws.com/stores/187378/products/221f7e6aecba07ad3e6c605056bc7c02e5cce3e4.jpeg"
        filename = "test_image.jpg"
        s3_url = self.s3_service.upload_from_url(url, filename)
        
        self.mock_s3.upload_file.assert_called_once()
        self.assertIn(config.AWS['bucket'], s3_url)
        self.assertIn(config.AWS['designs_folder'], s3_url)

    def test_generate_presigned_url(self):
        """Test generating a presigned URL."""
        key = "designs/test_image.jpg"
        self.mock_s3.generate_presigned_url.return_value = "http://example.com/presigned_url"
        
        url = self.s3_service.generate_presigned_url(key)
        self.mock_s3.generate_presigned_url.assert_called_once_with(
            'get_object',
            Params={'Bucket': config.AWS['bucket'], 'Key': key},
            ExpiresIn=1800
        )
        self.assertEqual(url, "http://example.com/presigned_url")

if __name__ == "__main__":
    unittest.main()
