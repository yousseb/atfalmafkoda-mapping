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

log.basicConfig(format='[ %(levelname)s ] %(message)s', level=log.INFO, stream=sys.stdout)

MAX_COMMENTS = 0


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
            pages=2,
            options={"comments": MAX_COMMENTS, "progress": True}
        )
        for post in gen:
            code = self.find_code(post)
            post_images = post['images']

            try:
                _ = self.map[code]
                log.info('Code was repeated - could be a repost')
            except:
                pass

            images = []
            for image in post_images:
                url_parsed = urlparse(image)
                cleaned_image = unquote(Path(url_parsed.path).name)
                #cleaned_image = cleaned_image.split("?")[0]
                images.append(cleaned_image)

            self.map[code] = images
            print(code)

        with open('map.json', 'w') as fp:
            json.dump(self.map, fp, indent=2)

        return gen


def build_argparser():
    parser = ArgumentParser(add_help=False)
    args = parser.add_argument_group('Options')
    args.add_argument('-h', '--help', action='help', default=SUPPRESS, help='Show this help message and exit.')
    return parser

    # Use a breakpoint in the code line below to debug your script.
    print(f'Hi, {name}')  # Press Ctrl+F8 to toggle the breakpoint.


if __name__ == '__main__':
    args = build_argparser().parse_args()
    Indexer().build_index()
