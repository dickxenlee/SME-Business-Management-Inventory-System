from datetime import date, datetime

from django.test import SimpleTestCase, override_settings
from django.utils import timezone

from reports.services import resolve_period


@override_settings(TIME_ZONE="Asia/Kuala_Lumpur", USE_TZ=True)
class ReportPeriodTests(SimpleTestCase):
    def test_today_uses_local_half_open_calendar_bounds(self):
        period = resolve_period("today", today=date(2026, 8, 14))

        self.assertEqual(period.key, "today")
        self.assertEqual(period.start_date, date(2026, 8, 14))
        self.assertEqual(period.end_date, date(2026, 8, 14))
        self.assertEqual(
            timezone.localtime(period.start_at),
            datetime(2026, 8, 14, 0, 0, tzinfo=timezone.get_current_timezone()),
        )
        self.assertEqual(
            timezone.localtime(period.end_at),
            datetime(2026, 8, 15, 0, 0, tzinfo=timezone.get_current_timezone()),
        )

    def test_seven_day_period_includes_today_and_six_previous_days(self):
        period = resolve_period("7d", today=date(2026, 8, 14))

        self.assertEqual(period.start_date, date(2026, 8, 8))
        self.assertEqual(period.end_date, date(2026, 8, 14))
        self.assertEqual(period.day_count, 7)

    def test_thirty_day_period_includes_at_most_thirty_daily_points(self):
        period = resolve_period("30d", today=date(2026, 8, 14))

        self.assertEqual(period.start_date, date(2026, 7, 16))
        self.assertEqual(period.end_date, date(2026, 8, 14))
        self.assertEqual(period.day_count, 30)

    def test_missing_or_invalid_period_falls_back_to_thirty_days(self):
        for value in (None, "", "year", "7D"):
            with self.subTest(value=value):
                period = resolve_period(value, today=date(2026, 8, 14))
                self.assertEqual(period.key, "30d")
                self.assertEqual(period.day_count, 30)
