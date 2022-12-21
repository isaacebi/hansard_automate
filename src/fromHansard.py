# %%
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from urllib.error import URLError
from selenium import webdriver
from datetime import datetime
import urllib.request
import pandas as pd
import wikipediaapi
import numpy as np
import warnings
import fitz
import time
import os
import re
import shutil
import requests
import random

# %%
# bm -> eng [month]
month_translate = {
    'januari': 'January',
    'februari': 'February',
    'mac': 'March',
    'april': 'April',
    'mei': 'May',
    'jun': 'June',
    'julai': 'July',
    'ogos': 'August',
    'september': 'September',
    'oktober': 'October',
    'november': 'November',
    'disember': 'December'
}

# %%
def checkFolder(path):
    ifExist = os.path.exists(path)
    if not ifExist:
        os.makedirs(path)

def toDF(list_date, parlimen, penggal, mesyuarat):
    dr_dates = []
    for dr in list_date:
        dr = dr.lower().split()
        dr[1] = month_translate[dr[1]]
        dr = "-".join(dr)
        dr = datetime.strptime(dr, '%d-%B-%Y')
        dr_dates.append(dr)

    arkib = {
        'parlimen': parlimen,
        'penggal': penggal,
        'mesyuarat': mesyuarat,
        'sesi': [dr_dates]
    }

    df = pd.DataFrame(arkib)
    df['url'] = df['sesi'].apply(lambda x: [f"DR-{item.strftime('%m%d%Y')}" for item in x])
    return df

# %%
class Scrape:
    def __init__(self, parentPath, URL) -> None:
        self.parentPath = parentPath
        self.URL = URL

    def hansard_session(self, headless=True):
        # empty df
        df = pd.DataFrame() 

        # headless browser
        options = Options()
        options.headless = True

        # create 'FireFox' Webdriver Object
        if headless:
            driver = webdriver.Firefox(options=options, executable_path=GeckoDriverManager().install())
        elif not headless:
            driver = webdriver.Firefox(executable_path=GeckoDriverManager().install()) 

        driver.get(self.URL)

        time.sleep(random.randint(5,10))
        driver.refresh()

        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]"))
            )

            # sleep 5 seconds
            time.sleep(5)

            # scroll down
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # sleep
            time.sleep(random.randint(3,30))

            # find 'Show all' Button Using 'XPath'
            tables1 = element.find_elements_by_xpath('/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr')

            # iterate to click main table
            for i in range(2, len(tables1)+1):

                parlimen = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr/td[4]').text

                trigger = "parlimen kesebelas"
                flagKeduaBelas = " ".join(parlimen.lower().split())
                if trigger in flagKeduaBelas:
                    break

                toClick1 = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[1]/td[1]')
                toClick1.click()
                time.sleep(random.randint(5,10))

                # find nested tables
                tables2 = element.find_elements_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr')
                
                for j in range(2, len(tables2)+1):
                    penggal = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr/td[4]').text
                    toClick2 = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr[1]/td[1]')
                    toClick2.click()
                    time.sleep(random.randint(5,10))

                    # find nested tables
                    tables3 = element.find_elements_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr')

                    for k in range(2, len(tables3)+1):
                        mesyuarat = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr[{k}]/td[2]/table/tbody/tr/td[4]').text
                        toClick3 = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr[{k}]/td[2]/table/tbody/tr[1]/td[1]')
                        toClick3.click()
                        time.sleep(random.randint(5,10))


                        # get 'HTML' Content of Page
                        list_date = []
                        spans = driver.find_elements_by_tag_name('span')
                        for span in spans:
                            text = span.text

                            if "-" in text:
                                # skip iteration
                                continue

                            text = re.findall('\d{1,2}\s\w.*?\s\d{4}', text)
                            if text:
                                list_date.append(text[0])

                        single_df = toDF(list_date, parlimen, penggal, mesyuarat)
                        df = pd.concat([df, single_df], ignore_index=True)
                        time.sleep(random.randint(3,30))

                        toClick3.click()
                        time.sleep(1)
                    toClick2.click()
                    time.sleep(1)
                toClick1.click()
                time.sleep(1)
                            

        finally:
            driver.quit()

        # folder
        RESULTS = os.path.join(self.parentPath, 'results')
        PDF = os.path.join(RESULTS, 'pdf')
        ARKIB = os.path.join(RESULTS, 'arkib.csv')

        # store folder
        listFolder = [RESULTS, PDF]

        # create folder
        for folder in listFolder:
            checkFolder(folder)

        # create subfolder
        df['path'] = df['parlimen'].str.cat(df[['penggal', 'mesyuarat']], sep=',')
        df['path'] = df['path'].apply(lambda x: x.split(','))
        df.to_csv(ARKIB, index=False)

        return df

    def groupSessionURL(self, df):
        SESSION = os.path.join(self.parentPath, 'results', 'sorted_session.csv')

        grouped = df.groupby('parlimen')['url'].sum()

        sorted_session = []
        for i in range(len(grouped)):
            session = {
                'parlimen': grouped.index[i],
                'session': grouped[i]
            }
            sorted_session.append(session)

        sorted_session = pd.DataFrame(sorted_session)
        sorted_session.to_csv(SESSION)
        
        return sorted_session