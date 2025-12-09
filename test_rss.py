import unittest
import feedparser
import requests

class TestRSSFetching(unittest.TestCase):
    def setUp(self):
        self.urls = [
            "https://techcrunch.com/feed/",
            "https://www.cnbc.com/id/100003114/device/rss/rss.html"
        ]
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

    def test_rss_feeds_reachable(self):
        print("\nTesting RSS Fetching...")
        for url in self.urls:
            with self.subTest(url=url):
                print(f"Fetching {url}...")
                try:
                    response = requests.get(url, headers=self.headers, timeout=10)
                    self.assertEqual(response.status_code, 200, f"Failed to fetch {url}: Status {response.status_code}")
                    
                    feed = feedparser.parse(response.content)
                    self.assertTrue(len(feed.entries) > 0, f"No entries found in {url}")
                    print(f"Entries: {len(feed.entries)}")
                    if feed.entries:
                        print(f"Top Title: {feed.entries[0].title}")
                except Exception as e:
                    self.fail(f"Exception while fetching {url}: {e}")

if __name__ == '__main__':
    unittest.main()
