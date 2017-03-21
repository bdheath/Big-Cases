import re
import multiprocessing
import feedparser
from io import BytesIO
import requests
import sys
import dbconnect
import bigcases_list
from pacer_rss_feeds import courts
from bigcases_settings import settings

multitask = settings.multitask
threads = settings.multitask_threads
TIMEOUT = settings.http_timeout
TITLEPATTERN = re.compile('^(.*?) (.*?)', re.IGNORECASE)

db = dbconnect.db(host = settings.db_host, user=settings.db_user, pwd=settings.db_pass, port=settings.db_port)
	


def bigCaseList():
	l = []
	for case in bigcases_list.cases:
		l.append(case['court'] + case['case_number'])
	return l
	
def checkBigCase(court, case_number):
	if case_number is not None:
		if court + case_number in bigcases:
			return 1
	return 0

def processFeed(court):
	print "# QUERYING " + court['id']
	try:
		rss = requests.get(court['url'], timeout = TIMEOUT)
		stream = BytesIO(rss.content)
		feed = feedparser.parse(stream)
	except Exception, e:
		print "#### " + str(e)
		return False

	for item in feed.entries:
		m = re.search(TITLEPATTERN, item.title)
		if m:
			case_number = m.group(1)
		else:
			case_number = None
		if not checkGuid(item.guid):
			cn = case_number
			if cn is None:
				cn = ''
			print ' -> Adding to ' + court['id'] + ' ' + cn + ': %s' % item.description[:20]
			bigcase = checkBigCase(court['id'], case_number)
			pf = None
			db.run(""" INSERT INTO court.pacer_raw(court, preflag, case_number, title, guid, modified, pubdate, description, link, bigcase)
									VALUES(%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s) """,
									(court['id'], pf, case_number, item.title[:253], item.guid, item.published, item.description, item.link, bigcase))

def checkGuid(guid):
	c = db.getOne(""" SELECT COUNT(*) AS c
							FROM court.pacer_raw
							WHERE guid = %s """, (guid, ))
	if c > 0:
		return True
	else:
		return False

if __name__ == '__main__':
	bigcases = bigCaseList()
	
	if multitask:
		pool = multiprocessing.Pool(processes=threads)
	for court in courts:
		if multitask:
			pool.apply_async(processFeed, args=(court, ))
		else:
			processFeed(court)
	if multitask:
		pool.close()
		pool.join()
