"""
单元测试 - UploadService 业务逻辑（不依赖真实数据库和 Minio）
"""

import hashlib
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import HTTPException

from knowlebase.admin.document.service import UploadService


def make_mock_upload_file(filename: str, content: bytes, content_type: str = "application/octet-stream"):
    """创建一个 mock 的 UploadFile 对象"""
    mock_file = MagicMock()
    mock_file.filename = filename
    mock_file.content_type = content_type
    mock_file.read = AsyncMock(return_value=content)
    return mock_file


def compute_md5(data: bytes) -> str:
    return hashlib.md5(data).hexdigest()


class TestVerifyFileIntegrity:
    """测试文件完整性验证"""

    @pytest.fixture
    def service(self):
        return UploadService(minio_service=MagicMock())

    @pytest.mark.asyncio
    async def test_matching_hash(self, service):
        content = b"hello world"
        correct_hash = compute_md5(content)
        ok, calc_hash, err = await service.verify_file_integrity(content, correct_hash)
        assert ok is True
        assert calc_hash == correct_hash
        assert err is None

    @pytest.mark.asyncio
    async def test_mismatching_hash(self, service):
        content = b"hello world"
        wrong_hash = "0" * 32
        ok, calc_hash, err = await service.verify_file_integrity(content, wrong_hash)
        assert ok is False
        assert err is not None
        assert err.field == "hash"
        assert err.actual == calc_hash

    @pytest.mark.asyncio
    async def test_case_insensitive_hash(self, service):
        content = b"hello world"
        correct_hash = compute_md5(content)
        ok, _, err = await service.verify_file_integrity(content, correct_hash.upper())
        assert ok is True


class TestValidateFileFormatAndSize:
    """测试文件格式和大小验证"""

    @pytest.fixture
    def service(self):
        return UploadService(minio_service=MagicMock())

    @pytest.mark.asyncio
    async def test_valid_pdf(self, service):
        await service.validate_file_format_and_size("doc.pdf", 1024)

    @pytest.mark.asyncio
    async def test_valid_docx(self, service):
        await service.validate_file_format_and_size("report.docx", 2048)

    @pytest.mark.asyncio
    async def test_valid_doc(self, service):
        await service.validate_file_format_and_size("report.doc", 2048)

    @pytest.mark.asyncio
    async def test_invalid_extension(self, service):
        with pytest.raises(Exception) as exc_info:
            await service.validate_file_format_and_size("image.png", 1024)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_file_too_large(self, service):
        with pytest.raises(Exception) as exc_info:
            # max_file_size = 104857600 (100MB)
            await service.validate_file_format_and_size("big.pdf", 104857601)
        assert exc_info.value.status_code == 400

    @pytest.mark.asyncio
    async def test_filename_too_long(self, service):
        long_name = "a" * 256 + ".pdf"
        with pytest.raises(Exception) as exc_info:
            await service.validate_file_format_and_size(long_name, 1024)
        assert exc_info.value.status_code == 400


class TestCleanupOrphanedFile:
    """测试孤立文件清理"""

    @pytest.fixture
    def service(self):
        mock_minio = MagicMock()
        return UploadService(minio_service=mock_minio)

    @pytest.mark.asyncio
    async def test_cleanup_existing_file(self, service):
        service.minio_service.file_exists = MagicMock(return_value=True)
        service.minio_service.delete_file = MagicMock(return_value=True)
        result = await service.cleanup_orphaned_file("abc123hash")
        assert result is True
        service.minio_service.delete_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_nonexistent_file(self, service):
        service.minio_service.file_exists = MagicMock(return_value=False)
        result = await service.cleanup_orphaned_file("abc123hash")
        assert result is False
        service.minio_service.delete_file.assert_not_called()


