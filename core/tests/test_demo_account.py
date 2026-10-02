from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from core.demo import DEMO_PASSWORD, DEMO_USERNAME


def make_demo_user(**overrides):
    values = {"username": DEMO_USERNAME, "password": DEMO_PASSWORD}
    values.update(overrides)
    user = get_user_model().objects.create_user(**values)
    group, _ = Group.objects.get_or_create(name="Staff")
    user.groups.add(group)
    return user


class DemoLoginHintTests(TestCase):
    def test_the_login_page_shows_the_demo_login_when_the_account_exists(self):
        make_demo_user()

        response = self.client.get(reverse("core:login"))

        self.assertContains(response, "Try the demo")
        self.assertContains(response, DEMO_USERNAME)
        self.assertContains(response, DEMO_PASSWORD)

    def test_a_site_without_a_demo_account_shows_no_hint(self):
        """A deployment holding real records must not advertise a login."""
        response = self.client.get(reverse("core:login"))

        self.assertNotContains(response, "Try the demo")
        self.assertNotContains(response, DEMO_PASSWORD)

    def test_a_suspended_demo_account_is_not_advertised(self):
        make_demo_user(is_active=False)

        response = self.client.get(reverse("core:login"))

        self.assertNotContains(response, "Try the demo")

    def test_the_published_password_is_short_enough_to_type(self):
        self.assertLessEqual(len(DEMO_PASSWORD), 8)


class DemoPasswordIsFixedTests(TestCase):
    """The password is public, so one visitor must not be able to change it
    and lock every other visitor out."""

    def setUp(self):
        self.demo = make_demo_user()
        self.client.force_login(self.demo)

    def test_the_demo_account_is_turned_away_from_the_password_form(self):
        response = self.client.get(reverse("core:password_change"))

        self.assertRedirects(
            response, reverse("core:home"), fetch_redirect_response=False
        )

    def test_posting_a_new_password_changes_nothing(self):
        self.client.post(
            reverse("core:password_change"),
            {
                "old_password": DEMO_PASSWORD,
                "new_password1": "a-visitor-chose-this-9911",
                "new_password2": "a-visitor-chose-this-9911",
            },
        )

        self.demo.refresh_from_db()
        self.assertTrue(self.demo.check_password(DEMO_PASSWORD))

    def test_other_accounts_can_still_change_their_own_password(self):
        other = get_user_model().objects.create_user(
            username="regular-staff", password="old-password-4411"
        )
        self.client.force_login(other)

        response = self.client.get(reverse("core:password_change"))

        self.assertEqual(response.status_code, 200)


class SeededDemoAccountIsLimitedTests(TestCase):
    """What a stranger holding the published login can and cannot reach."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username="owner", password="owner-password-5521"
        )
        call_command("seed_demo", stdout=StringIO())
        cls.demo = get_user_model().objects.get(username=DEMO_USERNAME)

    def test_it_is_staff_and_not_an_owner(self):
        self.assertTrue(self.demo.groups.filter(name="Staff").exists())
        self.assertFalse(self.demo.is_superuser)
        self.assertFalse(self.demo.is_staff)
        self.assertTrue(self.demo.check_password(DEMO_PASSWORD))

    def test_it_cannot_manage_staff_accounts_or_other_passwords(self):
        self.client.force_login(self.demo)

        pages = [
            reverse("core:staff_list"),
            reverse("core:staff_create"),
            reverse("core:staff_set_password", args=[self.owner.pk]),
        ]
        for url in pages:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    def test_it_cannot_set_another_accounts_password(self):
        self.client.force_login(self.demo)

        response = self.client.post(
            reverse("core:staff_set_password", args=[self.owner.pk]),
            {"new_password1": "hijacked-pass-7733", "new_password2": "hijacked-pass-7733"},
        )

        self.assertEqual(response.status_code, 403)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.check_password("owner-password-5521"))

    def test_it_cannot_suspend_anyone_or_reach_django_admin(self):
        self.client.force_login(self.demo)

        suspend = self.client.post(
            reverse("core:staff_toggle_access", args=[self.owner.pk])
        )
        admin = self.client.get(reverse("admin:index"))

        self.assertEqual(suspend.status_code, 403)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)
        self.assertEqual(admin.status_code, 302)

    def test_reseeding_puts_the_published_password_back(self):
        """Even if an owner changes it by hand, the next reset restores it."""
        self.demo.set_password("changed-by-someone-1188")
        self.demo.save()

        call_command("seed_demo", reset=True, stdout=StringIO())

        self.demo.refresh_from_db()
        self.assertTrue(self.demo.check_password(DEMO_PASSWORD))
        self.assertFalse(self.demo.is_superuser)

    def test_reseeding_keeps_the_owner_account(self):
        call_command("seed_demo", reset=True, stdout=StringIO())

        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_superuser)
        self.assertTrue(self.owner.check_password("owner-password-5521"))
