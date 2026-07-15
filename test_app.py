import unittest

import app


class ShortenApiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.init_db()
        app.app.config["TESTING"] = True
        cls.client = app.app.test_client()

    def test_shorten_endpoint_creates_short_url_and_redirects(self):
        response = self.client.post(
            "/shorten",
            json={
                "url": "https://example.com",
                "category": "general"
            }
        )

        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        self.assertIn("short_url", data)
        self.assertIn("code", data)
        self.assertTrue(data["short_url"].startswith("http://localhost/"))

        redirect_response = self.client.get(f"/{data['code']}", follow_redirects=False)

        self.assertEqual(redirect_response.status_code, 302)
        self.assertEqual(redirect_response.location, "https://example.com")

    def test_shorten_endpoint_normalizes_url_without_scheme(self):
        response = self.client.post(
            "/shorten",
            json={
                "url": "example.com",
                "category": "general"
            }
        )

        self.assertEqual(response.status_code, 200)

        data = response.get_json()
        redirect_response = self.client.get(f"/{data['code']}", follow_redirects=False)

        self.assertEqual(redirect_response.status_code, 302)
        self.assertEqual(redirect_response.location, "https://example.com")


if __name__ == "__main__":
    unittest.main()
