from django.test import Client, TestCase
from django.utils import timezone

from core.models import Word


class ApiRegressionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.word1 = Word.objects.create(
            word="abandon",
            phonetic="/əˈbændən/",
            pos="v.",
            meaning="放弃；抛弃",
            example="Never abandon hope.",
            example_cn="永远不要放弃希望。",
            synonyms=["desert"],
            freq_read=30,
            freq_listen=10,
            freq_translate=15,
            freq_write=12,
            difficulty=3,
        )
        cls.word2 = Word.objects.create(
            word="ability",
            phonetic="/əˈbɪləti/",
            pos="n.",
            meaning="能力；才能",
            example="She has the ability to lead.",
            example_cn="她有领导能力。",
            synonyms=["capacity"],
            freq_read=25,
            freq_listen=12,
            freq_translate=18,
            freq_write=20,
            difficulty=2,
        )

    def setUp(self):
        self.client = Client()

    def post(self, path, payload, token=None):
        headers = {"HTTP_AUTHORIZATION": "Bearer " + token} if token else {}
        return self.client.post(
            path,
            data=payload,
            content_type="application/json",
            **headers,
        )

    def register(self):
        response = self.post(
            "/api/auth/register",
            {"username": "test_user", "password": "pass1234", "nickname": "Test"},
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["access_token"]

    def test_api_smoke_without_external_llm(self):
        from unittest.mock import patch

        with patch("core.views.llm.is_configured", return_value=False):
            token = self.register()
            self.assertEqual(self.client.get("/api/health").status_code, 200)
            self.assertEqual(self.client.get("/api").status_code, 200)
            self.assertEqual(
                self.client.get("/api/auth/me", HTTP_AUTHORIZATION="Bearer " + token).status_code,
                200,
            )
            self.assertEqual(
                self.client.get("/api/words/today", HTTP_AUTHORIZATION="Bearer " + token).status_code,
                200,
            )
            self.assertEqual(
                self.client.get("/api/words?page=1&size=10", HTTP_AUTHORIZATION="Bearer " + token).status_code,
                200,
            )
            self.assertEqual(
                self.client.get("/api/words/lookup?word=abandon", HTTP_AUTHORIZATION="Bearer " + token).status_code,
                200,
            )
            self.assertEqual(
                self.post(
                    "/api/records",
                    {
                        "word_id": self.word1.pk,
                        "quality": 4,
                        "review_type": "learn",
                        "topic": "read",
                        "is_correct": True,
                    },
                    token,
                ).status_code,
                200,
            )
            for path in (
                "/api/stats/summary",
                "/api/plan/daily",
                "/api/notebook/wrong",
                "/api/notebook/stubborn",
                "/api/notebook/summary",
            ):
                self.assertEqual(
                    self.client.get(path, HTTP_AUTHORIZATION="Bearer " + token).status_code,
                    200,
                    path,
                )
            for path, payload in (
                ("/api/ai/example", {"word_id": self.word1.pk}),
                ("/api/agents/plan", {}),
                ("/api/agents/tutor", {"word_id": self.word1.pk}),
                ("/api/agents/train", {"topic": "read", "count": 2}),
                ("/api/agents/analyze", {"word_id": self.word1.pk}),
            ):
                self.assertEqual(self.post(path, payload, token).status_code, 200, path)

    def test_invalid_parameters_return_400_not_500(self):
        token = self.register()
        cases = (
            ("/api/words/today?limit=bad", "get", None),
            ("/api/words?topic=invalid", "get", None),
            ("/api/words?learned=bad", "get", None),
            ("/api/notebook/wrong?limit=bad", "get", None),
            ("/api/records", "post", {"word_id": "bad"}),
            ("/api/records", "post", {"word_id": self.word1.pk, "quality": "bad"}),
            ("/api/records/sync", "post", {"records": "bad"}),
            ("/api/ai/example", "post", {"word_id": "bad"}),
            ("/api/agents/tutor", "post", {"word_id": "bad"}),
            ("/api/agents/analyze", "post", {"word_id": "bad"}),
            ("/api/agents/train", "post", {"count": "bad"}),
        )
        for path, method, payload in cases:
            if method == "get":
                response = self.client.get(path, HTTP_AUTHORIZATION="Bearer " + token)
            else:
                response = self.post(path, payload, token)
            self.assertEqual(response.status_code, 400, (path, response.content))

    def test_plan_progress_does_not_go_backwards(self):
        token = self.register()
        today = timezone.localdate().isoformat()
        initial = self.client.get(
            "/api/plan/daily?date=" + today,
            HTTP_AUTHORIZATION="Bearer " + token,
        ).json()
        self.assertGreaterEqual(initial["total"], 1)
        self.assertEqual(initial["completed"], 0)

        first_word_id = initial["learn_new"][0]["word"]["id"]
        response = self.post(
            "/api/records",
            {"word_id": first_word_id, "quality": 4, "review_type": "learn", "is_correct": True},
            token,
        )
        self.assertEqual(response.status_code, 200, response.content)

        after = self.client.get(
            "/api/plan/daily?date=" + today,
            HTTP_AUTHORIZATION="Bearer " + token,
        ).json()
        self.assertEqual(after["completed"], 1)
        self.assertEqual(after["total"], initial["total"])
        self.assertGreater(after["progress"], 0)
