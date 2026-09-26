from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse


def sign_in(client, username, password):
    """Sign in through the real form.

    Client.login() calls authenticate() without a request, which the Axes
    backend refuses, so the only way to exercise a sign-in is to post the form
    the way a person would.
    """
    client.post(
        reverse("core:login"), {"username": username, "password": password}
    )
    return "_auth_user_id" in client.session


class StaffAccessControlTests(TestCase):
    """Staff administration belongs to the owner, not the shop floor."""

    @classmethod
    def setUpTestData(cls):
        staff_group, _ = Group.objects.get_or_create(name="Staff")
        cls.owner = get_user_model().objects.create_superuser(
            username="owner", password="test-password-123", email="owner@example.com"
        )
        cls.shop_staff = get_user_model().objects.create_user(
            username="shopfloor", password="test-password-123"
        )
        cls.shop_staff.groups.add(staff_group)

    def test_staff_cannot_reach_the_accounts_screen(self):
        self.client.force_login(self.shop_staff)

        for name, args in [
            ("core:staff_list", []),
            ("core:staff_create", []),
            ("core:staff_set_password", [self.owner.pk]),
        ]:
            with self.subTest(view=name):
                response = self.client.get(reverse(name, args=args))
                self.assertEqual(response.status_code, 403)

    def test_staff_cannot_suspend_anyone(self):
        self.client.force_login(self.shop_staff)

        response = self.client.post(
            reverse("core:staff_toggle_access", args=[self.owner.pk])
        )

        self.assertEqual(response.status_code, 403)
        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)

    def test_anonymous_visitors_are_sent_to_sign_in(self):
        response = self.client.get(reverse("core:staff_list"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("core:login"), response["Location"])


class StaffCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Group.objects.get_or_create(name="Staff")
        cls.owner = get_user_model().objects.create_superuser(
            username="owner", password="test-password-123", email="owner@example.com"
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def create(self, **overrides):
        data = {
            "username": "newhire",
            "email": "newhire@example.com",
            "password1": "shop-floor-pass-9182",
            "password2": "shop-floor-pass-9182",
        }
        data.update(overrides)
        return self.client.post(reverse("core:staff_create"), data)

    def test_a_new_account_joins_staff_and_stays_out_of_django_admin(self):
        self.create()

        user = get_user_model().objects.get(username="newhire")
        self.assertTrue(user.groups.filter(name="Staff").exists())
        self.assertTrue(user.is_active)
        # is_staff gates Django admin, which shop staff must never reach.
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_the_new_account_can_actually_sign_in(self):
        self.create()
        self.client.logout()

        self.assertTrue(
            sign_in(self.client, "newhire", "shop-floor-pass-9182")
        )

    def test_email_is_required_so_the_account_can_self_recover(self):
        response = self.create(email="")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="newhire").exists())

    def test_a_duplicate_email_is_rejected(self):
        self.create()

        response = self.create(username="another", email="newhire@example.com")

        self.assertContains(response, "already uses this email")
        self.assertFalse(get_user_model().objects.filter(username="another").exists())

    def test_a_weak_password_is_refused(self):
        response = self.create(password1="password", password2="password")

        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(username="newhire").exists())


