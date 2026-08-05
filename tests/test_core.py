from __future__ import annotations

import smtplib
import unittest
from unittest.mock import patch

import requests

from src.email_delivery import (
    DEFAULT_EMAIL,
    SMTPSettings,
    build_email_message,
    send_email,
)
from src.openrouter_client import (
    MAX_FREE_FALLBACK_MODELS,
    _friendly_error_message,
    _parse_json_content,
    _parse_or_repair_content,
    _request_with_recovery,
    analyze_with_openrouter,
    build_fallback_insights,
)
from src.preprocess import normalize_url, preprocess_items
from src.report_builder import build_email_html
from src.sample_data import build_sample_items, is_sample_url


class PreprocessTests(unittest.TestCase):
    def test_tracking_parameters_are_removed(self) -> None:
        normalized = normalize_url(
            "HTTPS://Example.com/news/?utm_source=mail&id=10#section"
        )
        self.assertEqual(normalized, "https://example.com/news?id=10")

    def test_sample_duplicate_is_removed(self) -> None:
        clean_items, duplicate_count, excluded_count = preprocess_items(
            build_sample_items()
        )
        self.assertEqual(len(clean_items), 9)
        self.assertEqual(duplicate_count, 1)
        self.assertEqual(excluded_count, 0)

    def test_only_reserved_demo_domain_is_sample_url(self) -> None:
        self.assertTrue(is_sample_url("https://example.com/news/item"))
        self.assertFalse(is_sample_url("https://openai.com/news/item"))


class InsightTests(unittest.TestCase):
    def test_openrouter_fallback_model_limit(self) -> None:
        self.assertEqual(MAX_FREE_FALLBACK_MODELS, 3)

    def test_fallback_insight_matches_schema(self) -> None:
        clean_items, _, _ = preprocess_items(build_sample_items())
        insights = build_fallback_insights(clean_items[:2])
        self.assertEqual(len(insights), 2)
        self.assertTrue(all(0 <= item.importance_score <= 100 for item in insights))
        self.assertTrue(all(item.summary for item in insights))
        self.assertTrue(all(item.work_relevance for item in insights))

    @patch("src.openrouter_client.time.sleep")
    @patch("src.openrouter_client._request_completion")
    def test_rate_limit_switches_to_another_free_model(
        self,
        request_mock,
        sleep_mock,
    ) -> None:
        request_mock.side_effect = [
            FakeResponse(429, headers={"Retry-After": "1"}),
            FakeResponse(200),
        ]
        response, warnings = _request_with_recovery(
            headers={"Authorization": "Bearer test"},
            payload={"model": "openrouter/free", "messages": []},
            timeout_seconds=5,
            fallback_models=[
                "example/free-model-a:free",
                "example2/free-model-b:free",
            ],
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("자동 전환", warnings[0])
        second_payload = request_mock.call_args_list[1].args[1]
        self.assertEqual(second_payload["model"], "example/free-model-a:free")
        sleep_mock.assert_called_once_with(1.0)

    @patch("src.openrouter_client._request_completion")
    def test_timeout_switches_model_and_reports_progress(
        self,
        request_mock,
    ) -> None:
        request_mock.side_effect = [
            requests.Timeout("slow"),
            FakeResponse(200),
        ]
        status_messages = []
        response, warnings = _request_with_recovery(
            headers={"Authorization": "Bearer test"},
            payload={"model": "openrouter/free", "messages": []},
            timeout_seconds=5,
            fallback_models=["example/free-model-a:free"],
            status_callback=status_messages.append,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("응답 대기 중 (1/2)", status_messages[0])
        self.assertTrue(any("자동 전환" in message for message in status_messages))
        self.assertTrue(any("example/free-model-a:free" in warning for warning in warnings))

    def test_rate_limit_error_is_user_friendly(self) -> None:
        response = FakeResponse(
            429,
            payload={"error": {"message": "provider raw details"}},
        )
        message = _friendly_error_message(response)
        self.assertIn("공용 호출 한도", message)
        self.assertNotIn("provider raw details", message)

    def test_multiple_json_objects_are_merged(self) -> None:
        parsed = _parse_json_content(
            '{"id":"one","summary":"first"}\n'
            '{"id":"two","summary":"second"}'
        )
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]["id"], "one")
        self.assertEqual(parsed[1]["id"], "two")

    def test_multiple_items_wrappers_are_merged(self) -> None:
        parsed = _parse_json_content(
            '{"items":[{"id":"one"}]}\n'
            '{"items":[{"id":"two"}]}'
        )
        self.assertEqual([item["id"] for item in parsed], ["one", "two"])

    @patch("src.openrouter_client._request_with_recovery")
    def test_plain_text_response_is_repaired_once(self, request_mock) -> None:
        request_mock.return_value = (
            FakeResponse(
                200,
                payload={
                    "choices": [
                        {
                            "message": {
                                "content": '{"items":[{"id":"one"}]}',
                            }
                        }
                    ]
                },
            ),
            [],
        )
        status_messages = []

        parsed, warnings = _parse_or_repair_content(
            content="분석을 완료했습니다. 결과는 다음과 같습니다.",
            headers={"Authorization": "Bearer test"},
            model="example/free-model:free",
            original_prompt="기사 one을 분석하세요.",
            timeout_seconds=5,
            status_callback=status_messages.append,
        )

        self.assertEqual(parsed["items"][0]["id"], "one")
        self.assertIn("자동 복구", warnings[0])
        self.assertTrue(any("JSON 형식" in message for message in status_messages))
        request_mock.assert_called_once()
        repair_payload = request_mock.call_args.args[1]
        self.assertEqual(
            repair_payload["response_format"]["type"],
            "json_schema",
        )
        self.assertEqual(
            repair_payload["plugins"],
            [{"id": "response-healing"}],
        )
        self.assertTrue(repair_payload["provider"]["require_parameters"])

    @patch("src.openrouter_client._request_with_recovery")
    def test_failed_json_repair_has_friendly_error(self, request_mock) -> None:
        request_mock.return_value = (
            FakeResponse(
                200,
                payload={
                    "choices": [
                        {"message": {"content": "여전히 일반 설명문입니다."}}
                    ]
                },
            ),
            [],
        )

        with self.assertRaisesRegex(RuntimeError, "백업 결과 사용"):
            _parse_or_repair_content(
                content="일반 설명문입니다.",
                headers={"Authorization": "Bearer test"},
                model="example/free-model:free",
                original_prompt="기사 one을 분석하세요.",
                timeout_seconds=5,
            )
        request_mock.assert_called_once()

    @patch(
        "src.openrouter_client._fetch_free_fallback_models",
        return_value=[],
    )
    @patch("src.openrouter_client._request_with_recovery")
    def test_string_item_is_skipped_and_missing_article_is_filled(
        self,
        request_mock,
        _fetch_mock,
    ) -> None:
        clean_items, _, _ = preprocess_items(build_sample_items())
        first_item = clean_items[0]
        request_mock.return_value = (
            FakeResponse(
                200,
                payload={
                    "model": "example/free-model:free",
                    "choices": [
                        {
                            "message": {
                                "content": (
                                    '{"items":["분석 결과",'
                                    f'{{"id":"{first_item.id}",'
                                    '"summary":"정상 요약"}]}'
                                ),
                            }
                        }
                    ],
                },
            ),
            [],
        )

        insights, _, warnings = analyze_with_openrouter(
            clean_items[:2],
            api_key="test-key",
            model="example/free-model:free",
            timeout_seconds=5,
        )

        self.assertEqual(len(insights), 2)
        self.assertTrue(any("JSON 객체가 아니어서 제외" in warning for warning in warnings))
        self.assertTrue(any("누락된 1건" in warning for warning in warnings))
        request_payload = request_mock.call_args.args[1]
        self.assertEqual(request_payload["response_format"]["type"], "json_schema")
        self.assertEqual(request_payload["plugins"], [{"id": "response-healing"}])
        self.assertTrue(request_payload["provider"]["require_parameters"])


