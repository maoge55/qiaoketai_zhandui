from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.dependencies.auth import require_elite_member


router = APIRouter(prefix="/api/uploads", tags=["uploads"])


# 上传目录：app/static/uploads/{images,files}
BASE_DIR = Path(__file__).resolve().parent.parent  # app/
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
IMAGE_DIR = UPLOAD_DIR / "images"
FILE_DIR = UPLOAD_DIR / "files"

IMAGE_DIR.mkdir(parents=True, exist_ok=True)
FILE_DIR.mkdir(parents=True, exist_ok=True)


ALLOWED_IMAGE_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}

ALLOWED_FILE_EXTS = {
    ".pdf",
    ".zip",
    ".rar",
    ".7z",
    ".txt",
    ".md",
    ".doc",
    ".docx",
    ".xls",
    ".xlsx",
    ".ppt",
    ".pptx",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
}


def _safe_ext_from_filename(filename: str | None) -> str:
    if not filename:
        return ""
    name = filename.strip().lower()
    if "." not in name:
        return ""
    return "." + name.split(".")[-1]


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    _: object = Depends(require_elite_member),
):
    """富文本图片上传。

    仅大神成员/管理员可上传（与发布攻略权限一致）。
    """

    if not file.content_type or file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WEBP/GIF 图片")

    ext = ALLOWED_IMAGE_TYPES[file.content_type]
    filename = f"{uuid4().hex}{ext}"
    path = IMAGE_DIR / filename

    data = await file.read()
    max_size = 5 * 1024 * 1024  # 5MB
    if len(data) > max_size:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")

    path.write_bytes(data)
    return {"url": f"/static/uploads/images/{filename}"}


@router.post("/file")
async def upload_file(
    file: UploadFile = File(...),
    _: object = Depends(require_elite_member),
):
    """富文本附件上传（插入为链接）。"""

    ext = _safe_ext_from_filename(file.filename)
    if not ext or ext not in ALLOWED_FILE_EXTS:
        raise HTTPException(
            status_code=400,
            detail="不支持的文件类型（建议：pdf/zip/docx/xlsx/pptx/txt/md 等）",
        )

    filename = f"{uuid4().hex}{ext}"
    path = FILE_DIR / filename

    data = await file.read()
    max_size = 20 * 1024 * 1024  # 20MB
    if len(data) > max_size:
        raise HTTPException(status_code=400, detail="文件不能超过 20MB")

    path.write_bytes(data)
    return {
        "url": f"/static/uploads/files/{filename}",
        "filename": file.filename or filename,
    }
