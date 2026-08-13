from django.contrib.auth.models import Group
from django.test import TestCase


class StaffRoleMigrationTests(TestCase):
    def test_staff_group_exists(self):
        self.assertTrue(Group.objects.filter(name="Staff").exists())

