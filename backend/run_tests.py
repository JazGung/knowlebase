#!/usr/bin/env python
"""Direct test runner (no pytest)"""
import sys
import os
import hashlib
import asyncio
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

passed = 0
failed = 0

def ok(msg):
    global passed
    passed += 1
    print(f"[OK] {msg}")

def fail(msg):
    global failed
    failed += 1
    print(f"[FAIL] {msg}")

def check(condition, ok_msg, fail_msg=""):
    if condition:
        ok(ok_msg)
    else:
        fail(fail_msg or ok_msg)

# ============ Schemas ============
print("\n--- Schemas ---")
from pydantic import ValidationError
from knowlebase.schemas.document import (
    DocumentStatus, ProcessingStatus, FileCheckItem, FileCheckRequest,
    DocumentUploadRequestMetadata, IntegrityValidationError,
    DocumentListQuery, ReprocessDocumentRequest,
)

check(DocumentStatus.PENDING == "pending", "DocumentStatus.PENDING")
check(DocumentStatus.SUCCESS == "success", "DocumentStatus.SUCCESS")
check(DocumentStatus.FAILED == "failed", "DocumentStatus.FAILED")
check(DocumentStatus.PROCESSING == "processing", "DocumentStatus.PROCESSING")
check(DocumentStatus.DELETED == "deleted", "DocumentStatus.DELETED")

check(ProcessingStatus.PENDING == "pending", "ProcessingStatus.PENDING")
check(ProcessingStatus.SUCCESS == "success", "ProcessingStatus.SUCCESS")

VH = "a" * 32
item = FileCheckItem(filename="test.pdf", hash=VH)
check(item.filename == "test.pdf" and item.hash == VH, "FileCheckItem valid")

item_upper = FileCheckItem(filename="test.pdf", hash=VH.upper())
check(item_upper.hash == VH, "FileCheckItem hash lowercased")

try:
    FileCheckItem(filename="test.pdf", hash="abc123")
    fail("FileCheckItem invalid hash should reject")
except ValidationError:
    ok("FileCheckItem invalid hash rejected")

try:
    FileCheckRequest(files=[])
    fail("FileCheckRequest empty files should reject")
except ValidationError:
    ok("FileCheckRequest empty files rejected")

try:
    FileCheckRequest(files=[
        {"filename": "a.pdf", "hash": VH},
        {"filename": "a.pdf", "hash": "b" * 32},
    ])
    fail("FileCheckRequest duplicate filenames should reject")
except ValidationError:
    ok("FileCheckRequest duplicate filenames rejected")

meta = DocumentUploadRequestMetadata()
check(meta.title is None and meta.tags is None, "DocumentUploadRequestMetadata defaults")

try:
    DocumentUploadRequestMetadata(tags="a" * 51)
    fail("Metadata tag too long should reject")
except ValidationError:
    ok("Metadata tag too long rejected")

try:
    DocumentUploadRequestMetadata(tags=" , , ")
    fail("Metadata empty tags should reject")
except ValidationError:
    ok("Metadata empty tags rejected")

q = DocumentListQuery()
check(q.page == 1 and q.page_size == 20 and q.sort_by == "created_at" and q.order == "desc", "DocumentListQuery defaults")

try:
    DocumentListQuery(page=0)
    fail("Invalid page should reject")
except ValidationError:
    ok("DocumentListQuery invalid page rejected")

try:
    DocumentListQuery(page_size=101)
    fail("Page size too large should reject")
except ValidationError:
    ok("DocumentListQuery page_size too large rejected")

try:
    DocumentListQuery(sort_by="unknown_field")
    fail("Invalid sort field should reject")
except ValidationError:
    ok("DocumentListQuery invalid sort field rejected")

err = IntegrityValidationError(field="hash", error="test", expected="a", actual="b")
check(err.field == "hash", "IntegrityValidationError creation")

req = ReprocessDocumentRequest(document_id="doc_123")
check(req.force_reprocess is False, "ReprocessDocumentRequest default force=False")

