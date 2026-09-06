"""Personalization scoring channels: constraint / context memories must
reach the ranking, and scoring must see the full memory history (spec:
不能只让 task-anchored 记忆参与排序)."""

from weilv.personal_rag import (
    merge_full_memory_history,
    personalize_task_candidates,
)


def task(task_id, minutes, contexts, rank=None):
    position = rank or int(task_id.split("-")[-1])
    return {
        "task_id": task_id,
        "estimated_minutes": minutes,
        "execution_contexts": contexts,
        "rerank_rank": position,
    }


def memory(memory_id, memory_type, value, task_id=None):
    return {
        "memory_id": memory_id,
        "user_id": "u-1",
        "memory_type": memory_type,
        "source_type": "questionnaire_cold_start",
        "task_id": task_id,
        "memory_key": memory_type,
        "memory_value": value,
        "retrieval_text": f"type={memory_type}",
        "active": True,
        "review_status": "valid",
    }


def order(tasks):
    return [item["task_id"] for item in personalize_task_candidates(tasks, [])]


def deltas(tasks, memories):
    result = personalize_task_candidates(tasks, memories)
    return {item["task_id"]: item["personalization"]["personalization_delta"] for item in result}


EYE_1MIN = task("MT-EYE-002", 1, ["home", "school", "study_space"])
EYE_2MIN = task("MT-EYE-004", 2, ["home", "school", "study_space"])
SLEEP_5MIN = task("MT-SLEEP-904", 5, ["bedroom"])
CANDIDATES = [EYE_1MIN, EYE_2MIN, SLEEP_5MIN]


class TestUserConstraintChannel:
    def test_exceeding_constraint_pushes_task_down(self):
        """P3「≤5 分钟」：10 分钟任务被负向调整、1 分钟任务正向调整。"""
        long_task = task("MT-BREAK-003", 10, ["home", "school"])
        memories = [memory("m1", "user_constraint", {"preferred_max_task_minutes": 5})]

        result = deltas([long_task, EYE_1MIN], memories)

        assert result["MT-BREAK-003"] == -2
        assert result["MT-EYE-002"] == 2
        ordered = [item["task_id"] for item in personalize_task_candidates([long_task, EYE_1MIN], memories)]
        assert ordered == ["MT-EYE-002", "MT-BREAK-003"]

    def test_matching_constraint_is_positive_even_when_domain_preferences_miss(self):
        """候选与问卷偏好任务域不相交时，约束仍提供排序通道。"""
        memories = [
            memory("m-prefer", "task_preference", {"preference": "prefer_task"}, task_id="MT-BREAK-003"),
            memory("m-constraint", "user_constraint", {"preferred_max_task_minutes": 5}),
        ]

        result = deltas(CANDIDATES, memories)

        # prefer MT-BREAK-003 不在候选中（delta 0）；约束对全部候选生效
        assert result["MT-EYE-002"] == 2
        assert result["MT-EYE-004"] == 2
        assert result["MT-SLEEP-904"] == 2
        # 全部等分：不强行制造差异，保持 Basic 顺序
        assert order(CANDIDATES) == [t["task_id"] for t in CANDIDATES]


class TestContextPreferenceChannel:
    def test_matching_context_scores_positive_and_reorders(self):
        memories = [memory("m1", "context_preference", {"preferred_context": "home"})]

        result = personalize_task_candidates([SLEEP_5MIN, EYE_1MIN], memories)

        by_id = {item["task_id"]: item for item in result}
        assert by_id["MT-EYE-002"]["personalization"]["personalization_delta"] == 1
        assert by_id["MT-SLEEP-904"]["personalization"]["personalization_delta"] == 0
        assert by_id["MT-EYE-002"]["personalization"]["reason_codes"] == ["context_match_task"]
        assert [item["task_id"] for item in result] == ["MT-EYE-002", "MT-SLEEP-904"]

    def test_non_matching_context_scores_zero_without_penalty(self):
        memories = [memory("m1", "context_preference", {"preferred_context": "outdoor"})]

        result = deltas(CANDIDATES, memories)

        assert all(delta == 0 for delta in result.values())


