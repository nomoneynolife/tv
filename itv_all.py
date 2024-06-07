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

eventlet.monkey_patch()

urls = [
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5rGf6IuPIg%3D%3D",           # 江苏省 37
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5rWZ5rGf55yBIg%3D%3D",       # 浙江省 201
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5rmW5YyXIg%3D%3D",          # 湖北省 57
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5rmW5Y2XIg%3D%3D",          # 湖南省 193
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0iZ3Vhbmdkb25nIg%3D%3D",      # 广东省 253
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5bm%2F6KW%2FIg%3D%3D",     # 广西壮族自治区 1662
    "https://fofa.info/result?qbase64=ImlwdHYvbGl2ZS96aF9jbi5qcyIgJiYgY291bnRyeT0iQ04iICYmIHJlZ2lvbj0i5r6z6ZeoIg%3D%3D"           # 澳门特别行政区 0
]

def modify_urls(url):
    """ Modify the URL by changing the last octet of the IP address and appending the specific path. """
    modified_urls = []
    ip_start_index = url.find("//") + 2
    ip_end_index = url.find(":", ip_start_index)
    base_url = url[:ip_start_index]
    ip_address = url[ip_start_index:ip_end_index]
    port = url[ip_end_index:]
    ip_end = "/iptv/live/1000.json?key=txiptv"
    for i in range(1, 256):
        modified_ip = f"{ip_address[:-1]}{i}"
        modified_url = f"{base_url}{modified_ip}{port}{ip_end}"
        modified_urls.append(modified_url)
    return modified_urls

def is_url_accessible(url):
    """ Check if the URL is accessible by sending a GET request. """
    try:
        response = requests.get(url, timeout=0.5)
        if response.status_code == 200:
            return url
    except requests.exceptions.RequestException:
        pass
    return None

def extract_urls_from_page(url):
    """ Use Selenium to extract URLs from the given webpage. """
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    driver = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    time.sleep(10)
    page_content = driver.page_source
    driver.quit()
    pattern = r"http://\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d+"
    return set(re.findall(pattern, page_content))

def validate_and_extract_streams(urls):
    """ Validate the modified URLs and extract stream information. """
    results = []
    for url in urls:
        modified_urls = modify_urls(url)
        valid_urls = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=100) as executor:
            futures = [executor.submit(is_url_accessible, u) for u in modified_urls]
            for future in concurrent.futures.as_completed(futures):
                result = future.result()
                if result:
                    valid_urls.append(result)
        for valid_url in valid_urls:
            try:
                response = requests.get(valid_url, timeout=0.5)
                json_data = response.json()
                base_url = valid_url.rsplit('/', 1)[0]
                for item in json_data.get('data', []):
                    name = item.get('name')
                    urlx = item.get('url')
                    if name and urlx:
                        if not urlx.startswith('http'):
                            urlx = f"{base_url}/{urlx}"
                        results.append((name, urlx))
            except requests.exceptions.RequestException:
                continue
    return results

def worker(task_queue, results, error_channels, channels):
    """ Worker function for downloading and validating stream URLs. """
    while True:
        channel_name, channel_url = task_queue.get()
        try:
            channel_url_t = channel_url.rstrip(channel_url.split('/')[-1])
            lines = requests.get(channel_url, timeout=1).text.strip().split('\n')
            ts_lists = [line.split('/')[-1] for line in lines if not line.startswith('#')]
            ts_lists_0 = ts_lists[0].rstrip(ts_lists[0].split('.ts')[-1])
            ts_url = f"{channel_url_t}{ts_lists[0]}"
            with eventlet.Timeout(5, False):
                start_time = time.time()
                content = requests.get(ts_url, timeout=1).content
                end_time = time.time()
                response_time = (end_time - start_time) * 1
            if content:
                with open(ts_lists_0, 'ab') as f:
                    f.write(content)
                file_size = len(content)
                download_speed = file_size / response_time / 1024
                normalized_speed = min(max(download_speed / 1024, 0.001), 100)
                os.remove(ts_lists_0)
                result = (channel_name, channel_url, f"{normalized_speed:.3f} MB/s")
                results.append(result)
                numberx = (len(results) + len(error_channels)) / len(channels) * 100
                print(f"可用频道：{len(results)} 个 , 不可用频道：{len(error_channels)} 个 , 总频道：{len(channels)} 个 ,总进度：{numberx:.2f} %。")
        except Exception:
            error_channels.append((channel_name, channel_url))
            numberx = (len(results) + len(error_channels)) / len(channels) * 100
            print(f"可用频道：{len(results)} 个 , 不可用频道：{len(error_channels)} 个 , 总频道：{len(channels)} 个 ,总进度：{numberx:.2f} %。")
        finally:
            task_queue.task_done()

def main():
    all_channels = []
    for url in urls:
        extracted_urls = extract_urls_from_page(url)
        streams = validate_and_extract_streams(extracted_urls)
        all_channels.extend(streams)

    task_queue = Queue()
    results = []
    error_channels = []

    for channel in all_channels:
        task_queue.put(channel)

    threads = []
    for _ in range(10):
        t = threading.Thread(target=worker, args=(task_queue, results, error_channels, all_channels))
        t.daemon = True
        t.start()
        threads.append(t)

    task_queue.join()

    for t in threads:
        t.join()

    print(f"All tasks completed. {len(results)} valid channels found.")
    return results

if __name__ == "__main__":
    main()
