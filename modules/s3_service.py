import asyncio
import aiohttp
import aiofiles
import magic
import mimetypes
import os
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from aiobotocore.session import get_session
from aiobotocore.config import AioConfig
from config import config
from logging_config import configure_logger

logger = configure_logger("s3_service")
logger.info("AsyncS3Service initialized.")

class S3Service:
    """Async S3 service for FastAPI compatibility"""
    
    VALID_IMAGE_TYPES = ('image/jpeg', 'image/png', 'image/webp')
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

    def __init__(self):
        """Initialize async S3 session"""
        self.session = get_session()
        self.config = AioConfig(
            region_name=config.AWS['region'],
            connect_timeout=30,
            read_timeout=30
        )
        self.bucket = config.AWS['bucket']
        self.folder = config.AWS['designs_folder'].rstrip('/') + '/'
        self.mime = magic.Magic(mime=True)

    async def upload_from_url(self, url: str, filename: str) -> Tuple[bool, str]:
        """Async upload from URL with enhanced validation"""
        async with aiohttp.ClientSession() as http_client:
            try:
                async with http_client.get(url) as response:
                    if response.status != 200:
                        return False, f"HTTP error {response.status}"
                    
                    async with aiofiles.tempfile.NamedTemporaryFile('wb') as tmp:
                        content = await response.read()
                        await tmp.write(content)
                        await tmp.flush()
                        
                        # Validate file
                        valid, msg = await self._validate_image(tmp.name)
                        if not valid:
                            return False, msg
                        
                        # Generate unique filename
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        s3_key = f"{self.folder}{timestamp}_{filename}"
                        
                        async with self.session.create_client(
                            's3',
                            aws_access_key_id=config.AWS['access_key'],
                            aws_secret_access_key=config.AWS['secret_key'],
                            config=self.config
                        ) as s3:
                            await s3.put_object(
                                Bucket=self.bucket,
                                Key=s3_key,
                                Body=content,
                                ContentType=msg,  # msg contains validated MIME type
                                Metadata={
                                    'source_url': url,
                                    'upload_date': timestamp
                                }
                            )
                            logger.info(f"Uploaded to S3: {s3_key}")
                            return True, s3_key
            except Exception as e:
                logger.error(f"Upload failed: {str(e)}")
                return False, "Upload failed"

    async def _validate_image(self, file_path: str) -> Tuple[bool, str]:
        """Async-compatible validation with thread pooling"""
        try:
            # Run blocking IO in thread pool
            file_size = await asyncio.to_thread(os.path.getsize, file_path)
            if file_size > self.MAX_FILE_SIZE:
                return False, f"File too large (max {self.MAX_FILE_SIZE/1024/1024}MB)"
            
            # MIME detection in thread pool
            file_type = await asyncio.to_thread(self.mime.from_file, file_path)
            if file_type not in self.VALID_IMAGE_TYPES:
                return False, f"Unsupported file type: {file_type}"

            logger.debug(f"Validating image: {file_path}")
            logger.debug(f"File size: {file_size} bytes, MIME type: {file_type}")

            return True, file_type
        except Exception as e:
            return False, f"Validation error: {str(e)}"

    async def generate_presigned_url(self, key: str, expires_in: int = 3600) -> Optional[str]:
        """Generate async presigned URL"""
        try:
            async with self.session.create_client(
                's3',
                aws_access_key_id=config.AWS['access_key'],
                aws_secret_access_key=config.AWS['secret_key'],
                config=self.config
            ) as s3:
                # Verify object exists first
                await s3.head_object(Bucket=self.bucket, Key=key)
                return await s3.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket, 'Key': key},
                    ExpiresIn=expires_in
                )
        except Exception as e:
            logger.error(f"Presigned URL failed: {str(e)}")
            return None

    async def list_images(self, max_results: int = 50) -> List[dict]:
        """Async list with pagination"""
        try:
            images = []
            async with self.session.create_client(
                's3',
                aws_access_key_id=config.AWS['access_key'],
                aws_secret_access_key=config.AWS['secret_key'],
                config=self.config
            ) as s3:
                paginator = s3.get_paginator('list_objects_v2')
                async for page in paginator.paginate(
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
                                'url': await self.generate_presigned_url(obj['Key'])
                            })
            return images
        except Exception as e:
            logger.error(f"List images error: {str(e)}")
            return []

    async def delete_image(self, key: str) -> bool:
        """Async delete operation"""
        try:
            async with self.session.create_client(
                's3',
                aws_access_key_id=config.AWS['access_key'],
                aws_secret_access_key=config.AWS['secret_key'],
                config=self.config
            ) as s3:
                await s3.delete_object(Bucket=self.bucket, Key=key)
                return True
        except Exception as e:
            logger.error(f"Delete failed: {str(e)}")
            return False

    async def get_image_metadata(self, key: str) -> Optional[dict]:
        """Async metadata retrieval"""
        try:
            async with self.session.create_client(
                's3',
                aws_access_key_id=config.AWS['access_key'],
                aws_secret_access_key=config.AWS['secret_key'],
                config=self.config
            ) as s3:
                response = await s3.head_object(Bucket=self.bucket, Key=key)
                return {
                    'content_type': response['ContentType'],
                    'metadata': response.get('Metadata', {}),
                    'size': response['ContentLength'],
                    'last_modified': response['LastModified']
                }
        except Exception as e:
            logger.error(f"Metadata error: {str(e)}")
            return None