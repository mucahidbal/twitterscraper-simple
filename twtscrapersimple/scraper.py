from __future__ import annotations
import json
from datetime import datetime
from typing import TYPE_CHECKING
from pydash.objects import get
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
from seleniumwire import webdriver
from seleniumwire.utils import decode

if TYPE_CHECKING:
    from seleniumwire.request import Request


class Scraper:
    def __init__(self, driver_path: str):
        self.driver = self.prepare_driver(driver_path)

    def retrieve_tweets(self, username: str = '', user_id: str = '', page_count: int = 1) -> list[dict] | None:
        if username:
            self.driver.get('https://twitter.com/' + username)
        elif user_id:
            self.driver.get('https://twitter.com/i/user/' + user_id)
        else:
            raise ValueError

        if not self.wait_for_request('UserByRestId'):
            self.clear_requests()
            return None

        tweets = []
        for i in range(page_count):
            if not (data := self.wait_for_request('UserTweets')):
                return tweets

            tweets.extend(self.extract_tweets(data))

            self.clear_requests()

            if i < page_count - 1:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        return tweets

    def extract_tweets(self, data: dict):
        tweets = []
        for timeline_data in get(data, 'data.user.result.timeline_v2.timeline.instructions', []):
            if get(timeline_data, 'type') != 'TimelineAddEntries':
                continue

            for tweet_data in get(timeline_data, 'entries'):
                if get(tweet_data, 'content.entryType') != 'TimelineTimelineItem':
                    continue

                tweet_result = get(tweet_data, 'content.itemContent.tweet_results.result')

                if get(tweet_result, '__typename') != 'Tweet':
                    continue

                tweets.append(
                    {
                        'full_text': get(tweet_result, 'legacy.full_text'),
                        'date': self._convert_to_datetime(get(tweet_result, 'legacy.created_at', ''))
                    }
                )

        return tweets

    def find_user_id(self, twitter_username: str) -> str:
        self.driver.get('https://twitter.com/' + twitter_username)

        if account_data := self.wait_for_request('UserByScreenName', 20):
            self.clear_requests()
            return get(account_data, 'data.user.result.rest_id', '')

        return ''

    def clear_requests(self):
        del self.driver.requests

    def wait_for_request(self, request_pattern: str, timeout: int = 10) -> dict:
        try:
            request = self.driver.wait_for_request(request_pattern, timeout=timeout)
            return json.loads(decode(request.response.body, request.response.headers.get('Content-Encoding')))
        except (TimeoutException, json.JSONDecodeError, TypeError):
            return None

    @staticmethod
    def prepare_driver(driver_path: str) -> webdriver.Chrome:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        driver = webdriver.Chrome(service=Service(driver_path), options=chrome_options)
        driver.scopes = [r'.*twitter[.]com.*']
        return driver

    @staticmethod
    def _convert_to_datetime(date: str) -> datetime | None:
        try:
            return datetime.strptime(date, '%a %b %d %H:%M:%S %z %Y')
        except ValueError:
            return None
