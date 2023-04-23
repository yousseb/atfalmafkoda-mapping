#!/usr/bin/env python
# -*- coding: utf-8 -*-
import urllib
from argparse import ArgumentParser, SUPPRESS
from types import SimpleNamespace
from typing import Iterator, Optional

from facebook_scraper import FacebookScraper, Post
from facebook_scraper.exceptions import TemporarilyBanned
from facebook_scraper.utils import parse_cookie_file
import logging as log
import sys
import re
from pathlib import Path
from urllib.parse import urlparse, unquote, urlsplit
import json
from random import randint
from time import sleep
import requests

log.basicConfig(format='[ %(levelname)s ] %(message)s', level=log.INFO, stream=sys.stdout)


class Indexer:
    def __init__(self):
        self.map = {}
        self.proxies = []
        self.proxy_iter = None

    def find_code(self, post: Post) -> Optional[str]:
        lines = post['text'].split('\n')
        for line in lines:
            if any(map(line.__contains__, ['code', 'كود'])):
                log.info(f'Found code line: {line}')
                cleaned = re.sub('[^0-9]', '', line)
                try:
                    cleaned = int(cleaned)
                    return str(cleaned)
                except ValueError:
                    log.warning(f'Error while finding code for: {cleaned}')
                    return None

        log.warning(f'Post has no code: {post}')
        return None

    def is_bad_proxy(self, proxy: str) -> bool:
        url = 'https://api.ipify.org'
        proxies = {"http": proxy, "https": proxy}
        proxy_ip = '{0.netloc}'.format(urlsplit(proxy))

        try:
            response = requests.get(url, proxies=proxies)
            assert response.text == proxy_ip
            return True
        except:
            return False

    def fetch_proxies(self, use_cache: bool = True):
        log.info("Fetching proxies")
        text = None
        if use_cache:
            log.info("Trying to use cache for proxies")
            cache_file = 'proxy_cache.json'
            cached_proxies = Path(cache_file)
            cache_found = cached_proxies.is_file()
            if cache_found:
                f = open(cache_file, "r")
                text = f.read()
                log.info("Proxies read from cache")
        if not use_cache or not cache_found:
            log.info("Fetching proxies from the internet")
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.35 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
            r = requests.get(
                'https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&country=US&speed=medium&protocols=http',
                headers=headers)
            text = r.text
            if use_cache:
                f = open(cache_file, 'w')
                f.write(text)

        json_proxies = json.loads(text, object_hook=lambda d: SimpleNamespace(**d))
        self.proxies = json_proxies.data
        self.proxy_iter = iter(self.proxies)
        log.info(f"Proxies count: {len(self.proxies)}")

    def get_next_proxy(self) -> Optional[str]:
        proxy_str = None
        while True:
            try:
                proxy = next(self.proxy_iter)
            except StopIteration:
                self.proxy_iter = iter(self.proxies)
                proxy = next(self.proxy_iter)
            proxy_str = f"{proxy.protocols[0]}://{proxy.ip}:{proxy.port}/"
            if self.is_bad_proxy(proxy_str):
                log.info(f"Proxy {proxy_str} is bad. Trying another.")
            else:
                log.info(f"Proxy {proxy_str} is good.")
                break
        return proxy_str

    def build_index(self) -> Iterator[Post]:
        self.fetch_proxies()

        fs = FacebookScraper()
        fs.set_user_agent(
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36')
        proxy = self.get_next_proxy()
        fs.requests_kwargs['timeout'] = 30
        fs.set_proxy(proxy)
        # fs.session.proxies.update({'http': proxy, 'https': proxy})

        cookies = parse_cookie_file('cookie.txt')
        fs.session.cookies.update(cookies)
        if not fs.is_logged_in():
            raise RuntimeError('Cookies are not valid')

        gen = fs.get_posts(
            'atfalmafkoda',
            pages=999999,
            posts_per_page=9,
            options={"comments": False,
                     "reactors": False,
                     "allow_extra_requests": True,
                     "remove_source": True,
                     "extra_info": False,
                     "progress": False}
        )
        counter = 0

        while True:
            post = None
            try:
                post = next(gen)
            except StopIteration:
                break

            counter = counter + 1
            if counter % 9 == 0:
                log.info("Switching proxies in order not to be blocked")
                proxy = self.get_next_proxy()
                fs.set_proxy(proxy)
                # fs.session.proxies.update({'http': proxy, 'https': proxy})

            code = self.find_code(post)
            post_images = post['images']

            if code is None:
                code = "no-code"

            code_exists = False
            if code in self.map:
                code_exists = True
                log.info('Code was repeated - could be a repost')

            images = []
            for image in post_images:
                url_parsed = urlparse(image)
                cleaned_image = unquote(Path(url_parsed.path).name)
                # cleaned_image = cleaned_image.split("?")[0]
                images.append(cleaned_image)

            if code_exists:
                self.map[code] = self.map[code] + images
                self.map[code] = list(set(self.map[code]))  # Unique
            else:
                self.map[code] = images

        with open('map.json', 'w') as fp:
            json.dump(self.map, fp, indent=2)

        return gen


def build_argparser():
    parser = ArgumentParser(add_help=False)
    args = parser.add_argument_group('Options')
    args.add_argument('-h', '--help', action='help', default=SUPPRESS, help='Show this help message and exit.')
    return parser


if __name__ == '__main__':
    args = build_argparser().parse_args()
    Indexer().build_index()
