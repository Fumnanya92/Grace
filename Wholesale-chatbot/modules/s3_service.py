import boto3
import tempfile
import urllib.request
import magic
import logging
import mimetypes
from botocore.exceptions import ClientError
from config import config
from typing import List, Optional, Tuple
import os
from datetime import datetime, timedelta
from logging_config import configure_logger

logger = configure_logger("s3_service")

logger.info("S3Service initialized.")

class S3Service:
    """Enhanced S3 service for handling image uploads and management"""
    
    VALID_IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/webp')
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self):
        """Initialize S3 client with configuration"""
        self.s3 = boto3.client(
            's3',
            aws_access_key_id=config.AWS['access_key'],
            aws_secret_access_key=config.AWS['secret_key'],
            region_name=config.AWS['region']
        )
        self.bucket = config.AWS['bucket']
        self.folder = config.AWS['designs_folder'].rstrip('/') + '/'
        self.mime = magic.Magic(mime=True)
        
    def upload_from_url(self, url: str, filename: str) -> Tuple[bool, str]:
        """
        Download and upload image from URL to S3 with validation
        Returns (success, message_or_key)
        """
        try:
            with tempfile.NamedTemporaryFile() as tmp:
                # Download with timeout
                try:
                    urllib.request.urlretrieve(url, tmp.name)
                except Exception as e:
                    return False, f"Download failed: {str(e)}"

                # Validate file
                validation_result = self._validate_image(tmp.name)
                if not validation_result[0]:
                    return validation_result

                # Generate unique filename
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                s3_key = f"{self.folder}{timestamp}_{filename}"

                # Upload with metadata
                self.s3.upload_file(
                    tmp.name,
                    self.bucket,
                    s3_key,
                    ExtraArgs={
                        'ContentType': validation_result[1],
                        'Metadata': {
                            'source_url': url,
                            'upload_date': timestamp
                        }
                    }
                )
                logger.info(f"File uploaded successfully to S3. Key: {s3_key}")
                return True, s3_key

        except ClientError as e:
            logger.error(f"S3 upload error for file {filename} from URL {url}: {e}")
            return False, "Failed to upload to storage"
        except Exception as e:
            logger.error(f"Unexpected error during upload for file {filename} from URL {url}: {e}")
            return False, "An unexpected error occurred"

    def _validate_image(self, file_path: str) -> Tuple[bool, str]:
        """Validate image file type and size"""
        try:
            # Check file size
            file_size = os.path.getsize(file_path)
            if file_size > self.MAX_FILE_SIZE:
                return False, f"File too large (max {self.MAX_FILE_SIZE/1024/1024}MB)"

            # Check MIME type
            file_type = self.mime.from_file(file_path)
            if file_type not in self.VALID_IMAGE_TYPES:
                return False, f"Unsupported file type: {file_type}"

            logger.debug(f"Validating image: {file_path}")
            logger.debug(f"File size: {file_size} bytes, MIME type: {file_type}")

            return True, file_type
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    def generate_presigned_url(self, key: str, expires_in: int = 3600) -> Optional[str]:
        """Generate presigned URL with additional validation"""
        try:
            # Verify object exists first
            self.s3.head_object(Bucket=self.bucket, Key=key)
            
            url = self.s3.generate_presigned_url(
                'get_object',
                Params={'Bucket': self.bucket, 'Key': key},
                ExpiresIn=expires_in
            )
            logger.info(f"Presigned URL generated successfully for key: {key}")
            return url
        except ClientError as e:
            logger.error(f"Presigned URL generation failed for key {key}: {e}")
            return None

    def list_images(self, max_results: int = 50) -> List[dict]:
        """List images with pagination and metadata"""
        try:
            images = []
            paginator = self.s3.get_paginator('list_objects_v2')
            
            for page in paginator.paginate(
                Bucket=self.bucket,
                Prefix=self.folder,
                PaginationConfig={'MaxItems': max_results}
            ):
                for obj in page.get('Contents', []):
                    if obj['Key'].lower().endswith(('.png', '.jpg', '.jpeg', '.webp')):
                        images.append({
                            'key': obj['Key'],
                            'name': obj['Key'].replace(self.folder, ''),
                            'size': obj['Size'],
                            'last_modified': obj['LastModified'],
                            'url': self.generate_presigned_url(obj['Key'])
                        })
            return images
        except ClientError as e:
            logger.error(f"List images error: {e}")
            return []

    def delete_image(self, key: str) -> bool:
        """Delete an image from S3"""
        try:
            self.s3.delete_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as e:
            logger.error(f"Delete error for {key}: {e}")
            return False

    def get_image_metadata(self, key: str) -> Optional[dict]:
        """Get metadata for a specific image"""
        try:
            response = self.s3.head_object(Bucket=self.bucket, Key=key)
            return {
                'content_type': response['ContentType'],
                'metadata': response.get('Metadata', {}),
                'size': response['ContentLength'],
                'last_modified': response['LastModified']
            }
        except ClientError as e:
            logger.error(f"Metadata error for {key}: {e}")
            return None