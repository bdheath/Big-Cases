import dbconnect
from twython import Twython
import re
from documentcloud import DocumentCloud
import requests
from io import BytesIO
from bigcases_settings import settings
import bigcases_list


class caseShare:

	VERBOSE = True

	# List of  filing types that should not be tweeted (because they're routine and seldom interesting)
	DONOTTWEET = ['Notice of Appearance','Pro Hac Vice', 'Appear Pro Hac Vice',  'Appearance', 'LCvR 7.1 Certificate of Disclosure - Corporate Affiliations/Financial Interests']
	
	tw = Twython(
		settings.twitter_app_key,
		settings.twitter_app_secret,
		settings.twitter_oauth_key,
		settings.twitter_oauth_secret
	)
	
	db = dbconnect.db(host=settings.db_host, user=settings.db_user, pwd=settings.db_pass, port=settings.db_port)
	dc = DocumentCloud(settings.dc_user, settings.dc_pass)

	# Re-arrange list of big cases into a dict with a unique ID 
	bigcases = dict((item['court']+item['case_number'], item) for item in bigcases_list.cases)

	
	def __init__(self):
		if self.VERBOSE:
			self.bigCasesMessage()
		self.listNew()
		return
	
	def listNew(self):
		# List new filings in selected cases that haven't been tweeted yet
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
		# Update a case after it's tweeted
		self.db.run(""" UPDATE court.pacer_raw
				SET bigcase = 2
				WHERE pid = %s """,
				(case['pid'], ))

	def twitter_upload(self, image_list):
		# Upload images of first four pages
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
		# Post a new filing to Twitter
		uid = case['court'] + case['case_number']
		DP1 = re.compile('\[(.*?)\].*?<a href="(.*?)"', re.IGNORECASE)
		DP2 = re.compile('\[(.*?)\]', re.IGNORECASE)
		d = case['description']
		media_ids = []
		typ = DP2.search(d).group(1)
		if case['dcid'] is not None:
			# Best case: We have the document on DC, and probably attached images
			link = case['document_location']
			nd = DP2.search(d).group(1) + '\n\n' + link
			doc = self.dc.documents.get(case['dcid'])
			images = doc.normal_image_url_list[:4]
			if len(images) > 0:
				media_ids = self.twitter_upload(images)
			
		elif DP1.search(d):
			# If the document ahsn't maded it to DC, send the PACER link
			link = DP1.search(d).group(2)
			nd = DP1.search(d).group(1) + '\n\nDoc. on PACER: ' + link
		elif DP2.search(d):
			# If there is no document, send a link to the PACER docket for the case
			nd = DP2.search(d).group(1) + '\n\nPACER Docket: ' + case['link']
		else:
			nd = False		
		if nd:	
			if typ not in self.DONOTTWEET:
				msg = 'New filing in %s: %s' % (self.bigcases[uid]['name'], nd )
				try:
					if len(media_ids) > 0:
						self.tw.update_status(status = msg, media_ids = media_ids)
					else:
						self.tw.update_status(status = msg)
				except Exception, e:
					print '##' + str(e)
					pass

		return

	def bigCasesMessage(self):
		print '# Checking for new filings in: '
		for case in bigcases_list.cases:
			print '  -> %s (%s, %s)' % (case['name'], case['court'], case['case_number'])

		
s = caseShare()
