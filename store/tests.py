from django.test import TestCase

from django.contrib.auth.models import User

from .models import Order


class AdminOrderTests(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(
            username='admin',
            password='test-password',
            is_staff=True,
        )
        self.order = Order.objects.create(user=self.admin)
        self.client.force_login(self.admin)

    def test_staff_can_accept_pending_order(self):
        response = self.client.post(
            '/admin-panel/orders/',
            {'order_id': self.order.pk, 'status': 'processing'},
        )

        self.assertRedirects(response, '/admin-panel/orders/')
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'processing')

    def test_pending_order_shows_processing_option(self):
        response = self.client.get('/admin-panel/orders/')

        self.assertContains(response, '<option value="processing" >Processing</option>', html=True)
