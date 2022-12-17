# %%
import os
import time
from src import hansard

# %%
PARENT = os.getcwd()
RESULTS = os.path.join(PARENT, 'results')
PDF = os.path.join(RESULTS, 'pdf')

ATTENDANCE = os.path.join(RESULTS, 'attendance.csv')
ATTENDANCE2 = os.path.join(RESULTS, 'attendance2.csv')

# %%
import src.download_extract_delete as DED

automate = DED.automate_hansard(
    parentPath=PARENT,
    URL='https://www.parlimen.gov.my/hansard-dewan-rakyat.html?uweb=dr&arkib=yes'
)

dr = automate.hansard_date(headless=True)
attendance = automate.DED(dr)

# %%
# # get all available hansard date
# hansard.hansard_session(PARENT)

# # interval
# time.sleep(10)


# dr = hansard.hansard_date(PARENT, headless=False)

# # download
# hansard.download_pdf(PDF, dr)

# # 
# attendance = hansard.etl_attendance_ex(RESULTS)
# attendance.to_csv(ATTENDANCE, index=False)

# dr = hansard.hansard_date(PARENT, headless=False)
# attendance = hansard.DED(dr)

# attendance.to_csv(ATTENDANCE2, index=False)

# %%
