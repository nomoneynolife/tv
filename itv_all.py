import time
import concurrent.futures
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import requests
import re
import os
import threading
from queue import Queue
import eventlet
import logging

eventlet.monkey_patch()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

urls = [
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5rGf6IuPIg%3D%3D",           # 江苏省 37
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5rWZ5rGf55yBIg%3D%3D",       # 浙江省 201
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5rmW5YyXIg%3D%3D",          # 湖北省 57
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5rmW5Y2XIg%3D%3D",          # 湖南省 193
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0iZ3Vhbmdkb25nIg%3D%3D",      # 广东省 253
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5bm%2F6KW%2FIg%3D%3D",     # 广西壮族自治区 1662
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5r6z6ZeoIg%3D%3D"  # 澳门特别行政区 0
]

def modify_urls(url):
    modified_urls = []
    ip_start_index = url.find("//") + 2
    ip_end_index = url.find(":", ip_start_index)
    base_url = url[:ip_start_index]  # http:// or https://
    ip_address = url[ip_start_index:ip_end_index]
    port = url[ip_end_index:]
    ip_end = "/iptv/live/1000.json?key=txiptv"
    for i in range(1, 256):
        modified_ip = f"{ip_address[:-1]}{i}"
        modified_url = f"{base_url}{modified_ip}{port}{ip_end}"
        modified_urls.append(modified_url)
    return modified_urls

def is_url_accessible(url):
    try:
        response = requests.get(url, timeout=0.5)
        if response.status_code == 200:
            return url
    except requests.exceptions.RequestException:
        pass
    return None

def get_page_content(url):
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')

    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(10)
    page_content = driver.page_source
    driver.quit()
    return page_content

def extract_urls(page_content):
    pattern = r"http://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+"
    urls_all = re.findall(pattern, page_content)
    return set(urls_all)

def validate_and_modify_urls(urls):
    x_urls = []
    for url in urls:
        url = url.strip()
        ip_start_index = url.find("//") + 2
        ip_end_index = url.find(":", ip_start_index)
        ip_dot_start = url.find(".") + 1
        ip_dot_second = url.find(".", ip_dot_start) + 1
        ip_dot_three = url.find(".", ip_dot_second) + 1
        base_url = url[:ip_start_index]
        ip_address = url[ip_start_index:ip_dot_three]
        port = url[ip_end_index:]
        ip_end = "1"
        modified_ip = f"{ip_address}{ip_end}"
        x_url = f"{base_url}{modified_ip}{port}"
        x_urls.append(x_url)
    return set(x_urls)

def fetch_and_parse_json(url, valid_urls):
    try:
        ip_start_index = url.find("//") + 2
        ip_index_second = url.find("/", url.find(".") + 1)
        base_url = url[:ip_start_index]
        ip_address = url[ip_start_index:ip_index_second]
        url_x = f"{base_url}{ip_address}"
        json_url = f"{url}"
        response = requests.get(json_url, timeout=0.5)
        json_data = response.json()

        results = []
        for item in json_data['data']:
            if isinstance(item, dict):
                name = item.get('name')
                urlx = item.get('url')
                if urlx and 'http' not in urlx:
                    urlx = f"{url_x}{urlx}"
                if name and urlx:
                    name = re.sub(r"CCTV(\d+)台", r"CCTV\1", name)
                    name = re.sub(r"(\w+卫视).*", r"\1", name)
                    results.append((name, urlx))
        return results
    except Exception as e:
        logging.error(f"Error fetching or parsing JSON from {url}: {e}")
        return []

def download_speed_test(channel_name, channel_url):
    try:
        channel_url_t = channel_url.rstrip(channel_url.split('/')[-1])
        lines = requests.get(channel_url, timeout=1).text.strip().split('\n')
        ts_lists = [line.split('/')[-1] for line in lines if not line.startswith('#')]
        ts_lists_0 = ts_lists[0].rstrip(ts_lists[0].split('.ts')[-1])
        ts_url = f"{channel_url_t}{ts_lists_0}.ts"
        start = time.time()
        response = requests.get(ts_url, timeout=1, stream=True)
        total_length = int(response.headers.get('content-length', 0))
        if total_length == 0:
            return 0

        downloaded = 0
        for chunk in response.iter_content(32 * 1024):
            downloaded += len(chunk)
            if time.time() - start > 1:
                break

        duration = time.time() - start
        if duration == 0:
            duration = 1
        speed = (downloaded / 1024) / duration
        return speed
    except Exception as e:
        logging.error(f"Error testing download speed for {channel_name} - {channel_url}: {e}")
        return 0

def process_channels(valid_urls):
    available_channels = []
    unavailable_channels = []
    for url in valid_urls:
        channels = fetch_and_parse_json(url, valid_urls)
        for name, channel_url in channels:
            speed = download_speed_test(name, channel_url)
            if speed > 0:
                normalized_speed = min(10 * round(speed / 10), 100)
                available_channels.append((name, channel_url, normalized_speed))
            else:
                unavailable_channels.append((name, channel_url))

    return available_channels, unavailable_channels

def main():
    for url in urls:
        modified_urls = modify_urls(url)
        valid_urls = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(is_url_accessible, mod_url) for mod_url in modified_urls]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    valid_urls.append(result)
        
        page_content = get_page_content(url)
        extracted_urls = extract_urls(page_content)
        x_urls = validate_and_modify_urls(extracted_urls)
        valid_urls.extend(x_urls)

        available_channels, unavailable_channels = process_channels(valid_urls)

        logging.info(f"Available Channels: {len(available_channels)}")
        logging.info(f"Unavailable Channels: {len(unavailable_channels)}")

if __name__ == "__main__":
    main()
