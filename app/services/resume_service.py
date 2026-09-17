"""Shared resume input handling for all resume-based workflows."""

from typing import Optional

from fastapi import File, Form, HTTPException, UploadFile

from app.resume_parser import extract_resume_text


async def resolve_resume_text(
    file: Optional[UploadFile] = File(default=None),
    resume_text: Optional[str] = Form(default=None),
) -> str:
    """Return text from an upload or pasted text, with one consistent error."""
    if file is not None:
        return await extract_resume_text(file)
    if resume_text and resume_text.strip():
        return resume_text.strip()
    raise HTTPException(status_code=400, detail="Provide either a resume file or resume_text.")