# ============ API Routes ============
print("\n--- API Routes ---")
from knowlebase.admin.document.api import router
route_paths = {route.path: list(route.methods) for route in router.routes}
expected = {"/check", "/upload", "/list", "/detail", "/enable", "/disable", "/reprocess"}
check(expected == set(route_paths.keys()), f"All 7 routes registered (got {set(route_paths.keys())})")
check("POST" in route_paths["/check"], "POST /check")
check("POST" in route_paths["/upload"], "POST /upload")
check("GET" in route_paths["/list"], "GET /list")
check("GET" in route_paths["/detail"], "GET /detail")
check("PUT" in route_paths["/enable"], "PUT /enable")
check("PUT" in route_paths["/disable"], "PUT /disable")
check("POST" in route_paths["/reprocess"], "POST /reprocess")

# ============ UploadService ============
print("\n--- UploadService ---")
from knowlebase.admin.document.service import UploadService
from fastapi import HTTPException

def md5(data):
    return hashlib.md5(data).hexdigest()

async def run_upload_tests():
    service = UploadService(minio_service=MagicMock())

    # Integrity - matching
    content = b"hello world"
    h = md5(content)
    ok_flag, calc, err = await service.verify_file_integrity(content, h)
    check(ok_flag is True, "verify_file_integrity matching")

    # Integrity - mismatching
    ok_flag, calc, err = await service.verify_file_integrity(content, "0" * 32)
    check(ok_flag is False and err is not None, "verify_file_integrity mismatching")

    # Integrity - case insensitive
    ok_flag, _, _ = await service.verify_file_integrity(content, h.upper())
    check(ok_flag is True, "verify_file_integrity case insensitive")

    # Valid formats
    await service.validate_file_format_and_size("doc.pdf", 1024)
    await service.validate_file_format_and_size("report.docx", 2048)
    await service.validate_file_format_and_size("report.doc", 2048)
    ok("validate_file_format_and_size valid formats")

    # Invalid extension
    try:
        await service.validate_file_format_and_size("image.png", 1024)
        fail("Invalid extension should reject")
    except HTTPException as e:
        check(e.status_code == 400, "Invalid extension rejected")

    # File too large
    try:
        await service.validate_file_format_and_size("big.pdf", 104857601)
        fail("File too large should reject")
    except HTTPException as e:
        check(e.status_code == 400, "File too large rejected")

    # Filename too long
    try:
        await service.validate_file_format_and_size("a" * 256 + ".pdf", 1024)
        fail("Filename too long should reject")
    except HTTPException as e:
        check(e.status_code == 400, "Filename too long rejected")

    # Cleanup orphaned - exists
    service.minio_service.file_exists = MagicMock(return_value=True)
    service.minio_service.delete_file = MagicMock(return_value=True)
    result = await service.cleanup_orphaned_file("abc123hash")
    check(result is True, "cleanup_orphaned_file existing")

    # Cleanup orphaned - not exists
    service.minio_service.file_exists = MagicMock(return_value=False)
    result = await service.cleanup_orphaned_file("abc123hash")
    check(result is False, "cleanup_orphaned_file non-existent")

    # Batch check - no duplicates
    mock_db = AsyncMock()
    mock_result = AsyncMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=None)
    mock_db.execute = AsyncMock(return_value=mock_result)
    result = await service.batch_check_duplicates(mock_db, [
        {"filename": "a.pdf", "hash": "a" * 32},
        {"filename": "b.pdf", "hash": "b" * 32},
    ])
    check(result == [], "batch_check_duplicates no duplicates")

    # Batch check - invalid hash
    result = await service.batch_check_duplicates(mock_db, [
        {"filename": "bad.pdf", "hash": "tooshort"},
    ])
    check(result == [], "batch_check_duplicates invalid hash skipped")

    # Batch check - some duplicates
    existing_doc = MagicMock()
    existing_doc.id = 12345
    existing_doc.original_filename = "already_there.pdf"
    call_count = 0
    async def mock_execute(stmt):
        nonlocal call_count
        call_count += 1
        result = AsyncMock()
        if call_count == 1:
            result.scalar_one_or_none = MagicMock(return_value=existing_doc)
        else:
            result.scalar_one_or_none = MagicMock(return_value=None)
        return result
    mock_db2 = AsyncMock()
    mock_db2.execute = mock_execute
    result = await service.batch_check_duplicates(mock_db2, [
        {"filename": "dup.pdf", "hash": "a" * 32},
        {"filename": "new.pdf", "hash": "b" * 32},
    ])
    check(len(result) == 1 and result[0]["filename"] == "dup.pdf", "batch_check_duplicates detects duplicate")

    # Successful upload
    content = b"test pdf content"
    file_hash = md5(content)
    mock_file = MagicMock()
    mock_file.filename = "test.pdf"
    mock_file.content_type = "application/octet-stream"
    mock_file.read = AsyncMock(return_value=content)
    mock_db3 = AsyncMock()
    mock_db3.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_db3.commit = AsyncMock()
    mock_db3.refresh = AsyncMock()
    result = await service.process_upload(mock_db3, mock_file, file_hash)
    check(result["status"] == "success" and result["file_hash"] == file_hash, "process_upload successful")

    # Duplicate file
    content2 = b"test pdf content 2"
    file_hash2 = md5(content2)
    mock_file2 = MagicMock()
    mock_file2.filename = "test2.pdf"
    mock_file2.content_type = "application/octet-stream"
    mock_file2.read = AsyncMock(return_value=content2)
    mock_db4 = AsyncMock()
    existing_doc2 = MagicMock()
    existing_doc2.id = 12345
    existing_doc2.file_hash = file_hash2
    existing_doc2.original_filename = "existing.pdf"
    mock_db4.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=existing_doc2)))
    result = await service.process_upload(mock_db4, mock_file2, file_hash2)
    check(result["status"] == "duplicate" and result["document_id"] == "12345", "process_upload duplicate detected")

    # Integrity check failure
    mock_file3 = MagicMock()
    mock_file3.filename = "test3.pdf"
    mock_file3.content_type = "application/octet-stream"
    mock_file3.read = AsyncMock(return_value=b"content")
    mock_db5 = AsyncMock()
    try:
        await service.process_upload(mock_db5, mock_file3, "0" * 32)
        fail("Integrity failure should raise")
    except HTTPException as e:
        check(e.status_code == 400, "Integrity check failure raises 400")

    # Invalid format
    mock_file4 = MagicMock()
    mock_file4.filename = "test.png"
    mock_file4.content_type = "image/png"
    mock_file4.read = AsyncMock(return_value=b"png content")
    mock_db6 = AsyncMock()
    try:
        await service.process_upload(mock_db6, mock_file4, md5(b"png content"))
        fail("Invalid format should raise")
    except HTTPException as e:
        check(e.status_code == 400, "Invalid format rejected")

    # File too large
    big_content = b"x" * 104857601
    mock_file5 = MagicMock()
    mock_file5.filename = "big.pdf"
    mock_file5.content_type = "application/octet-stream"
    mock_file5.read = AsyncMock(return_value=big_content)
    mock_db7 = AsyncMock()
    try:
        await service.process_upload(mock_db7, mock_file5, md5(big_content))
        fail("File too large should raise")
    except HTTPException as e:
        check(e.status_code == 400, "File too large rejected in upload")

    # DB commit failure cleanup
    content7 = b"test pdf content 7"
    file_hash7 = md5(content7)
    mock_file7 = MagicMock()
    mock_file7.filename = "test7.pdf"
    mock_file7.content_type = "application/octet-stream"
    mock_file7.read = AsyncMock(return_value=content7)
    service.minio_service.file_exists = MagicMock(return_value=True)
    service.minio_service.delete_file = MagicMock(return_value=True)
    mock_db8 = AsyncMock()
    mock_db8.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    mock_db8.commit = AsyncMock(side_effect=Exception("DB error"))
    try:
        await service.process_upload(mock_db8, mock_file7, file_hash7)
        fail("DB error should raise")
    except HTTPException as e:
        check(e.status_code == 500, "DB commit failure raises 500")
        check(service.minio_service.delete_file.call_count >= 1, "Orphaned file cleanup attempted")

