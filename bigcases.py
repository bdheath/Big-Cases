import dbconnect
from twython import Twython
import bigcases_list
import re
from documentcloud import DocumentCloud
import requests
from io import BytesIO
from dbaccess import dbinfo
from slackclient import SlackClient

class caseShare:

	VERBOSE = True

	DONOTTWEET = ['Notice of Appearance','Pro Hac Vice', 'Appear Pro Hac Vice',  'Appearance', 'LCvR 7.1 Certificate of Disclosure - Corporate Affiliations/Financial Interests']
	
	DONOTTWEETRE = re.compile('(pro hac vice|notice of appearance|certificate of disclosure|corporate disclosure|add and terminate attorneys)', re.IGNORECASE)
	
	tw = Twython(

	)
	
	db = dbconnect.db()
	
	dc = DocumentCloud('EMAIL','PASS')

	ROOM = 'CF1RKUUAV'

	bigcases = dict((item['court']+item['case_number'], item) for item in bigcases_list.cases)

	
	def __init__(self):
		if self.VERBOSE:
			self.bigCasesMessage()
		self.listNew()
		return
	
	def listNew(self):
		cases = self.db.getDict(""" SELECT * 
						FROM court.pacer_raw
						WHERE bigcase = 1
						ORDER BY pid DESC
						LIMIT 100 """)
		for case in cases:
			self.share(case)
			self.update(case)
		return

	def update(self, case):
		self.db.run(""" UPDATE court.pacer_raw
				SET bigcase = 2
				WHERE pid = %s """,
				(case['pid'], ))

	def twitter_upload(self, image_list):
		media_ids = []

		for image in image_list:
			try:
				res = requests.get(image)
				res.raise_for_status()

				uploadable = BytesIO(res.content)

				response = self.tw.upload_media(media=uploadable)
				media_ids.append(response['media_id'])
			except:
				pass
		return media_ids
				
	def share(self, case):
		uid = case['court'] + case['case_number']
		DP1 = re.compile('\[(.*?)\].*?<a href="(.*?)"', re.IGNORECASE)
		DP2 = re.compile('\[(.*?)\]', re.IGNORECASE)
		d = case['description']
		media_ids = []
		typ = DP2.search(d).group(1)
		if case['dcid'] is not None:
			link = 'https://www.usatoday.com/documents/' + case['dcid']
			nd = DP2.search(d).group(1) + '\n\n' + link
			doc = self.dc.documents.get(case['dcid'])
			images = doc.normal_image_url_list[:4]
			if len(images) > 0:
				media_ids = self.twitter_upload(images)
			
		elif DP1.search(d):
			link = DP1.search(d).group(2)
			nd = DP1.search(d).group(1) + '\n\nDoc. on PACER: ' + link
		elif DP2.search(d):
			nd = DP2.search(d).group(1) + '\n\nPACER Docket: ' + case['link']
		else:
			nd = False		
		if nd:	

			# Post everything to slack
			print 'Sending to Slack'
			try:
				msg = 'TRACKED CASE: New filing in *%s*: %s' % (self.bigcases[uid]['name'], nd)
				#sc = SlackClient(dbinfo.sl_token_newsalertsbot)
				#sc.rtm_connect()
				#sc.rtm_send_message(self.ROOM, msg)
			except Exception, e:
				with open('/data/s/bigcases-err.log','a') as logfile:
					logfile.write('SLACK ERROR: ' + str(e) + '\n')

			if not self.DONOTTWEETRE.search(typ):
				msg = 'New filing in %s: %s' % (self.bigcases[uid]['name'], nd )
				try:
					if len(media_ids) > 0:
						self.tw.update_status(status = msg, media_ids = media_ids)
					else:
						self.tw.update_status(status = msg)
#					x = 0
				except Exception, e:
					print '##' + str(e)
					pass
				print '-----------------------------'
				print media_ids
				print '' + msg

		return

	def bigCasesMessage(self):
		print '# Checking for new filings in: '
		for case in bigcases_list.cases:
			print '  -> %s (No. %s, %s)' % (case['name'], case['case_number'], case['court'])

		
s = caseShare()
