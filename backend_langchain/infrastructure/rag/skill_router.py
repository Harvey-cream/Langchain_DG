from __future__ import annotations

import math
import os
import threading
import logging
from dataclasses import dataclass
from collections.abc import Callable
from typing import Iterable, Literal

from langchain_core.embeddings import Embeddings

from backend_langchain.logger_func import log_info_event
from config.config import DEFAULT_HF_MODEL
from infrastructure.rag.embedding import get_embedding_model


@dataclass(frozen=True)
class SkillSpec:
    name: str
    when: str
    output_schema: str
    prototypes: tuple[str, ...]
    anti_prototypes: tuple[str, ...] = ()


_EMBEDDING_MODEL = os.getenv("SKILL_ROUTER_EMBEDDING_MODEL", DEFAULT_HF_MODEL)
_ROUTER_MIN_SIM = float(os.getenv("SKILL_ROUTER_MIN_SIM", "0.32"))
_ROUTER_DEBUG = os.getenv("SKILL_ROUTER_DEBUG", "0").strip() == "1"
logger = logging.getLogger(__name__)
_embedding_singleton: Embeddings | None = None
_embedding_lock = threading.Lock()
# 每条 prototype / anti_prototype 文案只嵌入一次，避免每条用户消息重复十几次 embed_query。
_phrase_vec_cache: dict[str, list[float]] = {}
_phrase_vec_lock = threading.Lock()


def _get_embeddings() -> Embeddings:
    global _embedding_singleton
    if _embedding_singleton is None:
        with _embedding_lock:
            if _embedding_singleton is None:
                _embedding_singleton = get_embedding_model(
                    _EMBEDDING_MODEL,
                    device="cpu",
                    normalize_embeddings=True,
                    batch_size=32,
                )
    return _embedding_singleton


def _embed_text(text: str) -> list[float]:
    emb = _get_embeddings()
    return emb.embed_query((text or "").strip())


def _embed_phrase_cached(text: str) -> list[float]:
    key = (text or "").strip()
    if not key:
        return []
    if key not in _phrase_vec_cache:
        with _phrase_vec_lock:
            if key not in _phrase_vec_cache:
                _phrase_vec_cache[key] = _embed_text(key)
    return _phrase_vec_cache[key]


def _all_skill_phrase_keys(catalogs: Iterable[tuple[SkillSpec, ...]]) -> list[str]:
    seen: set[str] = set()
    keys: list[str] = []
    for catalog in catalogs:
        for spec in catalog:
            for p in spec.prototypes:
                k = (p or "").strip()
                if k and k not in seen:
                    seen.add(k)
                    keys.append(k)
            for p in spec.anti_prototypes:
                k = (p or "").strip()
                if k and k not in seen:
                    seen.add(k)
                    keys.append(k)
            w = (spec.when or "").strip()
            if w and w not in seen:
                seen.add(w)
                keys.append(w)
    return keys


def warmup_skill_phrase_cache(*catalogs: tuple[SkillSpec, ...]) -> None:
    """启动时预计算 skill 路由所需短语向量，填入进程内缓存。

    调用方（组合根）传入各产品线 Skill catalog，本模块不感知具体业务目录。
    """
    for phrase_key in _all_skill_phrase_keys(catalogs):
        _embed_phrase_cached(phrase_key)


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return -1.0
    dot = 0.0
    na = 0.0
    nb = 0.0
    for x, y in zip(a, b):
        dot += x * y
        na += x * x
        nb += y * y
    if na <= 0.0 or nb <= 0.0:
        return -1.0
    return dot / (math.sqrt(na) * math.sqrt(nb))


def _skill_match_score(query_vec: list[float], spec: SkillSpec) -> float:
    proto_scores = [_cosine(query_vec, _embed_phrase_cached(p)) for p in spec.prototypes]
    when_text = (spec.when or "").strip()
    if when_text:
        proto_scores.append(_cosine(query_vec, _embed_phrase_cached(when_text)))
    best_proto = max(proto_scores) if proto_scores else -1.0
    if not spec.anti_prototypes:
        return best_proto
    anti_scores = [_cosine(query_vec, _embed_phrase_cached(p)) for p in spec.anti_prototypes]
    best_anti = max(anti_scores) if anti_scores else 0.0
    # 反向惩罚：降低错误路由（例如文档问答误进 repo_inspector）。
    return best_proto - 0.25 * best_anti


