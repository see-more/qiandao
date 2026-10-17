import unittest
from unittest.mock import patch

import requests

from soushuba import SouShuBaClient


def response(html, status=200):
    result = requests.Response()
    result.status_code = status
    result.url = 'https://example.invalid/home.php?mod=spacecp&ac=credit&op=base'
    result.encoding = 'gbk'
    result._content = html.encode('gbk')
    return result


class CreditTests(unittest.TestCase):
    def setUp(self):
        self.client = SouShuBaClient('example.invalid', 'unused', 'unused')
        self.addCleanup(self.client.session.close)

    def test_silver_is_read_without_header_menu_or_confusing_total_points(self):
        page = '''<ul class="creditl mtm">
          <li><em>积分: </em>9999</li>
          <li><em><img src="coin.gif"> 银币: </em><strong>123</strong> 枚
            <a href="home.php?op=buy">充值 100 枚</a></li>
        </ul>'''
        with patch.object(self.client.session, 'get', return_value=response(page)):
            self.assertEqual(self.client.credit(), '123')

    def test_zero_negative_and_formatted_balances_are_not_replaced_with_defaults(self):
        for value, expected in [('0', '0'), ('-12', '-12'), ('1,234.50', '1234.50')]:
            with self.subTest(value=value):
                page = f'<ul class="creditl"><li><em>银币：</em>{value} 枚</li></ul>'
                with patch.object(self.client.session, 'get', return_value=response(page)):
                    self.assertEqual(self.client.credit(), expected)

    def test_http_200_login_page_is_reported_as_lost_authentication(self):
        page = '<form id="loginform_abcd">您需要先登录才能继续本操作</form>'
        with patch.object(self.client.session, 'get', return_value=response(page)):
            with self.assertRaisesRegex(RuntimeError, '登录状态已失效'):
                self.client.credit()

    def test_http_error_takes_precedence_over_balance_looking_content(self):
        page = '<ul class="creditl"><li><em>银币:</em>123</li></ul>'
        with patch.object(self.client.session, 'get', return_value=response(page, 403)):
            with self.assertRaises(requests.HTTPError):
                self.client.credit()

    def test_missing_silver_is_not_reported_as_other_currency_or_zero(self):
        page = '<ul class="creditl"><li><em>积分:</em>123</li></ul>'
        with patch.object(self.client.session, 'get', return_value=response(page)):
            with self.assertRaisesRegex(RuntimeError, '缺少“银币”字段'):
                self.client.credit()

    def test_invalid_silver_does_not_return_a_recharge_link_amount(self):
        page = '''<ul class="creditl"><li><em>银币:</em>暂不可用
          <a href="home.php?op=buy">充值 100 枚</a></li></ul>'''
        with patch.object(self.client.session, 'get', return_value=response(page)):
            with self.assertRaisesRegex(RuntimeError, '不是有效数字'):
                self.client.credit()

    def test_http_200_without_auth_cookie_is_not_successful_login(self):
        self.client.session.cookies.set('prefix_saltkey', 'not-an-auth-cookie')
        with patch.object(self.client, 'login_form_hash', return_value=('login', 'form')):
            with patch.object(self.client.session, 'post', return_value=response('登录失败')):
                with self.assertRaisesRegex(RuntimeError, '未取得 Discuz 认证 Cookie'):
                    self.client.login()


if __name__ == '__main__':
    unittest.main()
