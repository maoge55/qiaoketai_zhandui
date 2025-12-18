from __future__ import annotations

import io
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from PIL import Image, ImageDraw, ImageFont

from app.dependencies.auth import require_elite_member
from app.models import User


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


def _add_watermark(image_data: bytes, username: str) -> bytes:
    """给图片添加水印，返回处理后的图片字节数据。

    水印格式：qiaoketai.com@用户名
    位置：右下角，半透明白色文字带黑色描边
    """
    try:
        img = Image.open(io.BytesIO(image_data))

        # 如果是GIF动图，不处理水印（避免破坏动画）
        if img.format == "GIF" and getattr(img, "is_animated", False):
            return image_data

        # 转换为RGBA以支持透明度
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # 创建水印层
        watermark_layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(watermark_layer)

        # 水印文字
        watermark_text = f"qiaoketai.com@{username}"

        # 动态计算字体大小（图片宽度的3%左右，最小12px，最大48px）
        font_size = max(12, min(48, int(img.width * 0.03)))

        # 尝试加载系统字体，失败则使用默认字体
        try:
            font = ImageFont.truetype("msyh.ttc", font_size)  # 微软雅黑
        except OSError:
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except OSError:
                font = ImageFont.load_default()

        # 获取文字边界框
        bbox = draw.textbbox((0, 0), watermark_text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 计算位置（右下角，留出边距）
        margin = int(img.width * 0.02)
        x = img.width - text_width - margin
        y = img.height - text_height - margin

        # 绘制描边（黑色）
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx != 0 or dy != 0:
                    draw.text((x + dx, y + dy), watermark_text, font=font, fill=(0, 0, 0, 180))

        # 绘制主文字（白色半透明）
        draw.text((x, y), watermark_text, font=font, fill=(255, 255, 255, 200))

        # 合并水印层
        img = Image.alpha_composite(img, watermark_layer)

        # 转回RGB（如果原图不支持透明）
        if img.mode == "RGBA":
            # 创建白色背景
            background = Image.new("RGB", img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[3])
            img = background

        # 保存到字节流
        output = io.BytesIO()
        img.save(output, format="PNG", quality=95)
        return output.getvalue()

    except Exception:
        # 如果处理失败，返回原图
        return image_data


@router.post("/image")
async def upload_image(
    file: UploadFile = File(...),
    user: User = Depends(require_elite_member),
):
    """富文本图片上传。

    仅大神成员/管理员可上传（与发布攻略权限一致）。
    图片会自动添加水印：qiaoketai.com@用户名
    """

    if not file.content_type or file.content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="仅支持 JPG/PNG/WEBP/GIF 图片")

    data = await file.read()
    max_size = 5 * 1024 * 1024  # 5MB
    if len(data) > max_size:
        raise HTTPException(status_code=400, detail="图片不能超过 5MB")

    # 添加水印
    username = user.nickname or user.email.split("@")[0]
    watermarked_data = _add_watermark(data, username)

    # 水印处理后统一保存为PNG格式
    filename = f"{uuid4().hex}.png"
    path = IMAGE_DIR / filename

    path.write_bytes(watermarked_data)
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
