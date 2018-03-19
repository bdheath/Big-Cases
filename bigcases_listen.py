import dbconnect
import json
import random
import re
from bigcases_settings import settings
from pacer_rss_feeds import courts
from twython import Twython

APPROVED = ['', ]

NOTAPPROVED = ['Who dares disturb my slumber?', 
				'Nope. (But suggestions by DM are appreciated.)', 
				'Sorry, no.', ]

FOLLOWPATTERN = re.compile('follow (.*?),? No. (.*?)\s{0,}(,|in|at) (.*?)[\?\,\!]{0,}$', re.IGNORECASE)
FOLLOW = re.compile('^.{0,30} follow ', re.IGNORECASE)

db = dbconnect.db(host=settings.db_host, user=settings.db_user, pwd=settings.db_pass, port=settings.db_port)

case_file = open('bigcases.json')
case_data = json.load(case_file)
cases = case_data['cases']
cases_sct = case_data['supreme_court_cases']

# Check whether this case is already on the list
def check_case(case_number, court, sender):
	for c in cases:
		if c['case_number'] == case_number and c['court'] == court:
			return '@%s Good news! I already follow %s, No. %s (%s)' % (sender, c['name'], c['case_number'], c['court'])
	return 'new'

# Check on availability of records for this court. Return either a sorry message, a data note or nothing.
def check_court(court, sender):
	ct = any(a['id'] == court for a in courts)
	if not ct:
		return '@%s Sorry, I don\'t have a good data feed for %s yet so I can\'t follow the case.' % (sender, court)
	else:
		for c in courts:
			if c['id'] == court:
				if 'data_note' in c:
					return '(%s)' % c['data_note']
				else:
					return ''
				break
				
	
if __name__ == '__main__':


	tw = Twython(
		settings.twitter_app_key,
		settings.twitter_app_secret,
		settings.twitter_oauth_key,
		settings.twitter_oauth_secret
	)
	
	mentions = tw.get_mentions_timeline(count = 100)
	
	for mention in mentions:
		
		if db.getOne(""" SELECT COUNT(*) 
					FROM court.bigcases_mentions
					WHERE id = %s """, (mention['id'], )) == 0:
			
			# This is a mention we have not seen before

			message = mention['text']
			sender = mention['user']['screen_name']
			sender_id = mention['user']['id_str']
			
			db.run(""" REPLACE INTO court.bigcases_mentions(id, txt, screen_name, user_id)
					VALUES(%s, %s, %s, %s) """,
					(mention['id'], mention['text'].encode('ascii','ignore'), sender, sender_id, ))
			
			# Check whether this is an approved requestor
			if sender.lower() in APPROVED:

				# Check whether this is a valid request
				m = FOLLOWPATTERN.search(message)
				if m:
#					print 'Got your message'
#					print 'New case: %s, No. %s in %s' % (m.group(1), m.group(2), m.group(4))
					case_number = m.group(2)
					court = m.group(4)
					name = m.group(1)

					# First, see if we already have it
					new = check_case(case_number, court, sender)
					if new == 'new':
						# Next, check to see if we have that court
						court_msg = check_court(court, sender)
						if 'Sorry' in court_msg:
							msg = court_msg
						else:
							# Next, check to see if it's in the db
							if db.getOne(""" SELECT COUNT(*) AS c
										FROM court.pacer_raw
										WHERE case_number = %s
											AND court = %s """, (case_number, court, )) == 0:
								msg = '@%s That case isn\'t in my database.' % sender
							else:	
						
						
								# Add this to the list and update the file
								cases.append({'name':name, 'case_number': case_number, 'court':court })
								out = { 'supreme_court_cases': cases_sct, 'cases':cases }
								with open('bigcases.json','w') as listfile:
									listfile.write(json.dumps(out, indent=4))
								
								# Go back and update some filings from today

								filings = db.getDict(""" UPDATE court.pacer_raw
													SET bigcase = 1
													WHERE bigcase = 0
														AND case_number = %s
														AND court = %s
														AND modified >= DATE_ADD(NOW(), INTERVAL -12 HOUR)
													ORDER BY modified DESC
													LIMIT 10 """, (case_number, court, ))
													
								
								# Tell us you have added it. Include any data notes for that court?
								msg = 'I\'m now following %s, No. %s in %s. %s' % (name, case_number, court, check_court(court, sender))
						
					else:
						msg = new
						
					# Now post the message
					print 'RESULT: %s' % msg
					tw.update_status(status = msg)
		
			else: 
				# Not approved sender
				if mention['in_reply_to_status_id'] is None:
					if FOLLOW.search(message):
						# Somebody has disturbed my slumber
						msg = NOTAPPROVED[random.randint(0, len(NOTAPPROVED) -1)]
						id = str(mention['id'])
						tw.update_status(status = '@' + sender + ' ' + msg, in_reply_to_status_id = id)
						
						