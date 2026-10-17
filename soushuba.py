# -*- coding: utf-8 -*-
"""
实现搜书吧论坛登入和发布空间动态
"""
import argparse
import os
import re
import sys
from copy import copy

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import time
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

ch = logging.StreamHandler(stream=sys.stdout)
ch.setLevel(logging.INFO)
ch.setFormatter(formatter)
logger.addHandler(ch)

def get_refresh_url(url: str):
    try:
        response = requests.get(url)
        if response.status_code != 403:
            response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        meta_tags = soup.find_all('meta', {'http-equiv': 'refresh'})

        if meta_tags:
            content = meta_tags[0].get('content', '')
            if 'url=' in content:
                redirect_url = content.split('url=')[1].strip()
                logger.info(f"Redirecting to: {redirect_url}")
                return redirect_url
        else:
            logger.error("No meta refresh tag found.")
            return None
    except Exception as e:
        logger.exception(f'An unexpected error occurred: {e}')
        return None

def get_url(url: str):
    resp = requests.get(url)
    soup = BeautifulSoup(resp.content, 'html.parser')
    
    links = soup.find_all('a', href=True)
    for link in links:
        if link.text == "搜书吧":
            return link['href']
    return None

class SouShuBaClient:

    def __init__(self, hostname: str, username: str, password: str, questionid: str = '0', answer: str = None,
                 proxies: dict | None = None):
        self.session: requests.Session = requests.Session()
        self.hostname = hostname
        self.username = username
        self.password = password
        self.questionid = questionid
        self.answer = answer
        self._common_headers = {
            "Host": f"{ hostname }",
            "Connection": "keep-alive",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            "Accept-Language": "zh-CN,cn;q=0.9",
            "Content-Type": "application/x-www-form-urlencoded",
        }
        self.proxies = proxies

    def login_form_hash(self):
        rst = self.session.get(f'https://{self.hostname}/member.php?mod=logging&action=login', verify=False).text
        loginhash = re.search(r'<div id="main_messaqge_(.+?)">', rst).group(1)
        formhash = re.search(r'<input type="hidden" name="formhash" value="(.+?)" />', rst).group(1)
        return loginhash, formhash

    def login(self):
        """Login with username and password"""
        loginhash, formhash = self.login_form_hash()
        login_url = f'https://{self.hostname}/member.php?mod=logging&action=login&loginsubmit=yes' \
                    f'&handlekey=register&loginhash={loginhash}&inajax=1'


        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f'https://{self.hostname}/'
        payload = {
            'formhash': formhash,
            'referer': f'https://{self.hostname}/',
            'username': self.username,
            'password': self.password,
            'questionid': self.questionid,
            'answer': self.answer
        }

        resp = self.session.post(login_url, proxies=self.proxies, data=payload, headers=headers, verify=False)
        resp.raise_for_status()
        if not any(cookie.name.endswith('_auth') and cookie.value
                   for cookie in self.session.cookies):
            raise RuntimeError('登录失败：未取得 Discuz 认证 Cookie，请检查账号、密码或安全提问')
        logger.info(f'Welcome {self.username}!')

    def credit(self):
        credit_url = f"https://{self.hostname}/home.php?mod=spacecp&ac=credit&op=base"
        response = self.session.get(credit_url, verify=False, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, features="lxml")
        if soup.select_one('form[id^="loginform_"]') or '您需要先登录才能继续本操作' in soup.get_text():
            raise RuntimeError('查询银币失败：登录状态已失效，请重新登录')

        # 顶部 AJAX 菜单可能隐藏积分；完整积分页按币种名称展示实际余额。
        for item in soup.select('ul.creditl > li'):
            label = item.find('em', recursive=False)
            if label is None or label.get_text(strip=True).rstrip(':：').strip() != '银币':
                continue
            label.decompose()
            balance = re.match(r'([+-]?\d+(?:,\d{3})*(?:\.\d+)?)(?=\s|$)',
                               item.get_text(' ', strip=True))
            if balance is None:
                raise RuntimeError('查询银币失败：银币字段不是有效数字')
            return balance.group(1).replace(',', '')

        raise RuntimeError('查询银币失败：完整积分页缺少“银币”字段，请检查站点响应或页面结构')

    def space_form_hash(self):
        rst = self.session.get(f'https://{self.hostname}/home.php', verify=False).text
        formhash = re.search(r'<input type="hidden" name="formhash" value="(.+?)" />', rst).group(1)
        return formhash

    def space(self):
        formhash = self.space_form_hash()
        space_url = f"https://{self.hostname}/home.php?mod=spacecp&ac=doing&handlekey=doing&inajax=1"

        headers = copy(self._common_headers)
        headers["origin"] = f'https://{self.hostname}'
        headers["referer"] = f'https://{self.hostname}/home.php'

        for x in range(5):
            payload = {
                "message": "开心赚银币 {0} 次".format(x + 1).encode("GBK"),
                "addsubmit": "true",
                "spacenote": "true",
                "referer": "home.php",
                "formhash": formhash
            }
            resp = self.session.post(space_url, proxies=self.proxies, data=payload, headers=headers, verify=False)
            if re.search("操作成功", resp.text):
                logger.info(f'{self.username} post {x + 1}nd successfully!')
                time.sleep(120)
            else:
                logger.warning(f'{self.username} post {x + 1}nd failed!')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='搜书吧自动签到及余额查询')
    parser.add_argument('--check-only', action='store_true',
                        help='只登录和查询银币余额，不发布空间动态')
    args = parser.parse_args()
    try:
        redirect_url = get_refresh_url('http://' + os.environ.get('SOUSHUBA_HOSTNAME', 'www.soushu2035.com'))
        time.sleep(2)
        redirect_url2 = get_refresh_url(redirect_url)
        url = get_url(redirect_url2)
        logger.info(f'{url}')
        client = SouShuBaClient(urlparse(url).hostname,
                                os.environ.get('SOUSHUBA_USERNAME', "USERNAME"),
                                os.environ.get('SOUSHUBA_PASSWORD', "PASSWORD"))
        client.login()
        if not args.check_only:
            client.space()
        credit = client.credit()
        logger.info(f'{client.username} have {credit} coins!')
    except Exception as e:
        logger.error(e)
        sys.exit(1)
