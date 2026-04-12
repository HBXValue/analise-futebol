from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse


class HomeViewTests(TestCase):
    def test_home_requires_authentication(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response.url)

    def test_home_is_available_for_logged_in_users(self):
        user = get_user_model().objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="admin12345",
        )
        self.client.force_login(user)
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cadastro global de futebol")
