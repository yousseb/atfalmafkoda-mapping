#!/usr/bin/env python
# -*- coding: utf-8 -*-

from argparse import ArgumentParser, SUPPRESS
from types import SimpleNamespace
from typing import Iterator, Optional

from facebook_scraper import FacebookScraper, Post
import logging as log
import sys
import re
from pathlib import Path
from urllib.parse import urlparse, unquote
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

    def get_proxies(self):
        log.info("Getting proxies")
        headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
        r = requests.get('https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc&country=US&speed=medium&protocols=http%2Chttps', headers=headers)
        json_proxies = json.loads(r.text, object_hook=lambda d: SimpleNamespace(**d))
        self.proxies = json_proxies.data
        self.proxy_iter = iter(self.proxies)
        log.info(f"Proxies count: {len(self.proxies)}")

    def get_next_proxy(self) -> str:
        try:
            proxy = next(self.proxy_iter)
        except StopIteration:
            self.proxy_iter = iter(self.proxies)
            proxy = next(self.proxy_iter)
        proxy_str = proxy.protocols[0] + '//' + proxy.ip + ':' + proxy.port

    def build_index(self) -> Iterator[Post]:
        self.get_proxies()
        fs = FacebookScraper()
        fs.set_user_agent('Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36')

        gen = fs.get_posts(
            'atfalmafkoda',
            pages=999999,
            posts_per_page=9,
            cookies='cookie.txt',
            options={"comments": False,
                     "reactors": False,
                     "allow_extra_requests": True,
                     "remove_source": True,
                     "extra_info": False,
                     "progress": False}
        )
        counter = 0

        while True:
            fs.set_proxy(self.get_next_proxy(), verify=True)

            post = None
            try:
                post = next(gen)
            except StopIteration:
                break

            # counter = counter + 1
            # if counter % 9 == 0:
            #     log.info("Sleeping for 30s in order not to be blocked")
            #     sleep(30)

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
                #cleaned_image = cleaned_image.split("?")[0]
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
