from modules.s3_service import S3Service
from modules.image_processing_module import ImageProcessor

s3_service = S3Service()
image_processor = ImageProcessor(s3_service)
