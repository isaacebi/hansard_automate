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

# %%
# intended to create folder on initial stage
def checkFolder(path):
    ifExist = os.path.exists(path)
    if not ifExist:
        os.makedirs(path)

# %%
URL = 'https://www.parlimen.gov.my/hansard-dewan-rakyat.html?uweb=dr&arkib=yes'

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
    
def etl_attendance(resultsPath):
    seat = get_seat()
    listSeat = seat['seat'].tolist()

    records = pd.DataFrame()

    for root, dir, files in os.walk(resultsPath):
        if 'pdf' in root:     
            for file in files:
                print(file)
                filePDF = os.path.join(root, file)
                session = attendance(filePDF, listSeat)
                records = pd.concat([records, session], axis=1)

    return records.reset_index().rename(columns={'index':'seat'})

def download_pdf(pdfPath, df_dr):
    """To download hansard PDF file

    Args:
        pdfPath (string): string pathing
        df_dr (dataframe): dewan rakyat session
    """
    
    # record start time
    st = time.time()

    # counter
    count = len(df_dr)

    while count != 0:
        # maybe do parallel tasking however will ip be banned? *need more research on hansard protocol
        try:
            # iterate  rows dataframe
            for item in df_dr.iterrows():
                # in each row, for URL cols
                session = item[1]['dr_url']

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
                filePath = os.path.join(pdfPath, fileName+".pdf")

                # check file if exist
                isExist = os.path.exists(filePath)

                for url in url_hansard:
                    if not isExist:
                        # tracker
                        print(fileName)

                        # get PDF
                        urllib.request.urlretrieve(url, filePath)
                        
                        # sleep 10 seconds - dont ask me why 10 seconds
                        time.sleep(10)

                        # if fail open, delete file
                        try:
                            fitz.open(filePath)
                            break
                        except:
                            os.remove(filePath)                          
                    
                    # case of downloaded corrupt file
                    if isExist:             
                        # if fail open, delete file
                        try:
                            fitz.open(filePath)
                            break
                        except:
                            os.remove(filePath)

            # 
            for root, dir, files in os.walk(pdfPath):
                for file in files:
                    fileFlag = file.split('.')[0]
                    if fileFlag not in df_dr.fileName.tolist():
                        pathDelete = os.path.join(root, file)
                        os.remove(pathDelete)

                 
        # hansard features filtering bot
        except URLError as e:
            print(fileName) 
            print(e)

            et = time.time()
            elapsed_time = et - st

            if elapsed_time > 3600:
                count = 0        

            time.sleep(120) # sleep 10 seconds

        finally:
            # counting
            innerCount = 0

            # Iterate directory
            for path in os.listdir(pdfPath):
                # check if current path is a file
                if os.path.isfile(os.path.join(pdfPath, path)):
                    innerCount += 1

            if innerCount >= count:
                count = 0              

def etl_DED(filePath, seat, records):
    try:
        session = attendance(filePath, seat)
        records = pd.concat([records, session], axis=1)
        os.remove(filePath)
        return records

    except:
        os.remove(filePath)
        print('Something wong with', filePath)

def DED(df):
    TEMP = os.path.join(os.getcwd(), 'TEMP')
    CSV = os.path.join(TEMP, 'temporary.csv')

    # delete for manual stop cases
    shutil.rmtree(TEMP)

    # create folder
    checkFolder(TEMP)

    seat = get_seat()
    
    if seat.empty:
        print(seat)

    listSeat = seat['seat'].tolist()

    records = pd.DataFrame()

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
                        r = requests.head('https://www.parlimen.gov.my/files/hindex/pdf/DR-21032022.pdf')
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
                                fitz.open(filePath)
                                records = etl_DED(filePath, listSeat, records)
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
            #
            print(records)

            # counting
            innerCount = 0

            records = records.drop_duplicates()
            innerCount = len(records.columns)

            if innerCount % 100 == 0:
                records.to_csv(CSV, index=False)

            if innerCount >= count:
                count = 0   

    os.rmdir(TEMP)
    return records.reset_index().rename(columns={'index':'seat'})