asyncio.run(run_upload_tests())

# ============ DocumentService ============
print("\n--- DocumentService ---")
from knowlebase.admin.document.service import DocumentService

async def run_document_service_tests():
    service = DocumentService()

    # Empty list
    mock_db = AsyncMock()
    mock_total = AsyncMock()
    mock_total.scalar_one = MagicMock(return_value=0)
    mock_list = AsyncMock()
    mock_list.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
    cc = 0
    async def mock_exec(stmt):
        nonlocal cc; cc += 1
        return mock_total if cc == 1 else mock_list
    mock_db.execute = mock_exec
    result = await service.get_document_list(mock_db, DocumentListQuery())
    check(result["documents"] == [] and result["pagination"]["total"] == 0, "get_document_list empty")

    # Nonexistent document
    mock_db2 = AsyncMock()
    mock_db2.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    result = await service.get_document_detail(mock_db2, "nonexistent")
    check(result is None, "get_document_detail nonexistent")

    # Enable document
    mock_db3 = AsyncMock()
    doc3 = MagicMock()
    doc3.enabled = False
    mock_db3.get = AsyncMock(return_value=doc3)
    await service.enable_document(mock_db3, "1")
    check(doc3.enabled is True, "enable_document")

    # Disable document
    mock_db4 = AsyncMock()
    doc4 = MagicMock()
    doc4.enabled = True
    mock_db4.get = AsyncMock(return_value=doc4)
    await service.disable_document(mock_db4, "1")
    check(doc4.enabled is False, "disable_document")

    # Enable non-existent
    mock_db5 = AsyncMock()
    mock_db5.get = AsyncMock(return_value=None)
    try:
        await service.enable_document(mock_db5, "999")
        fail("Enable non-existent should raise")
    except HTTPException as e:
        check(e.status_code == 404, "Enable non-existent raises 404")

    # Disable non-existent
    mock_db6 = AsyncMock()
    mock_db6.get = AsyncMock(return_value=None)
    try:
        await service.disable_document(mock_db6, "999")
        fail("Disable non-existent should raise")
    except HTTPException as e:
        check(e.status_code == 404, "Disable non-existent raises 404")

    # Reprocess
    mock_db7 = AsyncMock()
    doc7 = MagicMock()
    doc7.id = "1"
    doc7.status = "success"
    mock_db7.get = AsyncMock(return_value=doc7)
    max_result = AsyncMock()
    max_result.scalar_one = MagicMock(return_value=0)
    mock_db7.execute = AsyncMock(return_value=max_result)
    mock_db7.commit = AsyncMock()
    mock_db7.refresh = AsyncMock()
    result = await service.reprocess_document(mock_db7, "1")
    check(result["document_id"] == "1" and result["processing_number"] == 1, "reprocess_document")

    # Enable already enabled (backend validation)
    mock_db8 = AsyncMock()
    doc8 = MagicMock()
    doc8.enabled = True
    mock_db8.get = AsyncMock(return_value=doc8)
    try:
        await service.enable_document(mock_db8, "1")
        fail("Enable already enabled should raise")
    except HTTPException as e:
        check(e.status_code == 400, "Enable already enabled raises 400")

    # Disable already disabled (backend validation)
    mock_db9 = AsyncMock()
    doc9 = MagicMock()
    doc9.enabled = False
    mock_db9.get = AsyncMock(return_value=doc9)
    try:
        await service.disable_document(mock_db9, "1")
        fail("Disable already disabled should raise")
    except HTTPException as e:
        check(e.status_code == 400, "Disable already disabled raises 400")

    # Reprocess processing (backend validation)
    mock_db10 = AsyncMock()
    doc10 = MagicMock()
    doc10.status = "processing"
    mock_db10.get = AsyncMock(return_value=doc10)
    try:
        await service.reprocess_document(mock_db10, "1")
        fail("Reprocess processing should raise")
    except HTTPException as e:
        check(e.status_code == 400, "Reprocess processing raises 400")

    # Reprocess deleted (backend validation)
    mock_db11 = AsyncMock()
    doc11 = MagicMock()
    doc11.status = "deleted"
    mock_db11.get = AsyncMock(return_value=doc11)
    try:
        await service.reprocess_document(mock_db11, "1")
        fail("Reprocess deleted should raise")
    except HTTPException as e:
        check(e.status_code == 400, "Reprocess deleted raises 400")

    # Reprocess non-existent
    mock_db12 = AsyncMock()
    mock_db12.get = AsyncMock(return_value=None)
    try:
        await service.reprocess_document(mock_db12, "999")
        fail("Reprocess non-existent should raise")
    except HTTPException as e:
        check(e.status_code == 404, "Reprocess non-existent raises 404")

asyncio.run(run_document_service_tests())

print("\n" + "=" * 60)
print(f"Results: {passed} passed, {failed} failed")
if failed == 0:
    print("ALL TESTS PASSED")
else:
    print(f"SOME TESTS FAILED")
    sys.exit(1)
