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
        when="基于项目知识库的知识问答（教程/面试沉淀主题）",
        output_schema="问题澄清 -> 命中知识点 -> 答案总结 -> 延伸建议",
        prototypes=(
            "用户在问某个概念是什么、怎么理解、原理是什么。",
            "用户询问 OpenClaw、Vibe Coding、RAG、Agent 等教程/知识库条目。",
            "用户询问 MCP（Model Context Protocol）是什么、做什么、和其他方案有什么区别。",
            "用户希望解释术语、做知识点对比与归纳总结。",
        ),
    ),
    SkillSpec(
        name="repo_inspector",
        when="仅当用户提供 GitHub/Gitee 仓库链接（或明确仓库坐标）时触发；用于解析仓库元信息与能力",
        output_schema="仓库识别 -> 关键信息提取 -> 结构化总结 -> 下一步建议",
        prototypes=(
            "用户贴了 github 或 gitee 仓库链接，希望解析仓库信息、star、分支、issues。",
            "用户给出 owner/repo 等仓库坐标，要求分析该开源仓库的结构与关键指标。",
        ),
        anti_prototypes=(
            "用户只是在问概念定义，例如 MCP 是什么、原理是什么、和谁的区别是什么。",
            "用户没有提供任何 GitHub/Gitee 仓库链接或仓库坐标。",
        ),
    ),
    SkillSpec(
        name="document_export",
        when="用户明确要导出 PDF、生成可下载文档、打印/保存排版材料；含把对话、笔记、代码/源码/项目说明整理成 PDF 交付",
        output_schema="人机协同：必须先调用 confirm_pdf_export 一次；用户确认后结合上下文润色，再调用 finalize_pdf_export 一次（title + body_markdown）生成可下载 PDF；确认前勿声称已生成文件",
        prototypes=(
            "用户要求把当前对话或某段内容导出成 PDF。",
            "用户希望生成可下载的 PDF、打印版学习路线或排版好的材料。",
            "用户说整理成文档、做成 PDF、导出发我、给我正式版/打印版。",
            "用户要把总结、路线图、笔记输出为 PDF 或 Word 式交付物（以 PDF 为统一出口时可等同处理）。",
            "用户要把代码、源码、刚写的程序、项目说明或 README 整理成 PDF 或导出为 PDF。",
            "用户说把这段代码打成 PDF、代码导出 PDF、打印代码、代码片段生成文档版。",
            "用户要求把仓库里的代码、解决方案、实现步骤导出成可打印的 PDF 材料。",
        ),
        anti_prototypes=(
            "用户只是在问 PDF 是什么、格式原理、和其它格式的区别，不要求导出文件。",
            "用户只要改 bug、写实现或调试，全文未提及导出、PDF、下载、打印、文档交付。",
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
    SkillSpec(
        name="document_export",
        when="用户要把面试准备内容导出为 PDF；含代码题解答、手写代码、算法步骤整理成 PDF",
        output_schema="人机协同：先 confirm_pdf_export；用户确认后润色全文再 finalize_pdf_export；确认前勿声称已生成文件",
        prototypes=(
            "用户希望把面试题总结、错题本或准备清单导出成 PDF。",
            "用户要下载打印版面试材料、PDF 版复习大纲。",
            "用户说整理成文档发我、做成 PDF。",
            "用户要把代码题答案、手写代码、算法实现过程导出或打印成 PDF。",
        ),
        anti_prototypes=(
            "用户只在模拟面试问答，未要求导出或 PDF。",
            "用户只问某题怎么答、知识点是什么，不要求文档或下载。",
        ),
    ),
)

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


def _all_skill_phrase_keys() -> list[str]:
    seen: set[str] = set()
    keys: list[str] = []
    for catalog in (AGENT_SKILLS, INTERVIEW_SKILLS):
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


def warmup_skill_phrase_cache() -> None:
    """启动时预计算 skill 路由所需短语向量，填入进程内缓存。"""
    for phrase_key in _all_skill_phrase_keys():
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
    recent_dialogue: str = "",
    on_search: Callable[[], None] | None = None,
) -> tuple[SkillSpec | None, str, str]:
    """Skill 向量路由 → RAG 门控 → 问句改写 → 粗召回 + 精排检索。"""
    from common.query_rewrite import rewrite_search_queries
    from common.rag import retrieve_context
    from common.rag_gate import decide_rag_gate
    from config.config import CORPUS_AGENT, CORPUS_INTERVIEW

    text = (user_input or "").strip()
    skills = AGENT_SKILLS if mode == "main" else INTERVIEW_SKILLS
    spec = _pick_skill(text, skills) if text else None
    skill_context = _render_skill_context(spec)
    skill_name = spec.name if spec else None

    retrieved = ""
    if text:
        need_rag = await decide_rag_gate(text, mode=mode, skill_name=skill_name)
        if need_rag:
            if on_search:
                on_search()
            questions = await rewrite_search_queries(
                text,
                mode=mode,
                skill_name=skill_name,
                recent_dialogue=recent_dialogue,
            )
            corpus = CORPUS_INTERVIEW if mode == "interview" else CORPUS_AGENT
            retrieved = retrieve_context(questions, corpus=corpus)
    return spec, skill_context, retrieved


def build_agent_skill_context(user_input: str) -> str:
    return _render_skill_context(_pick_skill(user_input, AGENT_SKILLS))


def build_interview_skill_context(user_input: str) -> str:
    return _render_skill_context(_pick_skill(user_input, INTERVIEW_SKILLS))