def _pick_skill(user_input: str, skills: Iterable[SkillSpec]) -> SkillSpec | None:
    text = (user_input or "").strip().lower()
    if not text:
        return None
    qvec = _embed_text(text)
    best: SkillSpec | None = None
    best_score = -1.0
    score_rows: list[tuple[str, float]] = []
    for spec in skills:
        score = _skill_match_score(qvec, spec)
        score_rows.append((spec.name, score))
        if score > best_score:
            best_score = score
            best = spec
    if _ROUTER_DEBUG:
        preview = (user_input or "").replace("\n", " ")[:120]
        msg = (
            f"skill_router input={preview!r} "
            f"scores={', '.join(f'{name}:{score:.4f}' for name, score in score_rows)} "
            f"best={best.name if best else None} "
            f"best_score={best_score:.4f} min_sim={_ROUTER_MIN_SIM:.4f}"
        )
        print(msg)
        log_info_event(logger, "skill_router_debug_scores", message=msg)
    if best is None:
        return None
    if best_score < _ROUTER_MIN_SIM:
        if _ROUTER_DEBUG:
            print("skill_router not selected: best score below threshold")
            log_info_event(logger, "skill_router_not_selected_below_threshold")
        return None
    preview = (user_input or "").replace("\n", " ")[:120]
    log_info_event(
        logger,
        "skill_router_selected",
        selected=best.name,
        score=round(best_score, 4),
        input=preview,
    )
    if _ROUTER_DEBUG:
        print(f"skill_router selected={best.name}")
        log_info_event(logger, "skill_router_debug_selected", selected=best.name)
    return best


def _render_skill_context(spec: SkillSpec | None) -> str:
    if spec is None:
        return ""
    return (
        "【Skill 路由】\n"
        f"- 当前激活：{spec.name}\n"
        f"- 适用场景：{spec.when}\n"
        f"- 输出结构：{spec.output_schema}\n"
        "- 要求：先按该结构组织，再结合下方检索参考给出可执行回答。"
    )


RecallMode = Literal["main", "interview"]


async def prepare_turn_context(
    user_input: str,
    *,
    mode: RecallMode,
    skills: tuple[SkillSpec, ...],
    recent_dialogue: str = "",
    on_search: Callable[[], None] | None = None,
    user_id: int | None = None,
    skip_rag: bool = False,
    precomputed_retrieved: str = "",
) -> tuple[SkillSpec | None, str, str]:
    """Skill 向量路由 → Retrieval Planner →（按需）粗召回 + 精排。

    skills 由调用方（子图/产品线 runtime）传入，本模块不持有业务 Skill 目录。
    skip_rag=True：仅做 Skill，复用 precomputed_retrieved（Context Builder 已检索）。
    """
    from infrastructure.rag.rag import retrieve_context
    from infrastructure.rag.retrieval_planner import plan_retrieval
    from config.config import CORPUS_INTERVIEW, CORPUS_USER

    text = (user_input or "").strip()
    catalog = skills
    spec = _pick_skill(text, catalog) if text else None
    # 单 Skill 子图（如文档摘要）：低置信时仍落到该图主 Skill，避免空 skill_context
    if spec is None and len(catalog) == 1:
        spec = catalog[0]
    skill_context = _render_skill_context(spec)
    skill_name = spec.name if spec else None

    if skip_rag:
        return spec, skill_context, (precomputed_retrieved or "").strip()

    retrieved = ""
    if text:
        plan = await plan_retrieval(
            text,
            mode=mode,
            skill_name=skill_name,
            recent_dialogue=recent_dialogue,
        )
        if plan.need_rag:
            if on_search:
                on_search()
            questions = plan.search_questions or [text]
            if mode == "interview":
                retrieved = retrieve_context(questions, corpus=CORPUS_INTERVIEW)
            else:
                retrieved = retrieve_context(
                    questions,
                    corpus=CORPUS_USER,
                    user_id=user_id,
                )
    return spec, skill_context, retrieved

