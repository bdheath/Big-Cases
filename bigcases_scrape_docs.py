import dbconnect
import glob
import os
import re
import shutil
import time

from bigcases_settings import settings
from documentcloud import DocumentCloud
from recapupload import RecapUpload
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.keys import Keys
from urlparse import urljoin
from xvfbwrapper import Xvfb

waittime = 10

# Configure the headless browser so that it forces downloads 
br = ''
chrome_options = Options()
chrome_options.add_argument("--disable-extensions")
chrome_options.add_argument("--disable-print-preview")
profile = {
	'download.default_directory': settings.file_temp_path,
	'download.prompt.for.download': False,
	'download.directory_upgrade':True,
	'plugins.plugins_disabled': ['Chrome PDF Viewer']
}
chrome_options.add_experimental_option('prefs',profile)



START = 'https://pacer.login.uscourts.gov/csologin/login.jsf?appurl=pcl.uscourts.gov/search'
ACCESS = 'public'

URL = re.compile('"(http.*?)"', re.IGNORECASE)
COSTS =[
	re.compile('Cost: </FONT></TH><TD ALIGN=LEFT><FONT SIZE=-1 COLOR=DARKBLUE>(.*?)<', re.IGNORECASE), 
	re.compile('Cost: </font></th><td align="LEFT"><font size="-1" color="DARKBLUE">(.*?)<', re.IGNORECASE),
	re.compile('Cost: .{50,80}>([\s\d\.]{3,7})<', re.IGNORECASE)
]	

dc = DocumentCloud(settings.dc_user, settings.dc_pass)
db = dbconnect.db(host=settings.db_host, user=settings.db_user, pwd=settings.db_pass, port=settings.db_port)

def handleLogin():
	print "# Renewing login"
	global br
	br.get(START)
	br.find_element_by_name('login:loginName').send_keys(settings.pacer_user)
	br.find_element_by_name('login:password').send_keys(settings.pacer_pass)
	br.find_element_by_name('login:clientCode').send_keys(settings.pacer_client)
	br.find_element_by_name('login:clientCode').send_keys(Keys.RETURN)
	time.sleep(3)
	
def getDocument(case, url):
	global waittime
	global br

	pid = case['pid']

	br.get(url)
	time.sleep(2)
	html = br.page_source

	if re.search('<input\s+type=password', html, re.IGNORECASE):
		# logged out somehow
		print '# Oops, have to login again'
		handleLogin()
		br.get(url)	
		time.sleep(2)
		html = br.page_source
	
	if re.search('View All',  html):
		# Multiple documents on this entry. Try to get them all as a single document if you can
		br.find_element_by_xpath("//input[@value='View All']").click()
		time.sleep(4)
		waittime += 10
		html = br.page_source
	
	MULTIPATTERN = re.compile('<td colspan=\"?2\"?><b>Document Number:</b> <a.*?>(\d+)<', re.IGNORECASE)
	if MULTIPATTERN.search( html):
		# Document with multiple attachments, but cannot view all
		# Get the main document only
		xp = MULTIPATTERN.search(html).group(1)
		xpath = "//a[text()='" + xp + "']"
		br.find_element_by_xpath(xpath).click()
		time.sleep(4)
		html = br.page_source
		
		
	price = None
	for COST in COSTS:
		if COST.search(html):
			price = float(COST.search(html).group(1))
			break
	
	print '   - price: ' + str(price)
	
	# Now fetch the document if its price is less than the max cost
	if price <= settings.pacer_max_price and price is not None:
		print '   - extract'
		#br.find_element_by_xpath("//input[@type='submit']").click()
		br.find_element_by_xpath("//input[@value='View Document']").click()
		
		time.sleep(waittime)
		
		# Now fish out the most recent file and stick it where you want it
		
		files = glob.glob(settings.file_temp_path + '/*')
		files.sort(key=os.path.getmtime, reverse=True)
		if len(files) >= 2:
			newfn = settings.file_archive_path + '/document-' + str(pid) + '.pdf'
			print '   - now: ' + newfn
			shutil.move(files[0], newfn)
			
			dcid = None

			# source isn't publicly visible; description is public & free-form text.
			dcdoc = dc.documents.upload(
				newfn,
				source='U.S. District Court via big_cases bot',
				description='%s in %s (%s, %s) dated %s from %s' % (
					case['description'], case['title'], case['case_number'],
					case['court'], case['pubdate'], case['link']),
				project = settings.dc_project_id,
				access = ACCESS)
			
			print '   - DocumentCloud: ' + str(dcdoc.id)
			
			# Flag bigcase = 3
			# This means the document is processing - do not post it
			# Flag reverts to 1 after document upload is complete
			db.run(""" UPDATE court.pacer_raw
					SET modified = modified,
						scraped = 1,
						scraped_time = NOW(),
						dcid = %s,
						document_location = %s,
						price = %s,
						bigcase = 3
					WHERE pid = %s """,
					(dcdoc.id, str(dcdoc.published_url), price, pid, ))

                        # While DocumentCloud processes the document, upload it to RECAP
                        recap = RecapUpload(newfn,
                                            case['case_number'],
                                            case['title'],
                                            case['pubdate'],
                                            case['description'])

			# Wait until the document is public
			obj = dc.documents.get(dcdoc.id)
			while obj.access != 'public':
				print '   - Pausing for document to become public (%s) ' % obj.access
				time.sleep(5)
				obj = dc.documents.get(dcdoc.id)

			# Re-flag the docket entry in the database as ready to post
			db.run(""" UPDATE court.pacer_raw
					SET bigcase = 1
					WHERE pid = %s """, (pid, ))
				
	return

	
if __name__ == '__main__':
	print '# PACER DOCUMENT DOWNLOADER '
	
	print '# Querying new records'
	# Now get the latest relevant documents

	cases = db.getDict(""" SELECT *
						FROM court.pacer_raw
						WHERE bigcase = 1
							AND description LIKE %s
							AND scraped = 0
						ORDER BY pid DESC
						LIMIT %s """, 
					('%http%', settings.max_files_to_scrape, ))

	if len(cases) > 0:
		try:
			print '# Starting Chrome'
			display = Xvfb()
			display.start()
			br = webdriver.Chrome( chrome_options = chrome_options)
			br.set_page_load_timeout(settings.http_timeout)
			handleLogin()

						
			for case in cases:
				url = URL.search(case['description'])
				if url:
					print ' - ' + case['title'] + ' (' + case['court'] + ')'
					getDocument(case, url.group(1))
				
			br.quit()
			display.stop()
		except Exception, e:
			with open('bigcases_scrape.log','a') as logfile:
				logfile.write('ERROR: %s\n' % str(e) )
			br.quit()
			display.stop()
