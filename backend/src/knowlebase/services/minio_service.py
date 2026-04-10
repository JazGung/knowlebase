"""
Minio对象存储服务

功能：
1. Minio客户端初始化和连接管理
2. 存储桶管理（创建、检查、配置）
3. 文件上传、下载、删除操作
4. 文件元数据管理
5. 预签名URL生成
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, BinaryIO, Dict, Any, List, Tuple
from io import BytesIO

from minio import Minio
from minio.error import S3Error

from knowlebase.core.config import settings

logger = logging.getLogger(__name__)


class MinioService:
    """
    Minio对象存储服务类

    封装Minio客户端操作，提供简化的API
    """

    def __init__(self):
        self._client: Optional[Minio] = None
        self._initialized = False

    def init_client(self) -> Minio:
        """
        初始化Minio客户端

        Returns:
            Minio: 初始化的Minio客户端实例

        Raises:
            ConnectionError: 连接Minio失败时抛出
        """
        if self._client is not None:
            return self._client

        try:
            logger.info(f"初始化Minio客户端: {settings.minio_endpoint_url}")

            self._client = Minio(
                endpoint=settings.minio_endpoint,
                access_key=settings.minio_access_key,
                secret_key=settings.minio_secret_key,
                secure=settings.minio_secure,
                region=settings.minio_region,
            )

            # 测试连接
            if not self._client.bucket_exists(settings.minio_document_bucket):
                logger.info(f"存储桶不存在，创建存储桶: {settings.minio_document_bucket}")
                self._client.make_bucket(settings.minio_document_bucket)

            logger.info("Minio客户端初始化成功")
            self._initialized = True
            return self._client

        except Exception as e:
            logger.error(f"Minio客户端初始化失败: {e}")
            raise ConnectionError(f"连接Minio失败: {str(e)}")

    @property
    def client(self) -> Minio:
        """获取Minio客户端实例"""
        if self._client is None:
            self.init_client()
        return self._client

    def ensure_buckets_exist(self) -> None:
        """确保所有需要的存储桶都存在"""
        buckets = [
            (settings.minio_document_bucket, "文档存储桶"),
            (settings.minio_temp_bucket, "临时文件存储桶"),
        ]

        for bucket_name, description in buckets:
            try:
                if not self.client.bucket_exists(bucket_name):
                    logger.info(f"创建{description}: {bucket_name}")
                    self.client.make_bucket(bucket_name)
                    logger.info(f"{description}创建成功")
                else:
                    logger.debug(f"{description}已存在: {bucket_name}")
            except S3Error as e:
                logger.error(f"创建{description}失败: {e}")
                raise

    def upload_file(
        self,
        bucket_name: str,
        object_name: str,
        file_data: bytes,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        上传文件到Minio

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件名）
            file_data: 文件数据（字节）
            content_type: 内容类型
            metadata: 对象元数据

        Returns:
            str: 对象名称

        Raises:
            ValueError: 参数错误时抛出
            S3Error: Minio操作失败时抛出
        """
        if not bucket_name or not object_name:
            raise ValueError("bucket_name和object_name不能为空")

        if not file_data:
            raise ValueError("file_data不能为空")

        try:
            # 确保存储桶存在
            if not self.client.bucket_exists(bucket_name):
                self.client.make_bucket(bucket_name)

            # 准备元数据
            object_metadata = metadata or {}

            # 上传文件
            data_stream = BytesIO(file_data)
            data_length = len(file_data)

            self.client.put_object(
                bucket_name=bucket_name,
                object_name=object_name,
                data=data_stream,
                length=data_length,
                content_type=content_type,
                metadata=object_metadata,
            )

            logger.info(f"文件上传成功: {bucket_name}/{object_name} ({data_length} bytes)")
            return object_name

        except S3Error as e:
            logger.error(f"文件上传失败: {bucket_name}/{object_name} - {e}")
            raise

    def download_file(self, bucket_name: str, object_name: str) -> bytes:
        """
        从Minio下载文件

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件名）

        Returns:
            bytes: 文件数据

        Raises:
            FileNotFoundError: 文件不存在时抛出
            S3Error: Minio操作失败时抛出
        """
        try:
            response = self.client.get_object(bucket_name, object_name)
            file_data = response.read()
            response.close()
            response.release_conn()

            logger.debug(f"文件下载成功: {bucket_name}/{object_name} ({len(file_data)} bytes)")
            return file_data

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"文件不存在: {bucket_name}/{object_name}")
            logger.error(f"文件下载失败: {bucket_name}/{object_name} - {e}")
            raise

    def delete_file(self, bucket_name: str, object_name: str) -> bool:
        """
        删除Minio中的文件

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件名）

        Returns:
            bool: 删除是否成功

        Raises:
            S3Error: Minio操作失败时抛出
        """
        try:
            self.client.remove_object(bucket_name, object_name)
            logger.info(f"文件删除成功: {bucket_name}/{object_name}")
            return True

        except S3Error as e:
            logger.error(f"文件删除失败: {bucket_name}/{object_name} - {e}")
            raise

    def file_exists(self, bucket_name: str, object_name: str) -> bool:
        """
        检查文件是否存在

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件名）

        Returns:
            bool: 文件是否存在
        """
        try:
            self.client.stat_object(bucket_name, object_name)
            return True
        except S3Error as e:
            if e.code == "NoSuchKey":
                return False
            # 其他错误，记录日志但返回False
            logger.warning(f"检查文件存在状态时出错: {bucket_name}/{object_name} - {e}")
            return False

    def get_file_metadata(self, bucket_name: str, object_name: str) -> Dict[str, Any]:
        """
        获取文件元数据

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件名）

        Returns:
            Dict[str, Any]: 文件元数据

        Raises:
            FileNotFoundError: 文件不存在时抛出
            S3Error: Minio操作失败时抛出
        """
        try:
            stat = self.client.stat_object(bucket_name, object_name)

            metadata = {
                "bucket": bucket_name,
                "object_name": object_name,
                "size": stat.size,
                "content_type": stat.content_type,
                "last_modified": stat.last_modified.isoformat() if stat.last_modified else None,
                "etag": stat.etag,
                "metadata": stat.metadata or {},
            }

            return metadata

        except S3Error as e:
            if e.code == "NoSuchKey":
                raise FileNotFoundError(f"文件不存在: {bucket_name}/{object_name}")
            logger.error(f"获取文件元数据失败: {bucket_name}/{object_name} - {e}")
            raise

    def generate_presigned_url(
        self,
        bucket_name: str,
        object_name: str,
        expires_seconds: int = 3600,
        method: str = "GET"
    ) -> str:
        """
        生成预签名URL

        Args:
            bucket_name: 存储桶名称
            object_name: 对象名称（文件名）
            expires_seconds: URL过期时间（秒）
            method: HTTP方法（GET/PUT）

        Returns:
            str: 预签名URL

        Raises:
            S3Error: Minio操作失败时抛出
        """
        try:
            url = self.client.presigned_url(
                method=method,
                bucket_name=bucket_name,
                object_name=object_name,
                expires=timedelta(seconds=expires_seconds),
            )

            logger.debug(f"生成预签名URL: {method} {bucket_name}/{object_name} (过期: {expires_seconds}秒)")
            return url

        except S3Error as e:
            logger.error(f"生成预签名URL失败: {bucket_name}/{object_name} - {e}")
            raise

    def list_files(
        self,
        bucket_name: str,
        prefix: Optional[str] = None,
        recursive: bool = True
    ) -> List[Dict[str, Any]]:
        """
        列出存储桶中的文件

        Args:
            bucket_name: 存储桶名称
            prefix: 前缀过滤
            recursive: 是否递归列出

        Returns:
            List[Dict[str, Any]]: 文件列表
        """
        try:
            objects = self.client.list_objects(
                bucket_name=bucket_name,
                prefix=prefix,
                recursive=recursive,
            )

            files = []
            for obj in objects:
                files.append({
                    "object_name": obj.object_name,
                    "size": obj.size,
                    "last_modified": obj.last_modified.isoformat() if obj.last_modified else None,
                    "etag": obj.etag,
                    "is_dir": obj.is_dir,
                })

            return files

        except S3Error as e:
            logger.error(f"列出文件失败: {bucket_name} - {e}")
            raise

    def copy_file(
        self,
        source_bucket: str,
        source_object: str,
        dest_bucket: str,
        dest_object: str
    ) -> bool:
        """
        复制文件

        Args:
            source_bucket: 源存储桶
            source_object: 源对象
            dest_bucket: 目标存储桶
            dest_object: 目标对象

        Returns:
            bool: 复制是否成功

        Raises:
            S3Error: Minio操作失败时抛出
        """
        try:
            self.client.copy_object(
                dest_bucket,
                dest_object,
                f"/{source_bucket}/{source_object}"
            )

            logger.info(f"文件复制成功: {source_bucket}/{source_object} -> {dest_bucket}/{dest_object}")
            return True

        except S3Error as e:
            logger.error(f"文件复制失败: {source_bucket}/{source_object} -> {dest_bucket}/{dest_object} - {e}")
            raise


