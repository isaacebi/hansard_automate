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
import fitz
import time
import os
import re
import shutil
import requests

# %%
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

def get_seat(LANGUAGE='en', SEARCH='List_of_Malaysian_electoral_districts'):
    """Get parliment seat from wiki

    Args:
        LANGUAGE (str, optional): Wikipedia language. Defaults to 'en'.
        SEARCH (str, optional): Malaysia electrocal districts search. Defaults to 'List_of_Malaysian_electoral_districts'.
    """
    def get_seat(page):
        seat = []
        links = page.links
        for title in links.keys():
            if "federal constituency" in title:
                seat.append(title)

        return seat

    

    seat = []

    while not bool(seat):
        try:
            wiki_wiki = wikipediaapi.Wikipedia(LANGUAGE)
            page_py = wiki_wiki.page(SEARCH)
            seat = get_seat(page_py)
            seat = [seatClean.split('(')[0].strip().lower() for seatClean in seat]

        except:
            seat = []
            time.sleep(5)

    return pd.DataFrame({'seat': seat})


# %%
external_info = {
    'month_bm_to_eng': month_translate,
    'parliment_seat': get_seat()
}

# %%
def checkFolder(path):
    ifExist = os.path.exists(path)
    if not ifExist:
        os.makedirs(path)

def attendance(filePath, seat):

    if not isinstance(seat, list):
        raise Exception("Please check the 'seat' values")

    fileName = os.path.basename(filePath)
    sessionDate = fileName.split('.')[0]
    sessionDate = sessionDate.split('-')[2]


    pdf = fitz.open(filePath)

    # get text
    texts = []

    for page in pdf:
        text = page.get_text('xhtml', flags=True)
        text = " ".join(text.split())
        texts.append(text)

    texts = " ".join(texts)

    patterns = [
        '(<[^b]>)|(<\/[^b]>)',
        '(<.[^b]>)|(<\/.[^b]>)',
        '<b>\s<\/b>',
        '<b>Senator.*?<\/b>',
        '<div id="page0">',
        '<\/div>'
    ]

    for pattern in patterns:
        texts = re.sub(pattern, '', texts)

    # delete extra space
    texts = " ".join(texts.split())

    patterns = [
        '&apos;',
        '&#x2013;',
        '&#x2019;',
        'DR.\d{1,2}.\d{1,2}.\d{2,4}',
        '<b>.\s<\/b>',
        '&#x201c;',
        '<\/b>-<b>'
    ]

    replacement = [
        "'",
        "-",
        "'",
        '',
        '.',
        "'",
        '-'
    ]
    #print(texts)
    for i in range(len(patterns)):
        texts = re.sub(patterns[i], replacement[i], texts)
    #print(texts)
    
    # delete extra space
    texts = " ".join(texts.split())
    
    patterns = [
        'ahli-ahli dewan rakyat.*?dewan rakyat',
        'yang hadir.*?tidak hadir'
    ]
    for pattern in patterns:
        pageAttendance = re.findall(pattern, texts.lower())

        if pageAttendance:
            # by default all mp tidak hadir
            currentSeat = dict.fromkeys(seat, 0)
            pageAttendance = pageAttendance[0]

            patterns = [
                'ipoh timur',
                'tanjong piai',
                'johor baru'
            ]

            replacement = [
                'ipoh timor',
                'tanjung piai',
                'johor bahru'
            ]

            for i in range(len(patterns)):
                pageAttendance = re.sub(patterns[i], replacement[i], pageAttendance)

            for mp in currentSeat:
                if mp in pageAttendance:
                    currentSeat[mp] = 1

            currentSeat = pd.DataFrame(currentSeat, index=[0]).T
            currentSeat.columns = [sessionDate]

            break

    if not pageAttendance:
        print('No Attendance Page. Recheck PDF or code review')
        # by default all mp tidak hadir
        currentSeat = dict.fromkeys(currentSeat, np.nan)
        currentSeat = pd.DataFrame(currentSeat, index=[0]).T
        currentSeat.columns = [sessionDate]

    return currentSeat

