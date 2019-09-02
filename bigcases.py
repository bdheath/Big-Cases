import urllib2
import MySQLdb
import re
from bs4 import BeautifulSoup
import multiprocessing
import feedparser
from pacer_rss_feeds import courts
from io import BytesIO
import requests
import sys
import bigcases_list
import random

multitask = False
threads = 4
TIMEOUT = 30.0

TITLEPATTERN = re.compile('^(.*?) (.*?)', re.IGNORECASE)
	
db = MySQLdb.connect('localhost','USERNAME','PASSWORD','court').cursor(MySQLdb.cursors.DictCursor)

def checkUSV(t, d, c):
	usv = 0
	flags = [
		re.compile('\d{4,}\s+USA\s+v. ', re.IGNORECASE),
		re.compile('\d{4,}\s+United\s+States\s+v.\s+', re.IGNORECASE),
		re.compile('\d{4,}\s+United\s+States\s+of\s+America\,*\s+v.\s+', re.IGNORECASE),
		re.compile('\d{4,}\s+US\s+v. ', re.IGNORECASE),
		re.compile('\d{4,}\s+U\.S\.A\.\s+v. ', re.IGNORECASE),
	]
	if c is not None:
		if '-cv-' in c:
			for flag in flags:
				if flag.search(t):
					usv = 1
					if '[Complaint' in d:
						usv = 2
					break
	
	return usv

def checkFlags(t, d):
	pf = None

	return pf

def bigCaseList():
	l = []
	for case in bigcases_list.cases:
		l.append(case['court'] + case['case_number'])
	return l
	
def checkBigCase(court, case_number):
#	print bigcases
	bigcase = 0
	if case_number is not None:
		if court + case_number in bigcases:
			bigcase = 1
		else:
			bigcase = 0
	return bigcase

def checkObserved(court, case_number, title, link):
	# Check whether this case already exists in the pacer_observed table
	# First apply some rules based on what will be interesting
	if case_number is not None:
		if '-cr-' in case_number or '-ms-' in case_number or '-mis' in case_number \
			or '-sw-' in case_number or '-mc-' in case_number or '-mj-' in case_number \
			or '-ec-' in case_number or '-ml-' in case_number or '-gj-' in case_number:

			if court in('D.D.C.') \
				or ('grand jury sub' in title.lower() and court not in('E.D. Pa.','E.D. Mich.')) \
				or (('-sw-' in case_number or '-mc-' in case_number or '-ec-' in case_number or '-ms-' in case_number or '-mi' in case_number) and court in('C.D. Cal.', 'E.D. Pa.', 'S.D.N.Y.')):
				
					db.execute(""" SELECT COUNT(*) AS c
										FROM court.pacer_observed
										WHERE court = %s
											AND case_number = %s """,
									(court, case_number, ))
					c = db.fetchone()['c']
					if c == 0:

						db.execute(""" REPLACE INTO court.pacer_observed
										(court, case_number, title, detected, link)
									VALUES(%s, %s, %s, NOW(), %s) """,
									(court, case_number, title, link))
						db.execute(""" COMMIT """)

def processFeed(court):
	print "# QUERYING " + court['id']
	try:
		url = court['url'] + '?x=' + str(int(random.random() * 10000))
		rss = requests.get(court['url'], timeout = TIMEOUT)
		stream = BytesIO(rss.content)
		feed = feedparser.parse(stream)
	except Exception, e:
		print "#### " + str(e)
#		sys.exit(0)
		return False

#	db.execute(""" INSERT INTO log.scrape_log(t,v) VALUES(%s, %s) """, ('pacer-rss',court['id'],))
#	db.execute(""" COMMIT; """)
	
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
			pf = checkFlags(item.title, item.description)
			usv = checkUSV(item.title, item.description, case_number)
			bigcase = checkBigCase(court['id'], case_number)
			checkObserved(court['id'], case_number, item.title[:253], item.link)
			
			if pf == 1:
				print '    HIT: %s' % item.description
			db.execute(""" INSERT INTO court.pacer_raw(court, preflag, case_number, title, guid, modified, pubdate, description, link, bigcase, usv)
									VALUES(%s, %s, %s, %s, %s, NOW(), %s, %s, %s, %s, %s) """,
									(court['id'], pf, case_number, item.title[:253], item.guid, item.published, item.description, item.link, bigcase, usv))

def checkGuid(guid):
	db.execute(""" SELECT COUNT(*) AS c
							FROM court.pacer_raw
							WHERE guid = %s """, (guid, ))
	c = db.fetchone()['c']
	if c > 0:
		return True
	else:
		return False

def setStatus():
	db.execute(""" REPLACE INTO court.bigcases_status(k,v)
					VALUES(%s,%s)""",
					('last-feed','complete'))
		
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

	setStatus()
		