# 全局Minio服务实例
minio_service = MinioService()


def init_minio():
    """初始化Minio连接"""
    logger.info("初始化Minio连接...")
    try:
        minio_service.init_client()
        minio_service.ensure_buckets_exist()
        logger.info("Minio连接初始化完成")
    except Exception as e:
        logger.error(f"Minio连接初始化失败: {e}")
        raise


def get_minio_service() -> MinioService:
    """
    获取Minio服务实例的依赖注入函数

    Usage:
        @router.post("/upload")
        async def upload_file(minio: MinioService = Depends(get_minio_service)):
            # 使用minio服务
            pass
    """
    return minio_service


if __name__ == "__main__":
    # 测试Minio连接
    import sys

    logging.basicConfig(level=logging.DEBUG)

    try:
        init_minio()
        print("Minio连接测试成功")

        # 测试基本操作
        service = get_minio_service()

        # 列出存储桶
        print(f"文档存储桶: {settings.minio_document_bucket}")
        print(f"临时存储桶: {settings.minio_temp_bucket}")

        # 测试上传下载
        test_data = b"Hello, Minio! This is a test file."
        test_object = "test-file.txt"

        # 上传测试文件
        service.upload_file(
            bucket_name=settings.minio_document_bucket,
            object_name=test_object,
            file_data=test_data,
            content_type="text/plain",
            metadata={"test": "true", "uploaded_by": "test_script"}
        )

        # 检查文件是否存在
        if service.file_exists(settings.minio_document_bucket, test_object):
            print(f"测试文件存在: {test_object}")

        # 下载测试文件
        downloaded_data = service.download_file(settings.minio_document_bucket, test_object)
        print(f"下载文件内容: {downloaded_data[:50]}")

        # 生成预签名URL
        url = service.generate_presigned_url(
            bucket_name=settings.minio_document_bucket,
            object_name=test_object,
            expires_seconds=300
        )
        print(f"预签名URL: {url[:100]}...")

        # 删除测试文件
        service.delete_file(settings.minio_document_bucket, test_object)
        print("测试文件已删除")

        print("所有Minio测试通过")

    except Exception as e:
        print(f"Minio测试失败: {e}", file=sys.stderr)
        sys.exit(1)