class automate_hansard:
    def __init__(self, parentPath, URL):
        self.parentPath = parentPath
        self.URL = URL

    def hansard_date(self, headless=True):
        """Get all hansard date starting from PRU 12 (2008) till latest

        Args:
            parentPath (string): main directory
            headless (bool, optional): if False will show Selenium automation. Defaults to True.
        """
        # folder pathing

        RESULTS = os.path.join(self.parentPath, 'results')
        PDF = os.path.join(RESULTS, 'pdf')

        # file pathing
        DR_DATE = os.path.join(RESULTS, 'dr_date.csv')

        # list for iteration in creation folder - initial stage
        listFolder = [RESULTS, PDF]

        # create folder
        for folder in listFolder:
            checkFolder(folder)

        # headless browser
        options = Options()
        options.headless = True

        # create 'FireFox' Webdriver Object
        if headless:
            driver = webdriver.Firefox(options=options, executable_path=GeckoDriverManager().install())
        elif not headless:
            driver = webdriver.Firefox(executable_path=GeckoDriverManager().install())

        # get Website
        driver.get(self.URL)

        try:
            # wait for element to show else website may changes / internet slow / ip blocked
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]"))
            )

            # sleep 5 seconds
            time.sleep(5)

            # scroll down to imitate human action - website has bot tracker
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

            # sleep
            time.sleep(3)

            # locate parlimen in drop down tables - dynamic component
            tables1 = element.find_elements_by_xpath('/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr')

            # iterate to click main table
            for i in range(2, len(tables1)+1):
                # parlimen element
                parlimen = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr/td[4]')

                # stopping criteria till PRU 12 (2008)
                trigger = "parlimen kesebelas"
                flagKeduaBelas = " ".join(parlimen.text.lower().split())
                if trigger in flagKeduaBelas:
                    break

                # click parliment element
                parlimen.click()

                time.sleep(2)

                # find nested tables - penggal
                tables2 = element.find_elements_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr')
                
                # iterate nested tables - penggal
                for j in range(2, len(tables2)+1):
                    # penggal element
                    element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr/td[4]').click()

                    time.sleep(1)

                    # scroll down to imitate human action - website has bot tracker
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

                    # find nested tables - mesyuarat
                    tables3 = element.find_elements_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr')

                    # iterate nested tables - mesyuarat
                    for k in range(2, len(tables3)+1):
                        # mesyuarate element
                        element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr[{k}]/td[2]/table/tbody/tr/td[4]').click()
                        
                        time.sleep(2)

                        # scroll down to imitate human action - website has bot tracker
                        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")                    


            # empty list template to store Dewan Rakyat (DR) date
            list_date = []
            
            # get all span elements
            spans = driver.find_elements_by_tag_name('span')

            # filter each span element to find only text with format (2digit-sometext-4digit)
            for span in spans:
                # get span text
                text = span.text

                if "-" in text:
                    # skip iteration
                    continue

                # regex-ing for date type format
                text = re.findall('\d{1,2}\s\w.*?\s\d{4}', text)

                # if date, append to list_date
                if text:
                    list_date.append(text[0])

            # cleaning date for appropriate format
            dr_dates = []
            
            # iterate over uncleaned list_date
            for dr in list_date:
                # make sure no extra space between each words
                dr = dr.lower().split()

                # bm -> eng month translation
                dr[1] = month_translate[dr[1]]

                # recombine whole date with '-' seperator
                dr = "-".join(dr)

                # change to desired date format
                dr = datetime.strptime(dr, '%d-%B-%Y')

                # cleaned date to list
                dr_dates.append(dr)

            # create dataframe - from latest to oldest
            df = pd.DataFrame(sorted(dr_dates, reverse=True), columns=['date'])
            
            # change to date time
            df['date'] = pd.to_datetime(df['date'])
            #df.sort_values(by='date', ascending=False, inplace=True)

            # from Y/m/d -> d/mY
            df['dr_url'] = df['date'].dt.strftime('%d%m%Y')

            # create unique key for PDF URL
            df['dr_url'] = df['dr_url'].apply(lambda x: f"DR-{x}")

            # create ranking system
            numberItems = []
            for i in range(1, len(df)+1):
                if len(str(i)) != len(str(len(df))):
                    numberItems.append(f"{'0'*(len(str(len(df)))-len(str(i)))}{i}")
                else:
                    numberItems.append(f"{i}")

            # insert ranking system to dataframe
            df['fileName'] = pd.DataFrame(numberItems)
            df['fileName'] = df['fileName'].astype(str) + "-" + df['dr_url']    

            # csv file dr_date
            try:
                df_stored = pd.read_csv(DR_DATE)
            except:
                df_stored = pd.DataFrame()

            # check if changes
            isSame = df_stored.equals(df)

            if not isSame:
                df.sort_values(by='date', ascending=False).to_csv(DR_DATE, index=False)
                
                # # download pdf *performance wise might do parallel but worried on getting flaged
                # download_pdf(PDF, df)

        finally:
            driver.quit()

        return df

    def DED(self, df):
        TEMP = os.path.join(self.parentPath, 'TEMP')
        CSV = os.path.join(TEMP, 'temporary.csv')

        # create folder
        checkFolder(TEMP)

        seat = get_seat()
        
        if seat.empty:
            print(seat)

        listSeat = seat['seat'].tolist()

        records = pd.DataFrame()
        records.index = listSeat

        # counter
        count = len(df)

        while count != 0:
            # maybe do parallel tasking however will ip be banned? *need more research on hansard protocol
            try:
                # tracker
                listDone = records.columns.tolist()

                # iterate  rows dataframe
                for item in df.iterrows():
                    flagDone = item[1]['dr_url'].split('-')[1]

                    # in each row, for URL cols
                    session = item[1]['dr_url']

                    if flagDone in listDone and not records.empty:
                        flagNan = records[flagDone].isnull().values.any()

                        if not flagNan:
                            print(f"{session} was extracted")
                            continue                    

                    # PDF URL - has many variation
                    url_hansard = [
                        f"https://www.parlimen.gov.my/files/hindex/pdf/{session}.pdf",
                        f"https://www.parlimen.gov.my/files/hindex/pdf/{session}.pdf%20baru.pdf",
                        f"https://www.parlimen.gov.my/files/hindex/pdf/{session}%20new.pdf",
                        f"https://www.parlimen.gov.my/files/hindex/pdf/{session}i.pdf",
                        f"https://www.parlimen.gov.my/files/hindex/pdf/{session}..pdf",
                        f"https://www.parlimen.gov.my/files/hindex/pdf/{session}%20_2_.pdf",
                        f"https://www.parlimen.gov.my/files/hindex/pdf/{session}%20_1_.pdf",
                        f"https://www.parlimen.gov.my/files/hindex/pdf/{session}_2_.pdf"
                    ]

                    
                    # using fileName in dataframe
                    fileName = item[1]['fileName']

                    # pathing file - PDF
                    filePath = os.path.join(TEMP, fileName+".pdf")

                    for url in url_hansard:
                        try:
                            r = requests.head(url)
                            r = dict(r.headers)

                            if 'pdf' in r['Content-Disposition']:
                                # tracker
                                print(f"Currently extracting {fileName}")

                                # get PDF
                                urllib.request.urlretrieve(url, filePath)
                                
                                # sleep 10 seconds - dont ask me why 10 seconds
                                time.sleep(10)

                                # if fail open, delete file
                                try:
                                    record = attendance(filePath, listSeat)
                                    record.index = listSeat
                                    records = pd.concat([records, record], axis=1)
                                    os.remove(filePath)
                                    break
                                except:
                                    os.remove(filePath)         

                        except:                 
                            time.sleep(10)
                    
            # hansard features filtering bot
            except URLError as e:
                print(f"URLError occurs on {fileName}, maybe been partial block by website \n take a 2 minutes breaks")

                time.sleep(120) # sleep 10 seconds

            finally:
                # counting
                innerCount = 0

                records = records.drop_duplicates()
                innerCount = len(records.columns)

                if innerCount >= count:
                    count = 0   

        os.rmdir(TEMP)
        return records.reset_index().rename(columns={'index':'seat'})
    
