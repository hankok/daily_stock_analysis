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
from src.config import Config, DEFAULT_ALPHASIFT_INSTALL_SPEC

router = APIRouter()

ALLOWED_ALPHASIFT_INSTALL_SPECS = frozenset({DEFAULT_ALPHASIFT_INSTALL_SPEC})


class AlphaSiftScreenRequest(BaseModel):
    market: str = Field("cn", min_length=1, max_length=16)
    strategy: str = Field("dual_low", min_length=1, max_length=64)
    max_results: int = Field(20, ge=1, le=100)


@router.get("/status")
def alphasift_status(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    return {
        "enabled": bool(config.alphasift_enabled),
        "available": _is_alphasift_available(),
        "install_spec_is_default": _is_default_alphasift_install_spec(config.alphasift_install_spec),
    }


@router.post("/install")
def alphasift_install(config: Config = Depends(get_config_dep)) -> Dict[str, Any]:
    _ensure_alphasift_enabled(config)
    return _install_alphasift(config)


def _install_alphasift(config: Config) -> Dict[str, Any]:
    install_spec_is_default = _is_default_alphasift_install_spec(config.alphasift_install_spec)
    if _is_alphasift_available():
        return _build_install_response(
            already_installed=True,
            install_spec_is_default=install_spec_is_default,
        )

    install_spec = _validate_install_spec(config.alphasift_install_spec)

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
            detail={
                "error": "alphasift_install_failed",
                "message": f"自动安装 AlphaSift 失败：{detail}",
            },
        )

    importlib.invalidate_caches()
    if not _is_alphasift_available():
        raise HTTPException(
            status_code=424,
            detail={"error": "alphasift_unavailable", "message": "AlphaSift 安装完成，但当前进程仍无法导入 alphasift。请重启后端后重试。"},
        )

    return _build_install_response(
        already_installed=False,
        install_spec_is_default=_is_default_alphasift_install_spec(install_spec),
    )


def _validate_install_spec(raw_install_spec: str) -> str:
    install_spec = (raw_install_spec or "").strip()
    if not install_spec or install_spec.lower() == "alphasift":
        raise HTTPException(
            status_code=424,
            detail={
                "error": "alphasift_install_spec_missing",
                "message": f"请先将 ALPHASIFT_INSTALL_SPEC 配置为受信任来源：{DEFAULT_ALPHASIFT_INSTALL_SPEC}。",
            },
        )

    if install_spec not in ALLOWED_ALPHASIFT_INSTALL_SPECS:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "alphasift_install_spec_not_allowed",
                "message": (
                    "出于安全考虑，自动安装 AlphaSift 仅允许使用受信任来源："
                    f"{DEFAULT_ALPHASIFT_INSTALL_SPEC}。如需使用本地路径或 wheel，请先手动安装到当前 Python 环境。"
                ),
            },
        )

    return install_spec


@router.post("/screen")
def alphasift_screen(
    request: AlphaSiftScreenRequest,
    config: Config = Depends(get_config_dep),
) -> Dict[str, Any]:
    _ensure_alphasift_enabled(config)

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


def _ensure_alphasift_enabled(config: Config) -> None:
    if not config.alphasift_enabled:
        raise HTTPException(
            status_code=403,
            detail={"error": "alphasift_disabled", "message": "ALPHASIFT_ENABLED is false."},
        )


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
        for key in ("picks", "candidates", "items", "results", "stocks"):
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
    score = item.get("score")
    if score is None:
        score = item.get("final_score")

    return {
        "rank": item.get("rank") or rank,
        "code": item.get("code") or item.get("symbol") or item.get("stock_code") or "",
        "name": item.get("name") or item.get("stock_name") or "",
        "score": score,
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


def _build_install_response(already_installed: bool, install_spec_is_default: bool) -> Dict[str, Any]:
    return {
        "installed": True,
        "already_installed": already_installed,
        "install_spec_is_default": install_spec_is_default,
    }


def _is_default_alphasift_install_spec(install_spec: str) -> bool:
    return (install_spec or "").strip() == DEFAULT_ALPHASIFT_INSTALL_SPEC
