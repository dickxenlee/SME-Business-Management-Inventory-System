import json
import os
import subprocess
import sys
from pathlib import Path

from django.test import SimpleTestCase


PROJECT_ROOT = Path(__file__).resolve().parents[2]


class ProductionSettingsTests(SimpleTestCase):
    def run_settings_probe(self, **overrides):
        environment = os.environ.copy()
        environment.update(
            {
                "DJANGO_SETTINGS_MODULE": "sme_manager.settings",
                "DJANGO_ENVIRONMENT": "production",
                "DJANGO_SECRET_KEY": (
                    "ci-only-production-secret-"
                    "9f8e7d6c5b4a3210-secure-validation-value"
                ),
                "DJANGO_DEBUG": "True",
                "DJANGO_ALLOWED_HOSTS": "app.example.com,www.example.com",
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://app.example.com",
                "DJANGO_TRUST_PROXY_SSL_HEADER": "False",
                "DJANGO_SECURE_HSTS_SECONDS": "0",
                "DJANGO_LOG_LEVEL": "INFO",
                "DB_NAME": "ci_database",
                "DB_USER": "ci_user",
                "DB_PASSWORD": "ci-password-placeholder",
                "DB_HOST": "database.example.com",
                "DB_PORT": "5432",
                "DB_SSLMODE": "require",
                "DB_CONNECT_TIMEOUT": "5",
                "DB_CONN_MAX_AGE": "60",
                "INVOICE_SELLER_NAME": "CI Example Business",
                "INVOICE_SELLER_ADDRESS": "CI Example Address",
            }
        )
        environment.update(overrides)
        script = """
import json
from django.conf import settings

print(json.dumps({
    "environment": settings.DJANGO_ENVIRONMENT,
    "debug": settings.DEBUG,
    "allowed_hosts": settings.ALLOWED_HOSTS,
    "csrf_origins": settings.CSRF_TRUSTED_ORIGINS,
    "session_secure": settings.SESSION_COOKIE_SECURE,
    "csrf_secure": settings.CSRF_COOKIE_SECURE,
    "ssl_redirect": settings.SECURE_SSL_REDIRECT,
    "redirect_exempt": settings.SECURE_REDIRECT_EXEMPT,
    "axes_enabled": settings.AXES_ENABLED,
    "axes_failure_limit": settings.AXES_FAILURE_LIMIT,
    "axes_lockout_parameters": settings.AXES_LOCKOUT_PARAMETERS,
    "axes_ip_precedence": settings.AXES_IPWARE_META_PRECEDENCE_ORDER,
    "hsts_seconds": settings.SECURE_HSTS_SECONDS,
    "hsts_subdomains": settings.SECURE_HSTS_INCLUDE_SUBDOMAINS,
    "hsts_preload": settings.SECURE_HSTS_PRELOAD,
    "proxy_header": settings.SECURE_PROXY_SSL_HEADER,
    "conn_max_age": settings.DATABASES["default"]["CONN_MAX_AGE"],
    "conn_health_checks": settings.DATABASES["default"]["CONN_HEALTH_CHECKS"],
    "database_options": settings.DATABASES["default"]["OPTIONS"],
    "static_backend": settings.STORAGES["staticfiles"]["BACKEND"],
    "middleware": settings.MIDDLEWARE,
}))
"""
        return subprocess.run(
            [sys.executable, "-c", script],
            cwd=PROJECT_ROOT,
            env=environment,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_production_enables_security_without_implicitly_trusting_proxy(self):
        result = self.run_settings_probe()

        self.assertEqual(result.returncode, 0, result.stderr)
        settings_data = json.loads(result.stdout)
        self.assertEqual(settings_data["environment"], "production")
        self.assertIs(settings_data["debug"], False)
        self.assertEqual(
            settings_data["allowed_hosts"],
            ["app.example.com", "www.example.com"],
        )
        self.assertEqual(
            settings_data["csrf_origins"], ["https://app.example.com"]
        )
        self.assertIs(settings_data["session_secure"], True)
        self.assertIs(settings_data["csrf_secure"], True)
        self.assertIs(settings_data["ssl_redirect"], True)
        self.assertEqual(settings_data["hsts_seconds"], 0)
        self.assertIs(settings_data["hsts_subdomains"], False)
        self.assertIs(settings_data["hsts_preload"], False)
        self.assertIsNone(settings_data["proxy_header"])

    def test_production_uses_postgresql_connection_and_static_options(self):
        result = self.run_settings_probe()

        self.assertEqual(result.returncode, 0, result.stderr)
        settings_data = json.loads(result.stdout)
        self.assertEqual(settings_data["conn_max_age"], 60)
        self.assertIs(settings_data["conn_health_checks"], True)
        self.assertEqual(
            settings_data["database_options"],
            {"connect_timeout": 5, "sslmode": "require"},
        )
        self.assertEqual(
            settings_data["static_backend"],
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )
        middleware = settings_data["middleware"]
        self.assertEqual(
            middleware[middleware.index("django.middleware.security.SecurityMiddleware") + 1],
            "whitenoise.middleware.WhiteNoiseMiddleware",
        )

    def test_proxy_header_requires_explicit_trust(self):
        result = self.run_settings_probe(DJANGO_TRUST_PROXY_SSL_HEADER="True")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["proxy_header"],
            ["HTTP_X_FORWARDED_PROTO", "https"],
        )

    def test_production_ssl_redirect_cannot_be_disabled_by_environment(self):
        result = self.run_settings_probe(DJANGO_SECURE_SSL_REDIRECT="False")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIs(json.loads(result.stdout)["ssl_redirect"], True)

    def test_only_the_health_path_is_exempt_from_the_ssl_redirect(self):
        result = self.run_settings_probe()

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["redirect_exempt"],
            ["^health/$"],
        )

    def test_login_lockout_is_enabled_and_scoped_to_username_and_address(self):
        result = self.run_settings_probe()

        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertIs(data["axes_enabled"], True)
        self.assertEqual(data["axes_failure_limit"], 5)
        self.assertEqual(
            data["axes_lockout_parameters"], [["username", "ip_address"]]
        )

    def test_forwarded_client_ip_is_only_trusted_behind_a_trusted_proxy(self):
        untrusted = json.loads(
            self.run_settings_probe(
                DJANGO_TRUST_PROXY_SSL_HEADER="False"
            ).stdout
        )
        trusted = json.loads(
            self.run_settings_probe(
                DJANGO_TRUST_PROXY_SSL_HEADER="True"
            ).stdout
        )

        # Reading a spoofable header without a trusted proxy in front would let
        # an attacker sidestep the lockout by forging X-Forwarded-For.
        self.assertEqual(untrusted["axes_ip_precedence"], ["REMOTE_ADDR"])
        self.assertEqual(
            trusted["axes_ip_precedence"],
            ["HTTP_X_FORWARDED_FOR", "REMOTE_ADDR"],
        )

    def test_hsts_seconds_are_environment_controlled(self):
        result = self.run_settings_probe(DJANGO_SECURE_HSTS_SECONDS="3600")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["hsts_seconds"], 3600)

    def test_development_keeps_local_http_defaults(self):
        result = self.run_settings_probe(
            DJANGO_ENVIRONMENT="development",
            DJANGO_DEBUG="True",
            DJANGO_ALLOWED_HOSTS="localhost,127.0.0.1",
            DJANGO_CSRF_TRUSTED_ORIGINS="",
            DB_SSLMODE="",
            DB_CONN_MAX_AGE="0",
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        settings_data = json.loads(result.stdout)
        self.assertIs(settings_data["debug"], True)
        self.assertIs(settings_data["session_secure"], False)
        self.assertIs(settings_data["csrf_secure"], False)
        self.assertIs(settings_data["ssl_redirect"], False)
        self.assertEqual(settings_data["hsts_seconds"], 0)
        self.assertEqual(settings_data["conn_max_age"], 0)
        self.assertIs(settings_data["conn_health_checks"], False)
        self.assertEqual(settings_data["database_options"], {"connect_timeout": 5})
        self.assertEqual(
            settings_data["static_backend"],
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )

    def test_missing_production_values_fail_without_echoing_secret(self):
        cases = {
            "secret": {"DJANGO_SECRET_KEY": ""},
            "placeholder secret": {
                "DJANGO_SECRET_KEY": "replace-with-a-long-random-secret-key"
            },
            "allowed hosts": {"DJANGO_ALLOWED_HOSTS": ""},
            "csrf origins": {"DJANGO_CSRF_TRUSTED_ORIGINS": ""},
        }

        for label, overrides in cases.items():
            with self.subTest(label=label):
                result = self.run_settings_probe(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ImproperlyConfigured", result.stderr)
                self.assertNotIn("ci-only-production-secret", result.stderr)

    def test_invalid_environment_values_fail_clearly(self):
        cases = {
            "environment": {"DJANGO_ENVIRONMENT": "live"},
            "boolean": {"DJANGO_TRUST_PROXY_SSL_HEADER": "sometimes"},
            "hsts": {"DJANGO_SECURE_HSTS_SECONDS": "tomorrow"},
            "connection age": {"DB_CONN_MAX_AGE": "later"},
            "missing production ssl mode": {"DB_SSLMODE": ""},
            "plaintext production ssl mode": {"DB_SSLMODE": "disable"},
            "downgradable production ssl mode": {"DB_SSLMODE": "prefer"},
            "ssl mode": {"DB_SSLMODE": "encrypted-ish"},
            "host containing scheme": {
                "DJANGO_ALLOWED_HOSTS": "https://app.example.com"
            },
            "wildcard host": {"DJANGO_ALLOWED_HOSTS": "*.example.com"},
            "insecure csrf origin": {
                "DJANGO_CSRF_TRUSTED_ORIGINS": "http://app.example.com"
            },
            "csrf origin containing path": {
                "DJANGO_CSRF_TRUSTED_ORIGINS": "https://app.example.com/path"
            },
        }

        for label, overrides in cases.items():
            with self.subTest(label=label):
                result = self.run_settings_probe(**overrides)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("ImproperlyConfigured", result.stderr)
