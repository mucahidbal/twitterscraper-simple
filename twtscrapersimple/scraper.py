import time
import json
from datetime import datetime
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException
from seleniumwire import webdriver
from seleniumwire.utils import decode


class Scraper:
    def __init__(self, driver_path: str):
        self.driver = self.prepare_driver(driver_path)

    def retrieve_tweets(self, username: str, scroll_count: int = 1) -> list[dict]:
        tweets = []

        self.driver.get('https://twitter.com/i/user/' + self.find_user_id(username))

        account_data_request = self.driver.wait_for_request('UserByRestId')
        account_data = json.loads(decode(account_data_request.response.body, account_data_request.response.headers.get('Content-Encoding')))

        if not account_data['data']['user'] or account_data['data']['user']['result']['__typename'] != 'User':
            del self.driver.requests
            return tweets

        time.sleep(10)

        for i in range(scroll_count):
            request = self.driver.wait_for_request('UserTweets')
            data = json.loads(decode(request.response.body, request.response.headers.get('Content-Encoding')))

            for timeline_data in data['data']['user']['result']['timeline_v2']['timeline']['instructions']:
                if timeline_data['type'] != 'TimelineAddEntries':
                    continue

                for tweet_data in timeline_data['entries']:
                    if tweet_data['content']['entryType'] == 'TimelineTimelineItem' and tweet_data['content']['itemContent']['tweet_results']['result']['__typename'] == 'Tweet':
                        data = {
                            'full_text': None
                        }

                        tweet_date = self._convert_to_datetime(tweet_data['content']['itemContent']['tweet_results']['result']['legacy']['created_at'])

                        data['date'] = tweet_date

                        if 'full_text' in tweet_data['content']['itemContent']['tweet_results']['result']['legacy']:
                            tweet_text = tweet_data['content']['itemContent']['tweet_results']['result']['legacy']['full_text']

                            data['full_text'] = tweet_text

                        tweets.append(data)

            del self.driver.requests

            if i < scroll_count - 1:
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        return tweets

    def find_user_id(self, twitter_username: str) -> str:
        self.driver.get('https://twitter.com/' + twitter_username)
        try:
            account_data_request = self.driver.wait_for_request('UserByScreenName', timeout=20)
        except TimeoutException:
            return ''

        account_data = json.loads(decode(account_data_request.response.body, account_data_request.response.headers.get('Content-Encoding')))

        try:
            return account_data['data']['user']['result']['rest_id']
        except KeyError:
            return ''

    @staticmethod
    def prepare_driver(driver_path: str) -> webdriver.Chrome:
        chrome_options = webdriver.ChromeOptions()
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        return webdriver.Chrome(service=Service(driver_path), options=chrome_options)

    @staticmethod
    def _convert_to_datetime(date: str) -> datetime:
        return datetime.strptime(date, '%a %b %d %H:%M:%S %z %Y')

    @staticmethod
    def _convert_to_mysql_date(date: datetime) -> str:
        return date.strftime('%Y-%m-%d %H:%M:%S')