class TestBatchCheckDuplicates:
    """测试批量重复检查"""

    @pytest.fixture
    def service(self):
        return UploadService(minio_service=MagicMock())

    @pytest.mark.asyncio
    async def test_no_duplicates(self, service):
        mock_db = AsyncMock()
        mock_result = AsyncMock()
        mock_result.scalar_one_or_none = MagicMock(return_value=None)
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await service.batch_check_duplicates(mock_db, [
            {"filename": "a.pdf", "hash": "a" * 32},
            {"filename": "b.pdf", "hash": "b" * 32},
        ])
        assert result == []

    @pytest.mark.asyncio
    async def test_some_duplicates(self, service):
        mock_db = AsyncMock()
        existing_doc = MagicMock()
        existing_doc.id = "doc-existing-001"
        existing_doc.original_filename = "already_there.pdf"

        call_count = 0
        async def mock_execute(stmt):
            nonlocal call_count
            call_count += 1
            result = AsyncMock()
            # First call returns existing doc, second call returns None
            if call_count == 1:
                result.scalar_one_or_none = MagicMock(return_value=existing_doc)
            else:
                result.scalar_one_or_none = MagicMock(return_value=None)
            return result

        mock_db.execute = mock_execute

        result = await service.batch_check_duplicates(mock_db, [
            {"filename": "dup.pdf", "hash": "a" * 32},
            {"filename": "new.pdf", "hash": "b" * 32},
        ])
        assert len(result) == 1
        assert result[0]["filename"] == "dup.pdf"

    @pytest.mark.asyncio
    async def test_invalid_hash_skipped(self, service):
        mock_db = AsyncMock()
        result = await service.batch_check_duplicates(mock_db, [
            {"filename": "bad.pdf", "hash": "tooshort"},
        ])
        assert result == []

    @pytest.mark.asyncio
    async def test_missing_fields_skipped(self, service):
        mock_db = AsyncMock()
        result = await service.batch_check_duplicates(mock_db, [
            {"filename": "nohash.pdf"},
            {"hash": "a" * 32},
        ])
        assert result == []


class TestProcessUpload:
    """测试文件上传完整流程"""

    @pytest.fixture
    def service(self):
        mock_minio = MagicMock()
        mock_minio.upload_file = MagicMock(return_value=True)
        return UploadService(minio_service=mock_minio)

    @pytest.mark.asyncio
    async def test_successful_upload(self, service):
        content = b"test pdf content"
        file_hash = compute_md5(content)
        mock_file = make_mock_upload_file("test.pdf", content)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.commit = AsyncMock()
        mock_db.refresh = AsyncMock()

        result = await service.process_upload(mock_db, mock_file, file_hash)
        assert result["status"] == "success"
        assert result["file_hash"] == file_hash
        assert "document_id" in result
        assert "processing_id" in result
        service.minio_service.upload_file.assert_called_once()

    @pytest.mark.asyncio
    async def test_duplicate_file(self, service):
        content = b"test pdf content"
        file_hash = compute_md5(content)
        mock_file = make_mock_upload_file("test.pdf", content)

        mock_db = AsyncMock()
        existing_doc = MagicMock()
        existing_doc.id = "doc_existing_001"
        existing_doc.file_hash = file_hash
        existing_doc.original_filename = "existing.pdf"
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_doc)))

        result = await service.process_upload(mock_db, mock_file, file_hash)
        assert result["status"] == "duplicate"
        assert result["document_id"] == "doc_existing_001"
        service.minio_service.upload_file.assert_not_called()

    @pytest.mark.asyncio
    async def test_integrity_check_failure(self, service):
        content = b"test pdf content"
        mock_file = make_mock_upload_file("test.pdf", content)
        wrong_hash = "0" * 32

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await service.process_upload(mock_db, mock_file, wrong_hash)
        assert exc_info.value.status_code == 400
        assert "上传文件不完整" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_invalid_format(self, service):
        content = b"test image content"
        file_hash = compute_md5(content)
        mock_file = make_mock_upload_file("test.png", content)

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await service.process_upload(mock_db, mock_file, file_hash)
        assert exc_info.value.status_code == 400
        assert "格式" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_file_too_large(self, service):
        content = b"x" * (104857601)
        file_hash = compute_md5(content)
        mock_file = make_mock_upload_file("big.pdf", content)

        mock_db = AsyncMock()

        with pytest.raises(HTTPException) as exc_info:
            await service.process_upload(mock_db, mock_file, file_hash)
        assert exc_info.value.status_code == 400
        assert "大小" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_db_commit_failure_cleanup(self, service):
        content = b"test pdf content"
        file_hash = compute_md5(content)
        mock_file = make_mock_upload_file("test.pdf", content)

        service.minio_service.file_exists = MagicMock(return_value=True)
        service.minio_service.delete_file = MagicMock(return_value=True)

        mock_db = AsyncMock()
        mock_db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
        mock_db.commit = AsyncMock(side_effect=Exception("DB error"))

        with pytest.raises(HTTPException) as exc_info:
            await service.process_upload(mock_db, mock_file, file_hash)
        assert exc_info.value.status_code == 500
        # Verify orphaned file cleanup was attempted
        service.minio_service.delete_file.assert_called_once()
