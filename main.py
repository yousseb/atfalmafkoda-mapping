#!/usr/bin/env python
# -*- coding: utf-8 -*-

from argparse import ArgumentParser, SUPPRESS
from typing import Iterator, Optional

import facebook_scraper as fs
import logging as log
import sys
import re
from pathlib import Path
from urllib.parse import urlparse, unquote
import json
from random import randint
from time import sleep


log.basicConfig(format='[ %(levelname)s ] %(message)s', level=log.INFO, stream=sys.stdout)


class Indexer:
    def __init__(self):
        self.map = {}

    def find_code(self, post: fs.Post) -> Optional[str]:
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

    def build_index(self) -> Iterator[fs.Post]:
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

        for post in gen:
            counter = counter + 1
            if counter % 9 == 0:
                log.info("Sleeping for 30s in order not to be blocked")
                sleep(30)

            code = self.find_code(post)
            post_images = post['images']

            if code is None:
                code = "no-code"

            code_exists = False
            try:
                _ = self.map[code]
                code_exists = True
                log.info('Code was repeated - could be a repost')
            except:
                pass

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
