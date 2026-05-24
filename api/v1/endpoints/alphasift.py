# -*- coding: utf-8 -*-
"""Optional AlphaSift stock screening endpoint."""

from __future__ import annotations

import importlib
import subprocess
import sys
from dataclasses import asdict, is_dataclass
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_config_dep
from src.config import Config

router = APIRouter()


class AlphaSiftScreenRequest(BaseModel):
    market: str = Field("cn", min_length=1, max_length=16)
    strategy: str = Field("dual_low", min_length=1, max_length=64)
    max_results: int = Field(20, ge=1, le=100)


@router.get("/status")
def alphasift_status(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    return {
        "enabled": bool(config.alphasift_enabled),
        "available": _is_alphasift_available(),
        "install_spec": config.alphasift_install_spec,
    }


@router.post("/install")
def alphasift_install(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    return _install_alphasift(config)


def _install_alphasift(config: Config) -> Dict[str, Any]:
    if _is_alphasift_available():
        return {"installed": True, "already_installed": True, "install_spec": config.alphasift_install_spec}

    install_spec = (config.alphasift_install_spec or "").strip()
    if not install_spec or install_spec.lower() == "alphasift":
        raise HTTPException(
            status_code=424,
            detail={
                "error": "alphasift_install_spec_missing",
                "message": (
                    "请先将 ALPHASIFT_INSTALL_SPEC 配置为真实可安装来源，例如 "
                    "git+https://github.com/ZhuLinsen/alphasift.git、本地路径或 wheel 文件。"
                ),
            },
        )

    try:
        completed = subprocess.run(
            [sys.executable, "-m", "pip", "install", install_spec],
            check=False,
            capture_output=True,
            text=True,
            timeout=300,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail={"error": "alphasift_install_failed", "message": f"自动安装 AlphaSift 失败：{exc}"},
        ) from exc

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        stdout = (completed.stdout or "").strip()
        detail = stderr or stdout or f"pip exited with code {completed.returncode}"
        raise HTTPException(
            status_code=424,
            detail={"error": "alphasift_install_failed", "message": f"自动安装 AlphaSift 失败：{detail}"},
        )

    importlib.invalidate_caches()
    if not _is_alphasift_available():
        raise HTTPException(
            status_code=424,
            detail={"error": "alphasift_unavailable", "message": "AlphaSift 安装完成，但当前进程仍无法导入 alphasift。请重启后端后重试。"},
        )

    return {"installed": True, "already_installed": False, "install_spec": install_spec}


@router.post("/screen")
def alphasift_screen(
    request: AlphaSiftScreenRequest,
    config: Config = Depends(get_config_dep),
) -> Dict[str, Any]:
    if not config.alphasift_enabled:
        raise HTTPException(
            status_code=403,
            detail={"error": "alphasift_disabled", "message": "ALPHASIFT_ENABLED is false."},
        )

    try:
        alphasift = _import_alphasift()
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if detail.get("error") != "alphasift_unavailable":
            raise
        _install_alphasift(config)
        alphasift = _import_alphasift()
    screen = getattr(alphasift, "screen", None)
    if not callable(screen):
        raise HTTPException(
            status_code=424,
            detail={"error": "alphasift_unavailable", "message": "已导入 alphasift，但 alphasift.screen 不可调用。"},
        )

    raw = screen(
        request.strategy,
        market=request.market,
        max_output=request.max_results,
        use_llm=False,
    )
    candidates = _normalize_candidates(raw)
    return {
        "enabled": True,
        "candidates": candidates[: request.max_results],
        "candidate_count": len(candidates[: request.max_results]),
    }


def _is_alphasift_available() -> bool:
    try:
        _import_alphasift()
        return True
    except HTTPException:
        return False


def _import_alphasift() -> Any:
    try:
        return importlib.import_module("alphasift")
    except Exception as exc:
        raise HTTPException(
            status_code=424,
            detail={
                "error": "alphasift_unavailable",
                "message": f"AlphaSift 未安装或未挂载到当前 Python 环境，无法导入 alphasift：{exc}",
            },
        ) from exc


def _normalize_candidates(raw: Any) -> List[Dict[str, Any]]:
    data = _to_plain(raw)
    items = data
    if isinstance(data, dict):
        for key in ("candidates", "items", "results", "stocks"):
            if isinstance(data.get(key), list):
                items = data[key]
                break
    if not isinstance(items, list):
        return []
    return [_normalize_candidate(item, index + 1) for index, item in enumerate(items)]


def _normalize_candidate(raw: Any, rank: int) -> Dict[str, Any]:
    item = _to_plain(raw)
    if not isinstance(item, dict):
        item = {"code": str(item)}
    return {
        "rank": item.get("rank") or rank,
        "code": item.get("code") or item.get("symbol") or item.get("stock_code") or "",
        "name": item.get("name") or item.get("stock_name") or "",
        "score": item.get("score"),
        "reason": item.get("reason") or item.get("ranking_reason") or item.get("summary") or "",
        "raw": item,
    }


def _to_plain(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict") and callable(value.dict):
        return value.dict()
    if isinstance(value, list):
        return [_to_plain(item) for item in value]
    return value
