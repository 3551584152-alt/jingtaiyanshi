# -*- coding: utf-8 -*-
"""CT4 Django JSON API（对应 CT4项目1.0 客户端 api 模块契约）。"""
import json

from django.contrib.auth.models import User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone

from .auth import do_login, login_required, make_token, user_payload
from .models import Word
from . import services as svc
from . import llm as llm


def body(request):
    """解析 JSON 请求体；非对象或非法 JSON 统一按空对象处理。"""
    try:
        data = json.loads(request.body.decode("utf-8") or "{}")
    except (TypeError, ValueError, UnicodeDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def text(value):
    return value.strip() if isinstance(value, str) else ""


def int_value(value, field, default=0, minimum=None, maximum=None):
    """把查询参数/JSON 值安全转换为整数，并做范围校验。"""
    if value is None or value == "":
        result = default
    else:
        if isinstance(value, bool):
            raise ValueError("%s 必须是整数" % field)
        try:
            result = int(value)
        except (TypeError, ValueError):
            raise ValueError("%s 必须是整数" % field) from None
    if result is None:
        raise ValueError("%s 不能为空" % field)
    if minimum is not None and result < minimum:
        raise ValueError("%s 不能小于 %s" % (field, minimum))
    if maximum is not None and result > maximum:
        raise ValueError("%s 不能大于 %s" % (field, maximum))
    return int(result)


def bool_value(value, default=True):
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("1", "true", "yes", "on"):
            return True
        if normalized in ("0", "false", "no", "off", ""):
            return False
    return bool(value)


def ok(data, status=200):
    return JsonResponse(data, status=status)


def err(msg, status=400):
    return JsonResponse({"detail": msg}, status=status)


# ---------------- auth ----------------
@csrf_exempt
def register(request):
    b = body(request)
    username = text(b.get("username"))
    password = text(b.get("password"))
    nickname = text(b.get("nickname"))
    if len(username) < 3:
        return err("用户名至少 3 个字符")
    if len(password) < 6:
        return err("密码至少 6 位")
    if User.objects.filter(username=username).exists():
        return err("用户名已存在")
    user = User.objects.create_user(username=username, password=password)
    user.first_name = nickname or username
    user.save()
    return ok({"access_token": make_token(user), "user": user_payload(user)})


@csrf_exempt
def login(request):
    b = body(request)
    username = text(b.get("username"))
    password = b.get("password") if isinstance(b.get("password"), str) else ""
    user = do_login(username, password)
    if user is None:
        return err("用户名或密码错误", 401)
    return ok({"access_token": make_token(user), "user": user_payload(user)})


@login_required
def me(request, user):
    return ok(user_payload(user))


# ---------------- words ----------------
@login_required
def words_today(request, user):
    try:
        limit = int_value(request.GET.get("limit"), "limit", 40, 1, 200)
    except ValueError as exc:
        return err(str(exc))
    return ok({"items": svc.today_words(user, limit)})


@login_required
def words_list(request, user):
    topic = text(request.GET.get("topic"))
    sort = text(request.GET.get("sort")) or "word"
    if topic not in ("", "read", "listen", "translate", "write"):
        return err("topic 参数无效")
    if sort not in ("word", "freq", "difficulty", "new"):
        return err("sort 参数无效")
    try:
        learned = int_value(request.GET.get("learned"), "learned", 0, 0, 2)
        page = int_value(request.GET.get("page"), "page", 1, 1, 1000000)
        size = int_value(request.GET.get("size"), "size", 30, 1, 200)
    except ValueError as exc:
        return err(str(exc))
    data = svc.word_search(
        user,
        q=text(request.GET.get("q")),
        topic=topic,
        learned=learned,
        sort=sort,
        page=page,
        size=size,
    )
    return ok(data)


@login_required
def words_lookup(request, user):
    w = text(request.GET.get("word")).lower()
    word = Word.objects.filter(word__iexact=w).first()
    if not word:
        return err("词库中未找到该单词", 404)
    return ok(svc.word_dict(word, user))


@login_required
def word_detail(request, user, word_id):
    try:
        word = Word.objects.get(id=word_id)
    except Word.DoesNotExist:
        return err("单词不存在", 404)
    return ok(svc.word_dict(word, user))


# ---------------- records ----------------
@login_required
def record_submit(request, user):
    b = body(request)
    wid = b.get("word_id")
    if wid in (None, ""):
        return err("缺少 word_id")
    try:
        word_id = int_value(wid, "word_id", minimum=1)
        quality = int_value(b.get("quality"), "quality", 3, 0, 5)
    except ValueError as exc:
        return err(str(exc))
    plan = svc.submit(
        user, word_id,
        quality=quality,
        review_type=text(b.get("review_type")) or "learn",
        topic=text(b.get("topic")),
        is_correct=bool_value(b.get("is_correct"), True),
    )
    if plan is None:
        return err("单词不存在", 404)
    return ok(plan)


@login_required
def record_sync(request, user):
    records = body(request).get("records")
    if records is None:
        records = []
    if not isinstance(records, list):
        return err("records 必须是数组")
    results = []
    for r in records:
        if not isinstance(r, dict) or r.get("word_id") in (None, ""):
            continue
        try:
            word_id = int_value(r.get("word_id"), "word_id", minimum=1)
            quality = int_value(r.get("quality"), "quality", 3, 0, 5)
        except ValueError:
            continue
        plan = svc.submit(
            user, word_id,
            quality=quality,
            review_type=text(r.get("review_type")) or "learn",
            topic=text(r.get("topic")),
            is_correct=bool_value(r.get("is_correct"), True),
        )
        if plan:
            results.append(plan)
    return ok({"results": results, "synced": len(results)})


# ---------------- stats / plan / notebook ----------------
@login_required
def stats_summary(request, user):
    s = svc.stats_summary(user)
    plan = svc.plan_daily(user)
    s["plan_done"] = plan["completed"]
    s["plan_total"] = plan["total"]
    return ok(s)


@login_required
def plan_daily(request, user):
    d = text(request.GET.get("date")) or None
    refresh = request.GET.get("refresh") == "1"
    return ok(svc.plan_daily(user, d, refresh))


@login_required
def notebook_wrong(request, user):
    try:
        limit = int_value(request.GET.get("limit"), "limit", 200, 1, 500)
    except ValueError as exc:
        return err(str(exc))
    return ok({"items": svc.notebook_items(user, "wrong", limit)})


@login_required
def notebook_stubborn(request, user):
    try:
        limit = int_value(request.GET.get("limit"), "limit", 200, 1, 500)
    except ValueError as exc:
        return err(str(exc))
    return ok({"items": svc.notebook_items(user, "stubborn", limit)})


@login_required
def notebook_summary(request, user):
    from django.db.models import Q
    wrong = svc.ReviewState.objects.filter(user=user, wrong_count__gt=0).count()
    stubborn = svc.ReviewState.objects.filter(user=user).filter(
        Q(lapses__gte=3) | Q(wrong_count__gte=3)).count()
    return ok({"wrong_total": wrong, "stubborn_total": stubborn})


# ---------------- AI / agents (本地结构化降级) ----------------
@login_required
def ai_example(request, user):
    b = body(request)
    wid = b.get("word_id")
    wname = text(b.get("word"))
    word = None
    if wid not in (None, ""):
        try:
            wid = int_value(wid, "word_id", minimum=1)
        except ValueError as exc:
            return err(str(exc))
        word = Word.objects.filter(id=wid).first()
    if word is None and wname:
        word = Word.objects.filter(word__iexact=wname).first()
    if word is None:
        return err("未在词库中找到该单词", 404)
    if llm.is_configured():
        try:
            raw_text = llm.chat([
                {"role": "system", "content": "你是 CET-4 英语老师，为单词生成地道例句。只输出 JSON 数组，不要任何其他文字。"},
                {"role": "user", "content": "单词：%s (%s) 释义：%s。请给出 2 个不同场景的英文例句及中文翻译，格式：[{\"en\":\"英文\",\"cn\":\"中文\"}]" % (word.word, word.pos, word.meaning)},
            ])
            arr = llm.parse_json(raw_text)
            if isinstance(arr, list):
                examples = []
                for x in arr[:3]:
                    if isinstance(x, dict) and str(x.get("en") or "").strip():
                        examples.append({"en": str(x["en"]).strip(), "cn": str(x.get("cn") or "").strip()})
                if examples:
                    return ok({"examples": examples, "note": "由 %s 生成" % llm.provider_label()})
        except Exception as e:
            return ok({"examples": svc.local_examples(word), "note": "大模型调用失败，已降级本地生成：" + str(e)})
    note = "本地例句生成（未配置大模型 Key）" if not llm.is_configured() else "大模型未返回有效例句，已降级本地生成"
    return ok({"examples": svc.local_examples(word), "note": note})


@login_required
def agent_plan(request, user):
    s = svc.stats_summary(user)
    local = svc.local_planner(user)
    if llm.is_configured():
        try:
            compact = {k: s.get(k) for k in ("learned_total", "mastered", "due_today", "new_remaining", "streak_days", "accuracy", "wrong_count", "stubborn_count", "plan_done", "plan_total")}
            compact["topics"] = s.get("topics") or []
            raw_text = llm.chat([
                {"role": "system", "content": "你是 CET-4 学习规划师。必须只输出一个合法 JSON 对象，不要输出任何解释、注释或 Markdown。"},
                {"role": "user", "content": "根据我的学习统计生成规划：%s。JSON 结构固定为：{\"summary\":\"学情总结\",\"strengths\":[\"优势1\"],\"weaknesses\":[\"薄弱1\"],\"advice\":[\"建议1\",\"建议2\",\"建议3\"]}" % json.dumps(compact, ensure_ascii=False)},
            ])
            d = llm.parse_json(raw_text)
            if isinstance(d, dict) and (d.get("advice") or d.get("summary")):
                def as_list(v, fallback):
                    if isinstance(v, list):
                        out = [str(x) for x in v if str(x).strip()][:6]
                        return out or fallback
                    return fallback
                return ok({
                    "summary": str(d.get("summary") or ("已学 %d 词，掌握 %d 词。" % (s["learned_total"], s["mastered"]))),
                    "strengths": as_list(d.get("strengths"), ["坚持学习即为优势"]),
                    "weaknesses": as_list(d.get("weaknesses"), ["无明显短板"]),
                    "advice": as_list(d.get("advice"), ["保持每日新学与复习节奏"]),
                    "stats": s,
                    "note": "由 %s 生成规划" % llm.provider_label(),
                })
            local["note"] = "大模型返回内容无法解析，已用本地规则生成规划"
            return ok(local)
        except Exception as e:
            local["note"] = "大模型调用失败，已降级本地：" + str(e)
            return ok(local)
    return ok(local)


@login_required
def agent_tutor(request, user):
    b = body(request)
    wname = text(b.get("word"))
    if not wname and b.get("word_id") not in (None, ""):
        try:
            word_id = int_value(b.get("word_id"), "word_id", minimum=1)
        except ValueError as exc:
            return err(str(exc))
        w = Word.objects.filter(id=word_id).first()
        wname = w.word if w else ""
    word = Word.objects.filter(word__iexact=wname).first()
    if word is None:
        return err("未在词库中找到该单词", 404)
    base = svc.local_tutor(user, word.word) or {}
    if llm.is_configured():
        try:
            raw_text = llm.chat([
                {"role": "system", "content": "你是 CET-4 词汇辅导老师，讲解要简明、适合背单词。只输出 JSON，不要其他文字。"},
                {"role": "user", "content": "词条：word=%s; phonetic=%s; pos=%s; meaning=%s; example=%s; synonyms=%s。输出 JSON：{\"explanation\":\"简明中文讲解\",\"mnemonic\":\"联想记忆\",\"collocations\":[\"搭配\"],\"confusable\":[\"易混词\"],\"usage\":\"英文例句\",\"example_cn\":\"例句中文\"}" % (word.word, word.phonetic, word.pos, word.meaning, word.example, ",".join(word.synonyms or []))},
            ])
            d = llm.parse_json(raw_text)
            if isinstance(d, dict):
                for k in ("explanation", "mnemonic", "usage", "example_cn"):
                    v = d.get(k)
                    if isinstance(v, str) and v.strip():
                        base[k] = v.strip()
                    elif v is not None and not isinstance(v, str):
                        text_value = str(v).strip()
                        if text_value:
                            base[k] = text_value
                collocations = d.get("collocations")
                if isinstance(collocations, list) and collocations:
                    base["collocations"] = [str(x) for x in collocations if str(x).strip()][:8]
                confusable = d.get("confusable")
                if isinstance(confusable, list) and confusable:
                    base["confusable"] = [str(x) for x in confusable if str(x).strip()][:8]
                base["note"] = "由 %s 生成讲解" % llm.provider_label()
                return ok(base)
        except Exception as e:
            base["note"] = "大模型调用失败，已降级本地：" + str(e)
            return ok(base)
    return ok(base)


@login_required
def agent_train(request, user):
    b = body(request)
    topic = text(b.get("topic")) or "read"
    if topic not in ("read", "listen", "translate", "write"):
        return err("topic 参数无效")
    try:
        count = int_value(b.get("count"), "count", 4, 1, 20)
    except ValueError as exc:
        return err(str(exc))
    questions = svc.build_train_questions(
        user, topic=topic,
        word=text(b.get("word")) or None,
        stubborn_only=bool_value(b.get("stubborn_only"), False),
        count=count,
    )
    if not questions:
        return err("没有可出题的单词（可先背诵积累或确认顽固词存在）", 400)
    return ok({"questions": questions, "topic": topic,
               "note": "本地出题引擎（例句/讲解/规划已接入大模型）"})


@login_required
def agent_analyze(request, user):
    b = body(request)
    wname = text(b.get("word"))
    if not wname and b.get("word_id") not in (None, ""):
        try:
            word_id = int_value(b.get("word_id"), "word_id", minimum=1)
        except ValueError as exc:
            return err(str(exc))
        w = Word.objects.filter(id=word_id).first()
        wname = w.word if w else ""
    word = Word.objects.filter(word__iexact=wname).first()
    if word is None:
        return err("未在词库中找到该单词", 404)
    wd = svc.word_dict(word, user)
    base = svc.local_analyze(user, word.word) or {}
    if llm.is_configured():
        try:
            raw_text = llm.chat([
                {"role": "system", "content": "你是 CET-4 错题分析老师。根据词条与学习情况输出 JSON，只输出 JSON 不要其他文字。"},
                {"role": "user", "content": "单词：%s (%s) 释义：%s。学习情况：遗忘 %d 次、答错 %d 次、答对 %d 次。输出 JSON：{\"analysis\":\"错因分析\",\"suggestion\":\"改进建议\"}" % (word.word, word.pos, word.meaning, wd["lapses"], wd["wrong_count"], wd["correct_count"])},
            ])
            d = llm.parse_json(raw_text)
            if isinstance(d, dict):
                analysis_value = d.get("analysis")
                suggestion_value = d.get("suggestion")
                if analysis_value or suggestion_value:
                    analysis_text = str(analysis_value or "").strip()
                    suggestion_text = str(suggestion_value or "").strip()
                    if analysis_text:
                        base["analysis"] = analysis_text
                    if suggestion_text:
                        base["suggestion"] = suggestion_text
                    base["note"] = "由 %s 生成分析" % llm.provider_label()
                    return ok(base)
        except Exception as e:
            base["note"] = "大模型调用失败，已降级本地：" + str(e)
            return ok(base)
    return ok(base)
# ---------------- public root / health ----------------
@csrf_exempt
def api_root(request):
    return ok({
        "project": "CT4 单词记忆",
        "backend": "Django 6.1.1",
        "frontend": "Vue 3.5.25 (Vite SPA)",
        "note": "前后端已解耦，本接口由 Django 提供",
        "endpoints": [
            "/api/auth/register", "/api/auth/login", "/api/auth/me",
            "/api/words/today", "/api/words", "/api/words/lookup", "/api/words/{id}",
            "/api/records", "/api/records/sync", "/api/stats/summary",
            "/api/plan/daily", "/api/notebook/wrong", "/api/notebook/stubborn",
            "/api/notebook/summary", "/api/ai/example",
            "/api/agents/plan", "/api/agents/tutor", "/api/agents/train", "/api/agents/analyze",
        ],
    })


@csrf_exempt
def health(request):
    return ok({"status": "ok", "time": timezone.now().isoformat()})
