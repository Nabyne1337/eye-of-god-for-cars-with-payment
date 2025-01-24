from selenium import webdriver
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
import time
import re
import sys

driver = None

def determine_type(input_string):
    if re.match(r'^[A-HJ-NPR-Z0-9]{17}$', input_string):
        return "VIN"
    elif re.match(r'^[A-Z0-9\-]{6,17}$', input_string):
        return "BODY"
    elif re.match(r'^[АВЕКМНОРСТУХ]{1}\d{3}[АВЕКМНОРСТУХ]{2}\d{2,3}$', input_string):
        return "GZN"
    else:
        return None

def init_driver():
    global driver
    if driver is None:
        geckodriver_path = "geckodriver.exe"
        service = Service(executable_path=geckodriver_path)
        options = webdriver.FirefoxOptions()
        driver = webdriver.Firefox(service=service, options=options)
        driver.maximize_window()

def quit_driver():
    global driver
    if driver:
        driver.quit()
        driver = None

def wait_for_element(driver, timeout, by, value):
    try:
        return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))
    except TimeoutException:
        return None

def login_and_retry(driver, login, password, retries=3):
    for attempt in range(retries):
        email_input = wait_for_element(driver, 10, By.XPATH, '//*[@id="email"]//input')
        if email_input:
            email_input.clear()
            email_input.send_keys(login)
        
        password_input = wait_for_element(driver, 10, By.XPATH, '//*[@id="password"]//input')
        if password_input:
            password_input.clear()
            password_input.send_keys(password)

        login_button = wait_for_element(driver, 10, By.XPATH, '/html/body/div/div[1]/div/div/div/div[2]/form/button/span')
        if login_button:
            login_button.click()

        time.sleep(2)
        if "home" in driver.current_url:
            return True
        
        driver.refresh()
    
    return False

def parse_data(number_auto):
    login = ""
    password = ""
    data_type = determine_type(number_auto)
    if not data_type:
        return None, "Неверный формат данных."

    init_driver()

    driver.get("https://profi.avtocod.ru")

    if not login_and_retry(driver, login, password):
        driver.quit()
        return None, "Не удалось войти."

    if data_type == "VIN":
        driver.get(f"https://profi.avtocod.ru/reports/check-auto?type=VIN&query={number_auto}&fromUrl=%2Freports")
    elif data_type == "BODY":
        driver.get(f"https://profi.avtocod.ru/reports/check-auto?type=BODY&query={number_auto}&fromUrl=%2Freports")
    elif data_type == "GZN":
        driver.get(f"https://profi.avtocod.ru/reports/check-auto?type=GRZ&query={number_auto}&fromUrl=%2Freports")
    
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    button_wait = wait_for_element(driver, 10, By.XPATH, '/html/body/div[1]/div[1]/main/div/div/div[2]/div[4]/button')
    if button_wait:
        button_wait.click()

    try:
        time.sleep(1.5)
        WebDriverWait(driver, 60).until(
            EC.invisibility_of_element_located(
                (By.XPATH, "//span[contains(text(),'Идёт сбор данных...')]")
            )
        )
        link_element = wait_for_element(driver, 10, By.XPATH, "//div[@data-v-1f0aebf0]//a")
        if link_element:
            href = link_element.get_attribute("href")
            if href:
                full_ur = href
                driver.get(full_ur)
                title_element = wait_for_element(driver, 10, By.XPATH, '//p[@class="text-display-10 report-header__title"]')
                title_text = title_element.text if title_element else "Заголовок не найден"
                content_values = driver.find_elements(By.XPATH, '//span[@class="text-body-10 content-line__value" or @class="text-body-10 content-line__value content-line__value--danger"]')
                content_texts = [value.text for value in content_values]
                additional_elements = driver.find_elements(By.XPATH, '//span[@class="content-line__text"]')
                additional_texts = [element.text for element in additional_elements]
                full_url = driver.current_url
                return title_text, content_texts, additional_texts, full_url
    finally:
        time.sleep(2)
        quit_driver()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Ошибка: Не указан ID автомобиля.")

    number_auto = sys.argv[1]
    title, number = parse_data(number_auto)
