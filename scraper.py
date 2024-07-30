import os
import pickle
import requests
import time
from functools import wraps
from typing import Callable, List, Optional
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException, TimeoutException
import selenium_stealth
from seleniumwire import webdriver as wire_webdriver
from webdriver_manager.chrome import ChromeDriverManager


def retry(max_attempts: int = 3, delay: int = 1):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempts = 0
            while attempts < max_attempts:
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    attempts += 1
                    if attempts == max_attempts:
                        raise e
                    time.sleep(delay)

        return wrapper

    return decorator


class Scraper:
    def __init__(
        self,
        proxy_list: Optional[List[str]] = None,
        proxy_rotation_threshold: int = 6,
        cookies_path: str = "cookies.pkl",
        headless: bool = True,
    ):
        self.proxy_list = proxy_list or []
        self.num_proxies = len(self.proxy_list)
        self.proxy_rotation_threshold = proxy_rotation_threshold
        self.cookies_path = cookies_path
        self.real_ip = self._get_real_ip()
        self.current_proxy_index = 0
        self.retries = 0
        self.num_calls = 0
        self.headless = headless
        self.current_driver = self.get_driver()

    @retry(max_attempts=3)
    def _get_real_ip(self) -> str:
        try:
            response = requests.get("http://api64.ipify.org")
            response.raise_for_status()
            return response.text.strip()
        except requests.RequestException as e:
            print(f"Error getting real IP: {e}")
            return "Unknown"

    def create_chrome_options(self) -> Options:
        chrome_options = Options()
        chrome_options.add_argument("--blink-settings=imagesEnabled=false")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/102.0.5005.61 Safari/537.36"
        )
        chrome_options.add_experimental_option("useAutomationExtension", False)
        chrome_options.add_experimental_option(
            "excludeSwitches", ["enable-logging", "enable-automation"]
        )
        chrome_options.add_argument("start-maximized")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-browser-side-navigation")
        chrome_options.add_argument("--disable-gpu")
        if self.headless:
            chrome_options.add_argument("--headless")
        return chrome_options

    @retry(max_attempts=3)
    def get_driver(self) -> webdriver.Chrome:
        if hasattr(self, "current_driver"):
            self.current_driver.quit()

        chrome_options = self.create_chrome_options()
        wire_options = {}

        if self.num_proxies > 0:
            wire_options = self._configure_proxy(chrome_options)

        try:
            driver_path = ChromeDriverManager().install()
            service = Service(executable_path=driver_path)
            driver = wire_webdriver.Chrome(
                service=service,
                options=chrome_options,
                seleniumwire_options=wire_options,
            )

            selenium_stealth.stealth(
                driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
            )

            if self.num_proxies > 0:
                self._check_proxy_ip(driver)

            return driver
        except Exception as e:
            print(f"Error creating driver: {e}")
            raise

    def _configure_proxy(self, chrome_options: Options) -> dict:
        proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % self.num_proxies

        splitted_proxy = proxy.split(":")
        print(f"Current Proxy: [{splitted_proxy[0]}:{splitted_proxy[1]}]")

        wire_options = {
            "proxy": {
                "http": f"http://{proxy}",
                "https": f"https://{proxy}",
                "no_proxy": None,
            }
        }

        if len(splitted_proxy) == 4:  # username:password:ip:port
            wire_options["proxy"] = {
                "http": f"http://{splitted_proxy[2]}:{splitted_proxy[3]}@{splitted_proxy[0]}:{splitted_proxy[1]}",
                "https": f"https://{splitted_proxy[2]}:{splitted_proxy[3]}@{splitted_proxy[0]}:{splitted_proxy[1]}",
                "no_proxy": None,
            }
        elif len(splitted_proxy) != 2:  # Not ip:port
            raise ValueError(
                f"Invalid Proxy ['{proxy}'] encountered in the proxy list."
            )

        chrome_options.add_argument(
            f"--proxy-server={splitted_proxy[0]}:{splitted_proxy[1]}"
        )
        return wire_options

    def _check_proxy_ip(self, driver: webdriver.Chrome) -> None:
        try:
            driver.get("http://api64.ipify.org")
            self.current_proxy_ip = driver.find_element(
                By.CSS_SELECTOR, "pre"
            ).text.strip()
        except Exception:
            self.current_proxy_ip = self.real_ip
            print("Couldn't Resolve Proxy IP")

        if self.current_proxy_ip == self.real_ip:
            self.retries += 1
            if self.retries <= self.num_proxies:
                print("Forced a proxy rotate due to an IP leak")
                raise WebDriverException("IP leak detected")
            else:
                raise Exception("All proxies are down")

    @retry(max_attempts=3)
    def web_get(self, url: str) -> bool:
        self.num_calls += 1

        if self.num_calls % self.proxy_rotation_threshold == 0:
            self.current_driver = self.get_driver()

        try:
            self.current_driver.get(url)
            self.load_cookies()

            if (
                "google.com/sorry" in self.current_driver.current_url
                or "google.com/recaptcha" in self.current_driver.current_url
            ):
                raise WebDriverException("Google CAPTCHA encountered")

            return True
        except TimeoutException:
            print(f"Timeout while loading {url}")
            return False
        except WebDriverException as e:
            print(f"WebDriver error: {e}")
            return False

    def save_cookies(self) -> None:
        os.makedirs(os.path.dirname(self.cookies_path), exist_ok=True)
        with open(self.cookies_path, "wb") as f:
            pickle.dump(self.current_driver.get_cookies(), f)

    def load_cookies(self) -> None:
        try:
            with open(self.cookies_path, "rb") as f:
                cookies = pickle.load(f)
            for cookie in cookies:
                if "expiry" in cookie:
                    del cookie["expiry"]
                self.current_driver.add_cookie(cookie)
            self.current_driver.refresh()
        except FileNotFoundError:
            print(
                f"No cookies file found at {self.cookies_path}. Proceeding without cookies."
            )
        except Exception as e:
            print(f"Error loading cookies: {e}")