class EmailTests(unittest.TestCase):
    def test_default_sender_and_recipient_are_same(self) -> None:
        message = build_email_message(
            sender=DEFAULT_EMAIL,
            recipient=DEFAULT_EMAIL,
            subject="[Daily Insight] Test",
            html_body="<p>test</p>",
            attachments=[],
        )
        self.assertEqual(message["From"], "jongeunshin95@kbfg.com")
        self.assertEqual(message["To"], "jongeunshin95@kbfg.com")
        self.assertTrue(message.is_multipart())

    def test_sample_item_has_no_clickable_original_link(self) -> None:
        insight = build_fallback_insights(
            preprocess_items(build_sample_items())[0][:1]
        )
        html_body = build_email_html(
            insight,
            metrics={"raw_count": 1, "clean_count": 1},
            date_display="2026.08.05",
        )
        self.assertIn("샘플 데이터 · 실제 원문 없음", html_body)
        self.assertNotIn('href="https://example.com', html_body)

    @patch(
        "src.email_delivery.smtplib.SMTP",
        side_effect=smtplib.SMTPServerDisconnected(
            "Connection unexpectedly closed: reset by peer"
        ),
    )
    def test_smtp_disconnect_has_network_guidance(self, _smtp_mock) -> None:
        with self.assertRaisesRegex(RuntimeError, "외부 SMTP 포트"):
            send_email(
                settings=SMTPSettings(
                    host="smtp.gmail.com",
                    port=587,
                    username="sender@gmail.com",
                    password="test-app-password",
                    security="starttls",
                ),
                sender="sender@gmail.com",
                recipient=DEFAULT_EMAIL,
                subject="test",
                html_body="<p>test</p>",
                attachments=[],
            )


class FakeResponse:
    def __init__(
        self,
        status_code: int,
        headers=None,
        payload=None,
    ) -> None:
        self.status_code = status_code
        self.ok = 200 <= status_code < 300
        self.headers = headers or {}
        self._payload = payload or {}
        self.text = str(self._payload)

    def json(self):
        return self._payload


if __name__ == "__main__":
    unittest.main()