# download - extract - delete
def etl_attendance_ex(resultsPath):

    def extract(filePath):
        pdf = fitz.open(filePath)
        # get start page
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
            '<b>Senator.*?<\/b>'
        ]

        for pattern in patterns:
            texts = re.sub(pattern, '', texts)

        patterns = [
            '&apos;',
            '&#x2013;',
            '&#x2019;',
            'DR.*?\d{4}\s',
            '<b>.\s<\/b>'
        ]

        replacement = [
            "'",
            "-",
            "'",
            '',
            '.'
        ]

        for i in range(len(patterns)):
            texts = re.sub(patterns[i], replacement[i], texts)

        pattern = 'ahli-ahli yang hadir.*?ahli-ahli yang tidak hadir'
        ahliHadir = re.findall(pattern, texts.lower())

        pattern = '</b>'
        ahliHadir = ahliHadir[0].split(pattern)[1]

        pattern = '<b>'
        ahliHadir = ahliHadir.split(pattern)[0]

        pattern = '\d{1,3}.'
        ahliHadir = re.sub(pattern, 'SPLIT ', ahliHadir)

        pattern = 'SPLIT'
        ahliHadir = ahliHadir.split(pattern)

        yangHadir = []
        for ahli in ahliHadir:
            ahli = " ".join(ahli.split())
            if ahli != '' and len(ahli.split()) > 2:
                ahli = ahli.replace('</div> <div id="page', '')

                if '-' in ahli:
                    data = ahli.split('-', 1)
                    nama = data[0]
                    seat = data[1]

                if '(' in ahli:
                    data = ahli.split('(')
                    nama = data[0]
                    seat = re.sub(r'[^a-zA-Z0-9\s]', '', data[1])

                if 'Senator' in ahli:
                    data = ahli.split('Senator ')
                    nama = data[1]
                    seat = 'Senator'

                hadir = {
                    'nama': nama,
                    'seat': seat,
                    'hadir': 1
                }
                yangHadir.append(hadir)

        yangHadir = pd.DataFrame(yangHadir)

        pattern = 'ahli-ahli yang tidak hadir.*?malaysia'
        ahlixHadir = re.findall(pattern, texts.lower())

        pattern = '</b>'
        ahlixHadir = ahlixHadir[0].split(pattern)[1]

        pattern = '<b>'
        ahlixHadir = ahlixHadir.split(pattern)[0]

        pattern = '\d{1,3}.'
        ahlixHadir = re.sub(pattern, 'SPLIT ', ahlixHadir)

        pattern = 'SPLIT'
        ahlixHadir = ahlixHadir.split(pattern)


        yangxHadir = []
        for ahli in ahlixHadir:
            ahli = " ".join(ahli.split())
            if ahli != '' and len(ahli.split()) > 2:
                ahli = ahli.replace('</div> <div id="page', '')

                if '-' in ahli:
                    data = ahli.split('-', 1)
                    nama = data[0]
                    seat = data[1]

                if '(' in ahli:
                    data = ahli.split('(')
                    nama = data[0]
                    seat = re.sub(r'[^a-zA-Z0-9\s]', '', data[1])

                if 'Senator' in ahli:
                    data = ahli.split('Senator ')
                    nama = data[1]
                    seat = 'Senator'

                hadir = {
                    'nama': nama,
                    'seat': seat,
                    'hadir': 0
                }
                yangxHadir.append(hadir)

        yangxHadir = pd.DataFrame(yangxHadir)

        recordSession = pd.concat([yangHadir, yangxHadir], ignore_index=True)

        return recordSession   

    records = pd.DataFrame()

    for root, dir, files in os.walk(resultsPath):
        if 'pdf' in root:     
            for file in files:
                print(file)
                filePDF = os.path.join(root, file)
                session = extract(filePDF)
                session.rename(columns={'hadir': file.split('.')[0]}, inplace=True)
                records = pd.concat([records, session])

    RECORD = os.path.join(resultsPath, 'attendance.csv')
    records.to_csv(RECORD, index=False)

def hansard_date(parentPath, headless=True):
    """Get all hansard date starting from PRU 12 (2008) till latest

    Args:
        parentPath (string): main directory
        headless (bool, optional): if False will show Selenium automation. Defaults to True.
    """
    # folder pathing
    RESULTS = os.path.join(parentPath, 'results')
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
    driver.get(URL)

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

def hansard_session(parentPath, headless=True):

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

    driver.get(URL)

    try:
        element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]"))
        )

        # sleep 5 seconds
        time.sleep(5)

        # scroll down
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")

        # sleep
        time.sleep(3)

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
            time.sleep(1)

            # find nested tables
            tables2 = element.find_elements_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr')
            
            for j in range(2, len(tables2)+1):
                penggal = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr/td[4]').text
                toClick2 = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr[1]/td[1]')
                toClick2.click()
                time.sleep(1)

                # find nested tables
                tables3 = element.find_elements_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr')

                for k in range(2, len(tables3)+1):
                    mesyuarat = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr[{k}]/td[2]/table/tbody/tr/td[4]').text
                    toClick3 = element.find_element_by_xpath(f'/html/body/div[4]/div/div/div[1]/div[2]/div/div/div[4]/div/div/table/tbody/tr[{i}]/td[2]/table/tbody/tr[{j}]/td[2]/table/tbody/tr[{k}]/td[2]/table/tbody/tr[1]/td[1]')
                    toClick3.click()
                    time.sleep(1)


                    # get 'HTML' Content of Page
                    list_date = []
                    spans = driver.find_elements_by_tag_name('span')
                    for span in spans:
                        text = span.text
                        text = re.findall('\d{1,2}\s\w.*?\s\d{4}', text)
                        if text:
                            list_date.append(text[0])

                    single_df = toDF(list_date, parlimen, penggal, mesyuarat)
                    df = pd.concat([df, single_df], ignore_index=True)
                    time.sleep(2)

                    toClick3.click()
                    time.sleep(1)
                toClick2.click()
                time.sleep(1)
            toClick1.click()
            time.sleep(1)
                        

    finally:
        driver.quit()

    # folder
    RESULTS = os.path.join(parentPath, 'results')
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
    
# %%
