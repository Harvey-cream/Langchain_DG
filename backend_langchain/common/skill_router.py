from __future__ import annotations

import math
import os
import threading
import logging
from dataclasses import dataclass
from typing import Iterable

from langchain_core.embeddings import Embeddings

from common.embedding import get_embedding_model


@dataclass(frozen=True)
class SkillSpec:
    name: str
    when: str
    output_schema: str
    prototypes: tuple[str, ...]
    anti_prototypes: tuple[str, ...] = ()


AGENT_SKILLS: tuple[SkillSpec, ...] = (
    SkillSpec(
        name="coding_coach",
        when="报错排查、代码改造、方案对比、性能/可维护性优化",
        output_schema="问题定位 -> 最小修复 -> 原理解释 -> 验证步骤",
        prototypes=(
            "用户贴出报错堆栈，需要定位 bug 并给出最小可行修复。",
            "用户要求重构代码、比较实现方案、做性能与可维护性优化。",
            "用户提供代码片段，希望修改实现并给出验证步骤。",
        ),
        anti_prototypes=(
            "用户在问概念定义，例如某工具是什么、原理是什么。",
        ),
    ),
    SkillSpec(
        name="learning_planner",
        when="学习路线、周计划、项目驱动学习、阶段目标拆解",
        output_schema="目标拆分 -> 周任务 -> 里程碑 -> 复盘",
        prototypes=(
            "用户希望制定学习路线图，按阶段拆分目标与任务。",
            "用户希望得到周计划、里程碑和复盘节奏。",
        ),
    ),
    SkillSpec(
        name="knowledge_qa",
        when="基于项目知识库的知识问答（chroma_db 沉淀主题）",
        output_schema="问题澄清 -> 命中知识点 -> 答案总结 -> 延伸建议",
        prototypes=(
            "用户在问某个概念是什么、怎么理解、原理是什么。",
            "用户询问 OpenClaw、Vibe Coding、RAG、Agent 等教程/知识库条目。",
            "用户希望解释术语、做知识点对比与归纳总结。",
        ),
    ),
    SkillSpec(
        name="repo_inspector",
        when="用户提供 GitHub/Gitee 仓库地址；优先使用已接入的 MCP 工具（如 Gitee MCP）解析元信息与仓库能力",
        output_schema="仓库识别 -> 关键信息提取 -> 结构化总结 -> 下一步建议",
        prototypes=(
            "用户贴了 github 或 gitee 仓库链接，希望解析仓库信息、star、分支、issues。",
            "用户想快速了解一个开源仓库，要求给出仓库简介与关键指标。",
        ),
    ),
)


INTERVIEW_SKILLS: tuple[SkillSpec, ...] = (
    SkillSpec(
        name="interview_mock",
        when="面试问答、追问演练、答题优化",
        output_schema="考点 -> 标准答法 -> 高频追问 -> 易错点",
        prototypes=(
            "用户在准备技术面试，需要模拟问答与追问演练。",
            "用户希望优化面试表达，给出标准答法与易错点。",
        ),
    ),
    SkillSpec(
        name="learning_planner",
        when="求职学习路线、冲刺计划、项目补齐",
        output_schema="目标拆分 -> 周任务 -> 里程碑 -> 复盘",
        prototypes=(
            "用户要制定面试准备计划、冲刺节奏和里程碑。",
            "用户希望拆解周任务并给出复盘节奏。",
        ),
    ),
    SkillSpec(
        name="knowledge_qa",
        when="题库/知识库条目的解释、对比与归纳",
        output_schema="问题澄清 -> 命中知识点 -> 答案总结 -> 延伸建议",
        prototypes=(
            "用户询问题库知识点定义、原理、区别与归纳。",
            "用户问 Java、Vue、大模型等面试知识点是什么或怎么理解。",
        ),
    ),
)

_EMBEDDING_MODEL = os.getenv("SKILL_ROUTER_EMBEDDING_MODEL", "BAAI/bge-small-zh-v1.5")
_ROUTER_MIN_SIM = float(os.getenv("SKILL_ROUTER_MIN_SIM", "0.32"))
_ROUTER_DEBUG = os.getenv("SKILL_ROUTER_DEBUG", "0").strip() == "1"
logger = logging.getLogger(__name__)
_embedding_singleton: Embeddings | None = None
_embedding_lock = threading.Lock()
_skill_vec_cache: dict[str, list[float]] = {}
_skill_vec_lock = threading.Lock()


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


def _skill_vector(spec: SkillSpec) -> list[float]:
    if spec.name not in _skill_vec_cache:
        with _skill_vec_lock:
            if spec.name not in _skill_vec_cache:
                text = (
                    f"skill={spec.name}\n"
                    f"when={spec.when}\n"
                    f"schema={spec.output_schema}\n"
                    f"prototypes={' | '.join(spec.prototypes)}\n"
                    f"anti={' | '.join(spec.anti_prototypes)}"
                )
                _skill_vec_cache[spec.name] = _embed_text(text)
    return _skill_vec_cache[spec.name]


def _skill_match_score(query_vec: list[float], spec: SkillSpec) -> float:
    proto_scores = [_cosine(query_vec, _embed_text(p)) for p in spec.prototypes]
    best_proto = max(proto_scores) if proto_scores else -1.0
    if not spec.anti_prototypes:
        return best_proto
    anti_scores = [_cosine(query_vec, _embed_text(p)) for p in spec.anti_prototypes]
    best_anti = max(anti_scores) if anti_scores else 0.0
    # 反向惩罚：降低错误路由（例如“什么是X”误进 coding_coach）。
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
        logger.info(msg)
    if best is None:
        return None
    if best_score < _ROUTER_MIN_SIM:
        if _ROUTER_DEBUG:
            print("skill_router not selected: best score below threshold")
            logger.info("skill_router not selected: best score below threshold")
        return None
    if _ROUTER_DEBUG:
        print(f"skill_router selected={best.name}")
        logger.info("skill_router selected=%s", best.name)
    return best


def _render_skill_context(spec: SkillSpec | None) -> str:
    if spec is None:
        return ""
    return (
        "【Skill 路由】\n"
        f"- 当前激活：{spec.name}\n"
        f"- 适用场景：{spec.when}\n"
        f"- 输出结构：{spec.output_schema}\n"
        "- 要求：先按该结构组织，再结合工具检索结果给出可执行回答。"
    )


def build_agent_skill_context(user_input: str) -> str:
    return _render_skill_context(_pick_skill(user_input, AGENT_SKILLS))


def build_interview_skill_context(user_input: str) -> str:
    return _render_skill_context(_pick_skill(user_input, INTERVIEW_SKILLS))