class LockoutProtectionTests(TestCase):
    """Nobody may leave the shop with no way back in."""

    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username="owner", password="test-password-123", email="owner@example.com"
        )
        cls.other = get_user_model().objects.create_user(
            username="colleague", password="test-password-123"
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def test_an_owner_cannot_remove_their_own_access(self):
        response = self.client.post(
            reverse("core:staff_toggle_access", args=[self.owner.pk]), follow=True
        )

        self.owner.refresh_from_db()
        self.assertTrue(self.owner.is_active)
        self.assertContains(response, "cannot remove your own access")

    def test_an_active_owner_always_remains(self):
        """Suspending every owner is impossible, because only an active owner
        can reach this view and the self-check stops them targeting
        themselves."""
        second_owner = get_user_model().objects.create_superuser(
            username="coowner", password="test-password-123", email="co@example.com"
        )

        self.client.post(
            reverse("core:staff_toggle_access", args=[second_owner.pk])
        )
        self.client.post(
            reverse("core:staff_toggle_access", args=[self.owner.pk])
        )

        self.assertEqual(
            list(
                get_user_model().objects.filter(is_superuser=True, is_active=True)
            ),
            [self.owner],
        )

    def test_suspending_blocks_sign_in_without_deleting_the_account(self):
        self.client.post(
            reverse("core:staff_toggle_access", args=[self.other.pk])
        )

        self.other.refresh_from_db()
        self.assertFalse(self.other.is_active)
        # The row survives, because Sales and stock movements point at it.
        self.assertTrue(get_user_model().objects.filter(pk=self.other.pk).exists())
        self.client.logout()
        self.assertFalse(
            sign_in(self.client, "colleague", "test-password-123")
        )

    def test_access_can_be_restored(self):
        url = reverse("core:staff_toggle_access", args=[self.other.pk])
        self.client.post(url)
        self.client.post(url)

        self.other.refresh_from_db()
        self.assertTrue(self.other.is_active)


class OwnerSetPasswordTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = get_user_model().objects.create_superuser(
            username="owner", password="test-password-123", email="owner@example.com"
        )
        cls.locked_out = get_user_model().objects.create_user(
            username="forgetful", password="old-password-4411"
        )

    def test_an_owner_can_set_a_password_for_someone_locked_out(self):
        self.client.force_login(self.owner)

        self.client.post(
            reverse("core:staff_set_password", args=[self.locked_out.pk]),
            {"new_password1": "brand-new-pass-7733", "new_password2": "brand-new-pass-7733"},
        )

        self.client.logout()
        self.assertTrue(
            sign_in(self.client, "forgetful", "brand-new-pass-7733")
        )


@override_settings(
    PASSWORD_RESET_ENABLED=True,
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="shop@example.com",
)
class PasswordResetFlowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="resetter",
            password="old-password-4411",
            email="resetter@example.com",
        )

    def test_a_reset_email_is_sent_and_the_link_sets_a_new_password(self):
        self.client.post(
            reverse("core:password_reset"), {"email": "resetter@example.com"}
        )

        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        self.assertIn("/accounts/password-reset/", body)

        link = [
            line.strip()
            for line in body.splitlines()
            if "/accounts/password-reset/" in line
        ][0]
        path = link.split("://", 1)[1].split("/", 1)[1]
        follow = self.client.get("/" + path, follow=True)
        self.client.post(
            follow.redirect_chain[-1][0] if follow.redirect_chain else "/" + path,
            {"new_password1": "fresh-password-2244", "new_password2": "fresh-password-2244"},
            follow=True,
        )

        self.client.logout()
        self.assertTrue(
            sign_in(self.client, "resetter", "fresh-password-2244")
        )

    def test_an_unknown_address_is_not_revealed(self):
        """Confirming which addresses exist would leak the staff list."""
        response = self.client.post(
            reverse("core:password_reset"), {"email": "nobody@example.com"}
        )

        self.assertRedirects(response, reverse("core:password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_the_login_page_offers_the_reset_link(self):
        response = self.client.get(reverse("core:login"))

        self.assertContains(response, reverse("core:password_reset"))


@override_settings(PASSWORD_RESET_ENABLED=False)
class PasswordResetDisabledTests(TestCase):
    """With no mail host the flow must be absent, not silently broken."""

    def test_the_reset_page_is_not_reachable(self):
        response = self.client.get(reverse("core:password_reset"))

        self.assertEqual(response.status_code, 404)

    def test_the_login_page_does_not_offer_a_link_that_cannot_work(self):
        response = self.client.get(reverse("core:login"))

        self.assertNotContains(response, "Forgot your password?")