class TestScoringIntegrates:
    def test_channels_combine_and_clamp_at_five(self):
        memories = [
            memory("m-c", "user_constraint", {"preferred_max_task_minutes": 5}),
            memory("m-x", "context_preference", {"preferred_context": "home"}),
            memory("m-p", "task_preference", {"preference": "prefer_task"}, task_id="MT-EYE-002"),
        ]

        result = deltas([EYE_1MIN], memories)

        # 2 + 1 + 3 = 6 → clamp 5
        assert result["MT-EYE-002"] == 5

    def test_candidate_set_invariance_holds_with_new_channels(self):
        memories = [
            memory("m1", "user_constraint", {"preferred_max_task_minutes": 2}),
            memory("m2", "context_preference", {"preferred_context": "bedroom"}),
        ]

        result = personalize_task_candidates(CANDIDATES, memories)

        assert {item["task_id"] for item in result} == {t["task_id"] for t in CANDIDATES}

    def test_avoided_long_rest_task_still_ranks_below(self):
        """P3 的 long_rest 回避：候选中出现 MT-BREAK-001（远眺 10 分钟）时被双重压低。"""
        far_view_10min = task("MT-BREAK-001", 10, ["home", "school"])
        memories = [
            memory("m-avoid", "task_preference", {"preference": "avoid_task"}, task_id="MT-BREAK-001"),
            memory("m-c", "user_constraint", {"preferred_max_task_minutes": 5}),
        ]

        ordered = [item["task_id"] for item in personalize_task_candidates([far_view_10min, EYE_1MIN], memories)]

        assert ordered == ["MT-EYE-002", "MT-BREAK-001"]


class FakeHistoryClient:
    def __init__(self, docs):
        self.docs = docs

    def search(self, *, index, size, query, sort=None, source_excludes=None):
        terms = {}
        for item in query.get("bool", {}).get("filter", []):
            terms.update(item.get("term", {}))
        hits = [
            {"_source": dict(document)}
            for document in self.docs
            if all(document.get(key) == value for key, value in terms.items())
        ]
        return {"hits": {"hits": hits[:size]}}


class TestFullHistoryInput:
    def test_merge_appends_memories_missing_from_retrieval_topk(self):
        retrieved = [memory("m1", "user_constraint", {"preferred_max_task_minutes": 5})]
        stored = [
            memory("m1", "user_constraint", {"preferred_max_task_minutes": 5}),
            memory("m2", "context_preference", {"preferred_context": "home"}),
            memory("m3", "task_preference", {"preference": "prefer_task"}, task_id="MT-EYE-002"),
            memory("m4", "task_preference", {"preference": "prefer_task"}, task_id="MT-EYE-002"),
            memory("m5", "task_preference", {"preference": "prefer_task"}, task_id="MT-EYE-002"),
            memory("m6", "task_preference", {"preference": "prefer_task"}, task_id="MT-EYE-002"),
            memory("m7", "task_preference", {"preference": "prefer_task"}, task_id="MT-EYE-002"),
        ]

        merged = merge_full_memory_history(FakeHistoryClient(stored), "u-1", retrieved)

        assert [m["memory_id"] for m in merged] == ["m1", "m2", "m3", "m4", "m5", "m6", "m7"]
        # m6/m7 在检索 top-5 之外，但打分必须看到它们
        result = personalize_task_candidates([EYE_1MIN], merged)
        used = result[0]["personalization"]["memory_ids"]
        assert {"m3", "m4", "m5", "m6", "m7"} <= set(used)

    def test_merge_with_empty_retrieval_uses_full_history(self):
        stored = [memory("m2", "context_preference", {"preferred_context": "home"})]

        merged = merge_full_memory_history(FakeHistoryClient(stored), "u-1", [])

        assert merged == stored
